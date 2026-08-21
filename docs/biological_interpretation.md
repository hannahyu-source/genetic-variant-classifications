# Biological Interpretation

This document explains *why* the features that drove model performance ([`model_validation.md`](model_validation.md), SHAP results) make biological sense, and is explicit about where interpretation is grounded in this project's own analysis versus general domain background (marked "hypothesis" below).

## IMPACT

`IMPACT` (VEP-assigned: HIGH / MODERATE / LOW / MODIFIER) is a coarse categorical summary of how disruptive a variant's predicted effect on the gene product is — e.g. a stop-gain or frameshift is HIGH, a missense change is typically MODERATE, a synonymous change is typically LOW, and non-coding/regulatory changes are typically MODIFIER. It was the single largest SHAP contributor to CADD_PHRED predictions in this project, and the statistical test in `07_statistical_validation.py` confirmed a large, non-trivial effect size (Kruskal-Wallis eta² = 0.381, HIGH: mean 33.0 → MODIFIER: mean 6.8) — biologically consistent, since CADD is itself designed to score functional deleteriousness, and IMPACT is a direct, coarse proxy for that.

## Consequence

`Consequence` (e.g. `stop_gained`, `missense_variant`, `frameshift_variant`, `intron_variant`, `synonymous_variant`) is a finer-grained categorization of the predicted molecular effect than IMPACT. In this project's data, `stop_gained` variants had the highest mean CADD_PHRED (39.5) and `intron_variant` the lowest (6.2) among the top 8 most common consequence types (eta² = 0.379 — also a large effect). This tracks the expected biology: consequences that are more likely to abolish protein function (premature stop, frameshift) score as more deleterious than consequences with typically minimal functional impact (intronic, synonymous).

## SIFT

SIFT (Sorting Intolerant From Tolerant) predicts whether an amino acid substitution is likely to affect protein function, based on sequence conservation across homologous proteins — categorized here as e.g. `tolerated`, `deleterious`, `tolerated_low_confidence`. It was the second-largest SHAP contributor to CADD_PHRED, and the ablation experiment in `06_ablation_analysis.py` confirmed this is not a redundant signal: removing SIFT and PolyPhen together dropped R² by 15.5% (0.708 → 0.598), showing SIFT captures deleteriousness information that IMPACT/Consequence/BLOSUM62 do not.

## PolyPhen

PolyPhen (Polymorphism Phenotyping) is a related but methodologically distinct protein-damage predictor — categorized here as e.g. `benign`, `possibly_damaging`, `probably_damaging` — using a different combination of sequence and structural features than SIFT. Its high (3rd-ranked) SHAP importance, and its participation in the same ablation result described above, is consistent with PolyPhen and SIFT each contributing partially independent information despite measuring conceptually related properties (protein functional damage) — i.e. two different algorithms applied to overlapping but not identical biological signals.

**Important caveat surfaced by this project's own residual investigation** (`docs/model_validation.md`, Section 6): in a meaningful number of cases, SIFT/PolyPhen call a missense variant "tolerated"/"benign" while the true CADD_PHRED is still high — including several BRCA1/BRCA2 missense variants. Because the model leans heavily on SIFT/PolyPhen, these are exactly the cases where it under-predicts most. This suggests CADD is drawing on evidence (e.g., cross-species conservation, regulatory context) beyond what SIFT/PolyPhen alone capture — a finding grounded directly in this project's residual analysis, not just general domain knowledge.

## Allele Frequency

`AF_ESP`/`AF_EXAC`/`AF_TGP` (allele frequency in three reference population panels) showed a weak-to-moderate negative correlation with CADD_PHRED in EDA (r ≈ −0.15 to −0.17) and contributed modestly but non-trivially to SHAP importance after log-transformation. **Hypothesis, consistent with population genetics but not separately tested here**: highly deleterious variants are subject to stronger negative (purifying) selection, so they tend to be rarer in the general population — common variants are less likely to be highly deleterious. This project observed the correlation; it did not test the selection mechanism directly.

## Gene

`SYMBOL` (gene identity, grouped to the top 30 + "Other" as `GENE_GROUP`) contributed measurable SHAP importance (ranked 6th among aggregated variables). Biologically, this is plausible — different genes have different intrinsic tolerance to variation (captured in part by `LoFtool`, a loss-of-function intolerance score also in the feature set) and different baseline deleteriousness profiles for the mutations they accumulate. **However, gene identity is also exactly the feature most likely to produce a generalization/leakage concern**: a model that partly relies on "which gene is this" rather than "what does this variant do" will perform worse on genes it has never seen. `10_gene_group_validation.py` measured this directly — R² dropped from 0.709 (random split, 95.7% gene overlap) to 0.639 (strictly unseen genes) — real signal remains, but part of the original R² was gene-identity memorization rather than transferable variant-level biology. See [`model_validation.md`](model_validation.md), Section 3.

## ClinVar Conflict (`CLASS`)

Predicting `CLASS` (whether ClinVar submitters disagree on a variant's interpretation) proved a harder problem than predicting CADD_PHRED (ROC-AUC 0.791 vs. regression R²≈0.71), and the statistical test confirmed CADD_PHRED itself has almost no explanatory relationship with CLASS (Cohen's d = −0.087, "negligible" despite reaching statistical significance at this sample size). This is expected: interpretation conflict is not purely a function of a variant's molecular severity.

**Analysis-supported observation**: `08_conflict_classification.py`'s feature importance and `12_advanced_visualization.py`'s gene×IMPACT heatmap both show that well-studied, highly-submitted disease genes (BRCA1, BRCA2, LDLR, MSH6, and others) have elevated conflict rates — but concentrated specifically in their LOW/MODIFIER-impact variants (e.g. LDLR LOW-impact conflict rate 0.63, BRCA2 MODIFIER 0.64), while their HIGH-impact variants show low conflict (near 0–0.14 across genes). In other words, submitters largely agree on clearly damaging variants in these genes, and disagree mainly on ambiguous ones.

**Hypotheses for why conflict rate is elevated on ambiguous variants in heavily-studied genes** (plausible, not separately tested in this project's data):
- Genes with high clinical testing volume accumulate more independent submissions, mechanically increasing the chance that two submitters disagree.
- Evidence for pathogenicity is often incomplete for rare/ambiguous variants, especially compared to well-established founder or recurrent pathogenic variants.
- Different submitting laboratories may apply ACMG/AMP evidence criteria with different thresholds or emphasis.
- Phenotype context (which this dataset does not include) can shift interpretation for the same variant across different clinical presentations.
- Evidence and literature for a given variant evolve over time; submissions at different points in time may reflect different states of knowledge.
- Population-specific allele frequency evidence may be weighted differently across labs/panels.

These are offered as candidate explanations consistent with the observed pattern, not conclusions this dataset can directly verify — the dataset has no submitter identity, submission date, or ACMG evidence-code fields to test them further.
