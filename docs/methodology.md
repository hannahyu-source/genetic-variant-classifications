# Methodology

## 1. Dataset

- **Source**: [ClinVar Conflicting Classifications](https://www.kaggle.com/datasets/kevinarvai/clinvar-conflicting) (Kaggle), a derived dataset that joins NCBI ClinVar variant submissions with Ensembl VEP (Variant Effect Predictor) functional annotations.
- **Size**: 65,188 rows × 46 columns.
- **Primary regression target**: `CADD_PHRED` — a CADD (Combined Annotation Dependent Depletion) deleteriousness-prioritization score, continuous, missing in 1.68% of rows.
- **Secondary classification target**: `CLASS` — a binary flag for whether a ClinVar record has conflicting interpretations across submitters (0 = not conflicting, 74.8%; 1 = conflicting, 25.2%).
- **Key feature groups used**: allele frequency (`AF_ESP`, `AF_EXAC`, `AF_TGP`), variant location (`CHROM`, `POS`, exon/intron/protein/CDS/cDNA position strings), gene identity (`SYMBOL`), functional-impact annotations (`IMPACT`, `Consequence`, `BIOTYPE`, `CLNVC`), protein-effect predictors (`SIFT`, `PolyPhen`, `BLOSUM62`), and a loss-of-function-intolerance score (`LoFtool`).

Full column-level details are in [`eda_summary.md`](eda_summary.md).

## 2. Regression Target: `CADD_PHRED`

CADD_PHRED is a genome-wide variant deleteriousness-prioritization score produced by an independent annotation tool (CADD), not a value assigned by ClinVar itself. It is **not** an ACMG/AMP clinical pathogenicity classification:

```
CADD deleteriousness prioritization ≠ clinical pathogenicity classification (ACMG/AMP)
```

A high CADD_PHRED indicates a variant is predicted to be more evolutionarily/functionally deleterious relative to other variants genome-wide; it does not by itself establish that a specific variant causes disease in a specific clinical context. This project treats CADD_PHRED prediction as a regression task on genomic/functional features, not as a clinical classification task.

## 3. Data Preprocessing

Implemented in `src/common.py` (shared by `04_model_improvement.py` onward) and duplicated in simplified form in `src/03_baseline_models.py` for the first baseline pass:

- **Missing values**: columns with ≥86% missingness (`MOTIF_*`, `DISTANCE`, `SSR`, `CLN*INCL`, `INTRON`, etc.) were dropped from modeling entirely — confirmed via `results/eda/missing_ratio.csv`. Remaining numeric features are median-imputed; categorical features are imputed with the constant `"missing"`.
- **Target leakage guard**: `CADD_RAW` was excluded from all feature sets — it correlates with `CADD_PHRED` at r=0.955 (near-identical information) and would trivially leak the target.
- **Allele frequency**: `AF_ESP`, `AF_EXAC`, `AF_TGP` are zero-inflated (most variants are rare/absent from reference panels). The engineered feature set applies `log1p` to each.
- **Genomic position fields**: `EXON`/`INTRON` are stored as `"n/total"` strings, parsed into a ratio (`EXON_ratio`, `INTRON_ratio`). `Protein_position`/`CDS_position`/`cDNA_position` are stored as single numbers, ranges (`"800-802"`), or partially-unknown ranges (`"?-117"`); all are parsed into a single numeric value (ranges averaged).
- **Gene identity (`SYMBOL`)**: 2,328 unique genes — too high-cardinality for direct one-hot encoding. The top 30 most frequent genes are kept as individual categories; all others are grouped into `"Other"` (`GENE_GROUP`).
- **Categorical encoding**: `OneHotEncoder(handle_unknown="ignore")` for `CHROM`, `IMPACT`, `Consequence`, `BIOTYPE`, `CLNVC`, `SIFT`, `PolyPhen`, `GENE_GROUP`.
- **Numeric scaling**: applied only for models that need it (Linear Regression, and the PCA/t-SNE embedding in `12_advanced_visualization.py`); tree-based models (Random Forest, XGBoost) use unscaled numeric features.

## 4. Train/Test Split

- `train_test_split(test_size=0.2, random_state=42)` — a row-level random split, applied identically across all regression and classification scripts so results are directly comparable.
- Rows with missing `CADD_PHRED` are dropped before splitting for regression (64,096 → 51,276 train / 12,820 test).
- This split is later shown to be optimistic for estimating generalization to unseen genes — see [`model_validation.md`](model_validation.md) and [`limitations.md`](limitations.md).

## 5. Baseline Models

Three model families, chosen to represent increasing modeling capacity:

- **Linear Regression** — a simple, interpretable baseline; establishes how much signal is linearly recoverable from the raw features.
- **Random Forest Regressor** — a bagged tree ensemble; captures non-linearities and interactions without much tuning.
- **XGBoost Regressor** — a gradient-boosted tree ensemble; typically the strongest tabular-data baseline and the model carried forward through feature engineering, tuning, SHAP, ablation, and generalization analysis.

## 6. Feature Engineering

Implemented in `src/common.py::build_feature_sets`. On top of the raw feature set, adds: `log1p`-transformed allele frequencies, `EXON_ratio`/`INTRON_ratio`, and parsed numeric `Protein_position`/`CDS_position`/`cDNA_position`. See [Section 3](#3-data-preprocessing) above for details.

## 7. Hyperparameter Tuning

`RandomizedSearchCV(n_iter=10, cv=3, scoring="neg_root_mean_squared_error", random_state=42)` applied independently to Random Forest and XGBoost over the engineered feature set. Search spaces cover tree depth/count, learning rate, subsampling ratios, and regularization terms (`reg_alpha`, `reg_lambda`) for XGBoost. Internal estimator parallelism (`n_jobs`) is fixed to `1` while the search itself uses `n_jobs=-1`, to avoid CPU oversubscription (see [`workflow.md`](workflow.md)).

## 8. Evaluation Metrics

- **RMSE** (root mean squared error) — penalizes large errors more heavily; primary tuning objective.
- **MAE** (mean absolute error) — average magnitude of error, more robust to outliers.
- **R²** — proportion of target variance explained; primary headline metric for comparing pipeline stages.
- For the classification task: **Accuracy, Precision, Recall, F1, ROC-AUC** — Accuracy is reported but explicitly flagged as potentially misleading given the 74.8/25.2 class imbalance (see [`model_validation.md`](model_validation.md)).

## 9. Explainability

`src/05_shap_interpretation.py` re-fits the tuned XGBoost regressor and computes SHAP values with `shap.TreeExplainer`. One-hot-encoded columns are aggregated back to their original variable (e.g. all `IMPACT_*` dummy columns summed into `IMPACT`) so importance is interpretable at the level of the original genomic feature, not individual dummy categories.

## 10. Ablation

`src/06_ablation_analysis.py` re-trains the same tuned XGBoost configuration with `SIFT` and `PolyPhen` removed from the feature set, to directly test whether the high SHAP importance of these two features reflects genuinely independent predictive signal or redundant information already captured by other features (`IMPACT`, `Consequence`, `BLOSUM62`, etc.).

## 11. Generalization Validation

`src/10_gene_group_validation.py` compares the standard row-level random split against a gene-based split (`GroupShuffleSplit`, and `GroupKFold` with 5 folds) grouped by `SYMBOL`, to test performance on genes that never appear in the training set at all.

## 12. Secondary Classification Task

`src/08_conflict_classification.py` predicts `CLASS` — whether a ClinVar record has a conflicting interpretation across submitters — using the same engineered feature set plus `CADD_PHRED` as an additional input feature (this is not leakage, since the classification target is `CLASS`, not `CADD_PHRED`). Class imbalance (74.8%/25.2%) is handled via `class_weight="balanced"` (Logistic Regression, Random Forest) and `scale_pos_weight` (XGBoost). This is a ClinVar interpretation-conflict predictor, not a pathogenic/benign variant classifier — see [`biological_interpretation.md`](biological_interpretation.md).

## 13. Statistical Validation

`src/07_statistical_validation.py` tests whether `CADD_PHRED` differs meaningfully across groups defined by `CLASS`, `IMPACT`, and `Consequence`:

- **CLASS**: Welch's t-test + Mann-Whitney U (two groups), plus Cohen's d for effect size.
- **IMPACT** / **Consequence**: Kruskal-Wallis H-test (more than two groups, non-normal residuals expected), plus an approximate eta-squared (epsilon-squared) effect size, and Bonferroni-corrected pairwise Mann-Whitney post-hoc tests for IMPACT.

Effect sizes are reported alongside p-values because with n≈60,000, even negligible differences reach statistical significance — see [`model_validation.md`](model_validation.md) for the results and interpretation.
