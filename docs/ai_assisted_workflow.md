# AI-Assisted Workflow

This project was built with Claude Code as an implementation assistant. This document is intended to make that collaboration transparent — what the human directed and validated, and what the AI tool implemented — rather than leave AI involvement unstated.

## Responsibility split

| Task | Responsibility |
|---|---|
| Research questions | Human |
| Dataset selection | Human |
| Genomic/biological interpretation | Human |
| ML experiment design (which models, which validations to run) | Human, AI-assisted on implementation options |
| Python implementation (preprocessing, models, plots) | Claude Code-assisted |
| Debugging (e.g. CPU oversubscription, encoding errors, broken PDP grids) | Human + AI-assisted |
| Statistical evaluation | Human-reviewed |
| Model interpretation (SHAP → ablation reasoning) | Human, with AI-assisted implementation |
| Biological interpretation | Human |
| Documentation | Human + AI-assisted |
| Repository restructuring into this portfolio layout | AI-assisted (Claude Code), human-directed and reviewed |

## How Claude Code was used

- **Code scaffolding**: initial structure for each pipeline script (data loading, `ColumnTransformer` preprocessing pipelines, model training loops, metric computation).
- **Repetitive preprocessing code**: one-hot encoding setup, feature-set construction across baseline vs. engineered variants, the shared `src/common.py` module extracted during this restructuring to remove duplicated preprocessing logic across scripts.
- **Debugging**: diagnosing and fixing concrete issues encountered during the project, documented in `docs/development_log.md` — e.g. CPU oversubscription from double-parallelized `RandomizedSearchCV` + internal model `n_jobs=-1` (development_log.md, item 7), a `UnicodeEncodeError` from em-dash characters on a `cp949` console (item 17), and a broken PCA/t-SNE explained-variance calculation caused by reusing an unscaled tree-model preprocessor (item 19).
- **Visualization support**: matplotlib plotting code for the ~30 figures across `results/`.
- **Documentation assistance**: drafting and iterating on `docs/analysis_report.md` and this restructured documentation set, from findings the human directed and reviewed.
- **This restructuring itself**: reorganizing the repository from `scripts/`/`outputs/` into the current `src/`/`results/`/`docs/` layout, extracting `src/common.py` to fix an import-chain break caused by numeric script prefixes, updating all path references, and drafting the new documentation files — done by Claude Code following an explicit human-provided specification, then spot-verified (see below).

## Human validation

Findings and generated code were not accepted at face value. Validation included:

- **Output comparisons**: re-running refactored scripts (`01_eda.py`, `02_split_data.py`, `03_baseline_models.py`) after this restructuring and confirming metrics matched the previously committed results to full floating-point precision (see `docs/development_log.md` and the restructuring commit for verification detail).
- **Metric consistency**: cross-checking every headline number in `README.md` against the actual CSV/JSON files in `results/` before publishing, rather than trusting a prior draft or memory of the numbers.
- **Alternative validation methods used specifically to stress-test claims**, not just to add analysis breadth:
  - **Gene Group Split** — to test whether the SHAP-driven feature importance and headline R² reflected genuine variant-level signal rather than gene memorization.
  - **Ablation (SIFT/PolyPhen removal)** — to test whether SHAP's importance ranking implied redundancy, which it turned out not to (Section 4, `docs/model_validation.md`).
  - **Statistical hypothesis testing with effect sizes** (not just p-values) — to avoid overinterpreting statistical significance at n≈60,000, where even negligible differences (e.g. CLASS vs. CADD_PHRED, Cohen's d=-0.087) reach significance.
  - **Root-cause investigation of the residual "band" pattern** — rather than reporting the visual anomaly as-is, it was directly investigated and found to be substantially a quantization/overplotting artifact, with a smaller real bias underneath (`docs/model_validation.md`, Section 6).
- **Biological plausibility checks**: interpretations (e.g. why IMPACT/Consequence/SIFT/PolyPhen matter, why gene identity is a leakage risk) were grounded in genomics domain knowledge, not accepted purely because a model or SHAP plot ranked a feature highly.

## Responsible use

AI tools were used for implementation assistance — writing code, debugging, drafting documentation, and executing a human-specified restructuring — not for autonomous clinical variant classification or medical decision-making. No output from this project (model predictions, SHAP rankings, or generated text) was used to make or inform any real clinical decision. See [`limitations.md`](limitations.md) for the boundaries of what this project's models can and cannot claim.
