# Variant Case Studies

Four representative variants pulled directly from the test-set predictions of the tuned XGBoost regressor (same configuration as `src/04_model_improvement.py` Step 3 / `src/11_residual_investigation.py`) and from the raw dataset (`data/raw/clinvar_conflicting.csv`). All identifiers (HGVS genomic notation, `CLNHGVS` column) and metrics below are real values pulled from the data and from re-running the documented model configuration — none are fabricated.

---

## Case 1 — Accurately predicted, high-deleteriousness variant

| Field | Value |
|---|---|
| Gene | `MYO6` |
| Variant identifier (HGVS) | `NC_000006.11:g.76554623C>T` |
| Consequence | `stop_gained` |
| IMPACT | HIGH |
| CADD_PHRED (actual) | 39.0 |
| Predicted CADD_PHRED | 38.29 |
| Residual (actual − predicted) | +0.72 |
| SIFT / PolyPhen | not applicable (stop-gain, not missense) |
| CLASS | 0 (not conflicting) |

**Model interpretation**: a clean example of the model working as intended — a stop-gained, HIGH-impact variant with a high true CADD_PHRED is predicted almost exactly, well within normal residual noise.

**Biological interpretation**: stop-gained variants truncate the protein and are consistently among the most deleterious consequence classes (`docs/biological_interpretation.md`); the model's reliance on `IMPACT`/`Consequence` is well-justified here.

**Limitations**: this is a "clean" case — no SIFT/PolyPhen conflict, no quantization-band ambiguity. It should not be read as representative of overall model accuracy at high CADD values; Section 5 of `model_validation.md` documents a systematic under-prediction tendency for CADD_PHRED > 40 that this case does not exhibit.

---

## Case 2 — Large under-prediction, and a SIFT/PolyPhen-discordant case

| Field | Value |
|---|---|
| Gene | `BRCA2` |
| Variant identifier (HGVS) | `NC_000013.10:g.32915175T>C` |
| Consequence | `missense_variant` |
| IMPACT | MODERATE |
| CADD_PHRED (actual) | 23.3 |
| Predicted CADD_PHRED | 4.65 |
| Residual (actual − predicted) | +18.65 |
| SIFT | tolerated |
| PolyPhen | benign |
| CLASS | 0 (not conflicting) |

**Model interpretation**: this is one of the largest single residuals in the test set, and it directly illustrates the failure mode identified in `model_validation.md` Section 6 / 9: because SIFT and PolyPhen are the model's 2nd and 3rd most important features (SHAP), when both explicitly say "tolerated"/"benign," the model predicts a low CADD_PHRED — but the true CADD_PHRED is still moderately high (23.3), presumably reflecting evidence CADD incorporates that SIFT/PolyPhen do not (e.g. conservation-based signal).

**Biological interpretation**: SIFT and PolyPhen are both protein-sequence/structure-based predictors and can disagree with conservation-based scores like CADD for the same variant — they are different tools measuring related but non-identical biological properties (`docs/biological_interpretation.md`, SIFT/PolyPhen sections).

**Limitations**: this is a single case, not a systematic audit of all SIFT/PolyPhen-discordant variants in BRCA2 or elsewhere. It should not be read as a claim about the clinical significance of this specific variant — CADD_PHRED is a deleteriousness-prioritization score, not a pathogenicity classification (`docs/limitations.md`).

---

## Case 3 — Large over-prediction (regression failure mode)

| Field | Value |
|---|---|
| Gene | `NEB` |
| Variant identifier (HGVS) | `NC_000002.11:g.152541343delA` |
| Consequence | `frameshift_variant` |
| IMPACT | HIGH |
| CADD_PHRED (actual) | 0.008 |
| Predicted CADD_PHRED | 31.30 |
| Residual (actual − predicted) | −31.30 |
| SIFT / PolyPhen | not applicable (frameshift, not missense) |
| CLASS | 0 (not conflicting) |

**Model interpretation**: the largest single over-prediction observed in the test set. The model strongly associates `frameshift_variant`/HIGH impact with high deleteriousness (correctly, on average — see Case 1's HIGH-impact pattern and `docs/biological_interpretation.md`), but this specific variant's true CADD_PHRED is anomalously close to zero.

**Biological interpretation**: not established by this project's analysis. A near-zero CADD_PHRED for a nominally HIGH-impact frameshift is unusual and could reflect a real biological nuance CADD's scoring model captured for this variant (e.g. position very close to a transcript end, escaping nonsense-mediated decay, or a large gene like *NEB* where the frameshift falls in a region CADD's underlying model treats as low-consequence) — or it could reflect an artifact/edge case in the original CADD scoring pipeline for this exact position. This project's data does not include enough information to distinguish between those explanations.

**Limitations**: this case is presented explicitly as an unresolved model failure, not an explained one. It is a useful illustration that IMPACT/Consequence, while strong average predictors, do not universally guarantee accurate individual-variant predictions.

---

## Case 4 — ClinVar interpretation-conflict example

| Field | Value |
|---|---|
| Gene | `BRCA1` |
| Variant identifier (HGVS) | `NC_000017.10:g.41197778A>G` |
| Consequence | `missense_variant` |
| IMPACT | MODERATE |
| CADD_PHRED (actual) | 28.0 |
| SIFT | deleterious |
| PolyPhen | probably_damaging |
| CLASS | 1 (conflicting interpretation across ClinVar submitters) |

**Model interpretation**: unlike Cases 1–3, this illustrates the secondary classification task (`src/08_conflict_classification.py`), not the regression task — no per-variant predicted probability was separately computed for this case; aggregate classifier performance (ROC-AUC 0.791, F1 0.564) is reported in `model_validation.md`.

**Biological interpretation**: SIFT and PolyPhen both flag this variant as functionally damaging, and CADD_PHRED (28.0) is well above the dataset median (14.09) — by molecular-severity annotations alone this variant looks moderately-to-highly deleterious. Yet ClinVar submitters disagree on its clinical interpretation. This is consistent with the pattern documented in `docs/biological_interpretation.md`: heavily-studied genes like BRCA1 accumulate disagreement specifically on their harder-to-classify variants, for reasons (evidence completeness, differing lab criteria, phenotype context) this dataset cannot directly test.

**Limitations**: `CLASS` reflects submitter disagreement recorded in this dataset snapshot, not a ground-truth pathogenicity label — this case should not be read as evidence about this variant's actual clinical significance (`docs/limitations.md`).
