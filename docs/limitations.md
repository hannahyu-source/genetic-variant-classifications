# Limitations

## 1. CADD is not clinical pathogenicity

The regression target, `CADD_PHRED`, is a genome-wide deleteriousness-prioritization score produced by an independent annotation tool (CADD). It is **not** an ACMG/AMP clinical pathogenicity classification, and this project does not treat it as one:

```
CADD deleteriousness prioritization ≠ ACMG/AMP pathogenicity classification
```

A model that predicts CADD_PHRED accurately is predicting an annotation score, not diagnosing a variant as pathogenic or benign.

## 2. Feature circularity / correlated annotations

`SIFT`, `PolyPhen`, `IMPACT`, `Consequence`, and `CADD_PHRED` all capture overlapping aspects of "how disruptive is this variant to the gene product," derived from related (sometimes shared) underlying biology — sequence conservation, protein structure, and predicted functional consequence. The ablation experiment (`docs/model_validation.md`, Section 4) shows SIFT/PolyPhen are not fully redundant with the other features, but some degree of shared information among these annotations is inherent to the feature set. Any claim of "the model discovered X" should be read with this circularity in mind — the model is partly re-deriving relationships that were designed into the annotation tools themselves.

## 3. Random-split optimism

The primary holdout results (R²=0.708) use a row-level random 80/20 split. Because a given gene contributes many variants, genes shared between train and test can inflate apparent performance — confirmed directly: 95.7% of test-set genes in the random split also appear in training (`docs/model_validation.md`, Section 3).

## 4. Gene Group Split is stricter, but not full external validation

The gene-based split (R²≈0.64–0.65 on genes never seen in training) is a meaningfully more realistic estimate of unseen-gene performance, but it is still evaluated on variants drawn from the same dataset, same annotation pipeline, and same time snapshot as training. It does not substitute for validation on an independently collected, externally sourced variant set.

## 5. Dataset source and vintage

The dataset is a Kaggle-hosted derivative of ClinVar (joined with Ensembl VEP annotations); see [`data/README.md`](../data/README.md) for source details. It represents a **snapshot at the time it was compiled for Kaggle**, not the current state of ClinVar. ClinVar interpretations are actively revised as new evidence accumulates — variant classifications and conflict status in this dataset may no longer match the live ClinVar database.

## 6. ClinVar conflict target reflects submitter disagreement, not ground truth

`CLASS` (used as the secondary classification target) indicates whether submitting laboratories disagreed on a variant's interpretation in ClinVar — it is a measure of **inter-submitter agreement**, not an independently verified measure of whether the variant is actually pathogenic or benign. A "conflicting" label does not mean the variant's true clinical significance is ambiguous in an absolute sense, only that this dataset's submitters recorded different interpretations.

## 7. No prospective clinical validation

This model was developed and evaluated entirely offline, on retrospective data, for portfolio/research purposes. It has not been evaluated as a clinical decision-support system, has not undergone any regulatory or clinical validation process, and should not be used to inform real clinical decisions.

## 8. Missing phenotype context

The dataset contains no patient-specific phenotype, indication, or clinical presentation information. Real-world variant interpretation typically depends heavily on phenotype context (the same variant can be interpreted differently depending on the clinical picture); this project's models cannot account for that, because the data does not include it.

## 9. Model calibration

The `CLASS` classifier's predicted probabilities are measurably overconfident — the calibration curve sits below the diagonal, with observed conflict rates around 0.61 at a predicted probability of 0.8 (`docs/model_validation.md`, Section 7). Raw predicted probabilities from this classifier should not be interpreted as calibrated risk estimates without additional calibration (e.g. Platt scaling / isotonic regression), which this project did not implement.

## 10. Generalizability beyond this dataset

Performance was only evaluated within this dataset's distribution: this specific ClinVar/VEP annotation snapshot, this reference genome build, and whatever sequencing/curation practices produced these particular submissions. Performance on other variant databases, other populations, other genome builds, or variants derived from different sequencing/curation pipelines is unknown and was not tested.
