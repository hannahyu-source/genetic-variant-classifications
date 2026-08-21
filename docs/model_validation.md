# Model Validation

This document collects every check performed to interrogate whether the headline regression/classification results are trustworthy, and where they break down. Methodology details (preprocessing, splits, metrics) are in [`methodology.md`](methodology.md).

## 1. Holdout Evaluation

Baseline (original features, default hyperparameters) vs. tuned (engineered features + `RandomizedSearchCV`), all on the same 20% holdout test set (`random_state=42`):

| Stage | Model | RMSE | MAE | R² |
|---|---|---|---|---|
| Baseline | LinearRegression | 6.366 | 5.044 | 0.651 |
| Baseline | RandomForest | 6.164 | 4.814 | 0.672 |
| Baseline | XGBoost | 6.063 | 4.769 | 0.683 |
| +Feature engineering | XGBoost | 5.856 | 4.583 | 0.704 |
| **+Tuning** | **XGBoost** | **5.817** | **4.537** | **0.708** |

Feature engineering (log-transformed allele frequency, parsed position fields) improved XGBoost R² by **+0.021** (0.683→0.704); subsequent hyperparameter tuning added only **+0.004** more (0.704→0.708). The same pattern holds for Random Forest (+0.024 from engineering vs. +0.004 from tuning). **Domain-informed feature engineering contributed more than hyperparameter search** for this dataset — see `results/regression/model_improvement/`.

## 2. Random Split Limitation

All of the results above use a row-level random 80/20 split. Because ClinVar contains many variants per gene, this allows the *same gene* to appear in both train and test — the model could, in principle, be partly memorizing gene identity rather than learning transferable variant-level signal.

## 3. Gene-Based Group Split

`src/10_gene_group_validation.py` measured this directly: **95.7% of the genes in the random-split test set already appeared in training**. It then re-evaluated using `GroupShuffleSplit`/`GroupKFold` grouped by `SYMBOL`, guaranteeing zero gene overlap between train and test.

| Validation | RMSE | MAE | R² |
|---|---|---|---|
| Random split (as above) | 5.898 | 4.577 | 0.709 |
| **Gene Group Split** (466 unseen genes, trained on 1,860) | 6.538 | 5.074 | **0.639** |
| GroupKFold, 5-fold average | 6.374 ± 0.143 | 4.973 ± 0.116 | 0.653 ± 0.025 |

R² dropped by about 7 percentage points (0.709 → 0.639) under a strictly unseen-gene evaluation, and the drop reproduced consistently across all 5 GroupKFold folds (not a one-off artifact of a single split). **Interpretation**: performance decreased under a more realistic unseen-gene setting, indicating the random split was optimistic — but the model retained substantial predictive signal (R²≈0.64–0.65) beyond simple gene memorization. Gene Group Split gives a stricter estimate of unseen-gene performance; it is not equivalent to full external clinical validation (see [`limitations.md`](limitations.md)).

## 4. Feature Importance Validation: SHAP → Ablation

SHAP (`src/05_shap_interpretation.py`) ranked feature importance for the tuned XGBoost regressor as **IMPACT > SIFT > PolyPhen > Consequence** (mean |SHAP value|, aggregated to the original variable level). Because SIFT and PolyPhen both estimate protein-functional damage — conceptually overlapping with what CADD itself measures — the natural hypothesis was that they might be *redundant* with other functional annotations already in the model.

`src/06_ablation_analysis.py` tested this directly by retraining the identical tuned XGBoost configuration with SIFT and PolyPhen removed:

| Configuration | RMSE | MAE | R² |
|---|---|---|---|
| Full (with SIFT + PolyPhen) | 5.817 | 4.537 | 0.708 |
| Without SIFT + PolyPhen | 6.826 | 5.297 | 0.598 |

R² fell by 15.5% (0.708 → 0.598) — far more than a "redundant feature" hypothesis would predict. **SHAP importance alone does not establish redundancy**: it measures how much a feature contributes to the model's predictions, not whether some other feature could substitute for it if removed. Only the ablation experiment could answer that question, and it showed SIFT/PolyPhen carry substantial independent predictive signal that IMPACT, Consequence, and BLOSUM62 do not capture on their own.

## 5. Residual Analysis

The residual plot (`results/regression/01_residual_plot.png`) shows the tuned XGBoost regressor tracking `y = x` reasonably well overall, with two notable patterns:

- A tail-compression effect: variants with true `CADD_PHRED` > 40 are systematically under-predicted.
- A dense vertical band of points between actual CADD_PHRED values of 23 and 36, where predicted values scatter widely (0–40) — investigated separately below.

## 6. Quantization Investigation

`src/11_residual_investigation.py` was written specifically to explain the 23–36 band. Findings:

- **Root cause is not a model deficiency.** `CADD_PHRED` values in this range are heavily quantized/rounded in the source data (e.g., 34.0 appears exactly 1,431 times, 35.0 appears 1,263 times, 33.0 appears 931 times). This 23–36 band alone accounts for **29.6%** of all variants. The apparent "vertical band" in the residual plot is an overplotting artifact of many points sharing the same discretized x-coordinate, not evidence of higher model error in that range.
- **Residual variance inside the band is actually lower than average**: std 4.67 vs. 5.82 test-set-wide — the visual impression of scatter is misleading.
- **A real, smaller systematic bias does exist inside the band**: `missense_variant`/MODERATE-impact variants (81% of the band) are under-predicted by ~2.7 points on average (actual 27.4 vs. predicted 24.7), while `stop_gained`/HIGH-impact variants are over-predicted by ~2.3 points (actual 34.7 vs. predicted 37.0) — the model shrinks predictions toward each group's mean.
- **A real, smaller-scale failure mode**: the largest individual absolute errors in the band cluster around cases where `SIFT`/`PolyPhen` report "tolerated"/"benign" (or are missing) but the true `CADD_PHRED` is still high — e.g. a BRCA2 missense variant (`NC_000013.10:g.32915175T>C`, SIFT=tolerated, PolyPhen=benign) with actual CADD_PHRED 23.3 but predicted 4.6 (residual +18.65). See [`variant_case_studies.md`](variant_case_studies.md) for detail.

**Conclusion**: this is a case study in not trusting a visual pattern at face value — the "anomaly" was mostly a plotting artifact, but investigating it surfaced a real (smaller) shrinkage bias and a real SIFT/PolyPhen-discordance failure mode.

## 7. Calibration

The `CLASS` (conflict) classifier's predicted probabilities are **overconfident**: the calibration curve (`results/classification/03_calibration_curve.png`) sits below the diagonal — at a predicted probability of 0.8, the observed conflict rate is only about 0.61. This is a plausible side effect of `scale_pos_weight` class-imbalance correction, which shifts predicted probabilities without necessarily preserving calibration. Any downstream use of the raw probability (e.g., for risk communication) would need separate calibration (Platt scaling / isotonic regression).

## 8. Threshold Evaluation

`src/09_threshold_analysis.py` swept the classification threshold for the tuned XGBoost `CLASS` classifier (Average Precision = 0.533):

| Scenario | Threshold | Precision | Recall | F1 |
|---|---|---|---|---|
| Default (0.5) | 0.500 | 0.461 | 0.724 | 0.564 |
| F1-maximizing | 0.495 | 0.460 | 0.737 | **0.566** |
| High recall (Recall ≥ 0.9) | 0.344 | 0.375 | 0.900 | 0.529 |
| High precision (Precision ≥ 0.7) | 0.810 | 0.700 | 0.088 | 0.157 |

The default threshold is already very close to the F1-optimal point — tuning it barely moves F1 (0.564 → 0.566). The more informative finding is that pushing precision to 0.70 collapses recall to 0.088 (91% of true conflicting variants missed) — there is no high-confidence operating region where the model can flag conflicts with both good precision and reasonable coverage. This is a limitation of the underlying feature signal, not something threshold tuning can fix.

## 9. Model Failure Modes

Summary of confirmed failure modes across all validation steps:

- **Regression toward group means**: inside the quantized 23–36 CADD band, missense/MODERATE variants are under-predicted and stop_gained/HIGH variants are over-predicted, both shrinking toward their group average (Section 6).
- **Tail compression**: true CADD_PHRED > 40 is systematically under-predicted (Section 5).
- **SIFT/PolyPhen-discordant cases are a genuine blind spot**: when SIFT/PolyPhen say "tolerated"/"benign" but the true CADD_PHRED is high (driven by conservation or other evidence SIFT/PolyPhen don't capture), the model — which itself leans heavily on SIFT/PolyPhen (Section 4) — under-predicts substantially. Several of these cases involve major disease genes (BRCA1/2, PMM2, BUB1B).
- **Difficult consequence classes**: intronic and other MODIFIER-impact variants carry weak, ambiguous CADD signal and contribute to the largest individual residuals (e.g., a large-negative-residual case in `NEB`, `frameshift_variant`/HIGH impact, actual CADD_PHRED 0.008 vs. predicted 31.3 — see [`variant_case_studies.md`](variant_case_studies.md)).
- **The `CLASS` classifier is harder and less reliable than the regression task**: ROC-AUC 0.791 vs. regression R²≈0.71, an overconfident probability calibration (Section 7), and no usable high-precision operating point (Section 8) — consistent with `CLASS` reflecting submitter disagreement (a partly human/procedural signal) rather than a property fully determined by the available genomic annotations.
