# 분석 워크플로우

`development_log.md`가 "무엇을 언제 했는지"를 기록한 로그라면, 이 문서는 "파이프라인이 어떻게 구성되어 있고 어떤 순서로 실행하는지"를 정리한 재현 가이드다.

## 폴더 구조
```
data/       원본(raw/) 및 분할(processed/) 데이터
src/        분석 파이프라인 스크립트 (01~12번, 실행 순서대로 번호 부여) + common.py(공통 모듈) + utils/(보조 스크립트)
results/    연구 질문 단위로 정리된 분석·모델 결과물 (그래프, 지표 표, JSON)
docs/       문제 정의, 방법론, 검증, 생물학적 해석, 한계, 작업 로그 등 문서
notebooks/  포트폴리오 워크스루 노트북
```

## 공통 모듈: `src/common.py`

`05_shap_interpretation.py`부터 `12_advanced_visualization.py`까지는 `04_model_improvement.py`가 정의한 피처 엔지니어링·전처리 로직을 재사용해야 한다. 파일명이 숫자로 시작하면 `import` 대상이 될 수 없기 때문에(`import 04_model_improvement`는 불가능), 공유 로직(`ROOT`/`DATA_PATH` 등 경로 상수, `build_feature_sets`, `build_preprocessor`, 위치 파싱 함수 등)을 `src/common.py`로 분리했다. `03_baseline_models.py`도 원본(비가공) 피처 목록과 전처리기 빌더를 `common.py`에서 가져와 중복을 제거했다.

## 파이프라인 단계

| 순서 | 스크립트 | 입력 | 출력 | 역할 |
|---|---|---|---|---|
| 1 | `src/01_eda.py` | `data/raw/clinvar_conflicting.csv` | `results/eda/*.png`, `docs/eda_summary.md` | 결측치·분포·상관관계 탐색 |
| 2 | `src/02_split_data.py` | `data/raw/clinvar_conflicting.csv` | `data/processed/train.csv`, `data/processed/test.csv` | 80/20 훈련·테스트 분할 (참고용 스냅샷) |
| 3 | `src/03_baseline_models.py` | `data/raw/clinvar_conflicting.csv` | `results/regression/model_comparison.*`, `results/regression/feature_importance_*.png` | LR/RF/XGBoost 1차 비교 (원본 피처, 기본 하이퍼파라미터) |
| 4 | `src/04_model_improvement.py` | `data/raw/clinvar_conflicting.csv` | `results/regression/model_improvement/*` | 피처 엔지니어링 + 5-fold CV + 하이퍼파라미터 튜닝 + 최종 비교 |
| 5 | `src/05_shap_interpretation.py` | `data/raw/clinvar_conflicting.csv` | `results/explainability/shap/*` | 튜닝된 XGBoost를 SHAP `TreeExplainer`로 해석 |
| 6 | `src/06_ablation_analysis.py` | `data/raw/clinvar_conflicting.csv` | `results/explainability/ablation/*` | SIFT/PolyPhen 제외 시 튜닝된 XGBoost 성능 변화 검증 (SHAP 가설 실험 검증) |
| 7 | `src/07_statistical_validation.py` | `data/raw/clinvar_conflicting.csv` | `results/statistical_validation/*` | CLASS/IMPACT/Consequence 그룹 간 CADD_PHRED 차이 가설검정 (t-test, Mann-Whitney, Kruskal-Wallis, 효과크기) |
| 8 | `src/08_conflict_classification.py` | `data/raw/clinvar_conflicting.csv` | `results/classification/*` | `CLASS`(ClinVar 해석 상충 여부) 분류로 확장 — LR/RF/XGB, Accuracy·Precision·Recall·F1·ROC-AUC |
| 9 | `src/09_threshold_analysis.py` | `data/raw/clinvar_conflicting.csv` | `results/classification/threshold_analysis/*` | XGBoost 분류기 임계값별 Precision-Recall 트레이드오프 분석 |
| 10 | `src/10_gene_group_validation.py` | `data/raw/clinvar_conflicting.csv` | `results/generalization/*` | 유전자(`SYMBOL`) 기반 GroupShuffleSplit/GroupKFold로 미지 유전자 일반화 검증 |
| 11 | `src/11_residual_investigation.py` | `data/raw/clinvar_conflicting.csv` | `results/biological_insights/residual_investigation/*` | 잔차 플롯의 23~36 구간 이상 패턴(밴드) 원인 규명 |
| 12 | `src/12_advanced_visualization.py` | `data/raw/clinvar_conflicting.csv` | `results/regression/`, `results/explainability/`, `results/classification/`, `results/biological_insights/`에 분산 저장 | 잔차플롯, PCA/t-SNE 임베딩, 분류기 보정곡선, 유전자×IMPACT 히트맵, 2D PDP 상호작용 (연구 질문별로 결과 폴더가 다름) |
| - | `src/utils/build_report_pdf.py` | `docs/analysis_report.md` | `docs/analysis_report.pdf` | Markdown 리포트를 스타일 적용 HTML로 변환 후 Chrome/Edge headless로 PDF 인쇄 (최종 보고서 생성 유틸리티) |

문서 산출물: `docs/problem_definition.md`(문제 정의·기준선), `docs/analysis_report.md`(종합 리포트, 원본 섹션 구성 유지), `docs/development_log.md`(작업 이력)

## 재현 실행 순서
```bash
python src/01_eda.py
python src/02_split_data.py
python src/03_baseline_models.py
python src/04_model_improvement.py
python src/05_shap_interpretation.py
python src/06_ablation_analysis.py
python src/07_statistical_validation.py
python src/08_conflict_classification.py
python src/09_threshold_analysis.py
python src/10_gene_group_validation.py
python src/11_residual_investigation.py
python src/12_advanced_visualization.py
```
`03`~`12`번 스크립트는 각자 내부에서 원본 CSV를 읽어 자체적으로 분할하므로 `02_split_data.py`가 먼저 실행되지 않아도 동작하지만, 분석 흐름상 먼저 실행해 `data/processed/train.csv`·`test.csv`를 확보해두는 것을 권장한다. `05`~`12`번은 `04_model_improvement.py`의 튜닝 결과(`results/regression/model_improvement/results.json`)에서 얻은 최적 하이퍼파라미터를 코드에 상수로 박아 넣어 재사용한다(재현성을 위해 매번 재튜닝하지 않음).

**소요 시간 참고**: `04_model_improvement.py`는 5-fold CV(3개 모델 × 2개 피처셋)와 `RandomizedSearchCV`(RF/XGB 각각 `n_iter=10, cv=3`)를 포함해 로컬 환경에서 약 140분이 걸렸다(`docs/development_log.md` 12번 항목 참고). 나머지 스크립트는 대부분 수 분 이내에 완료된다.

## 공통 규칙 (모든 스크립트에서 동일하게 적용)
- **타겟**: `CADD_PHRED` (결측 행 제외). CADD_PHRED는 변이의 잠재적 유해성(deleteriousness)을 우선순위화하는 점수이며 ACMG/AMP 임상 병원성 분류와는 다른 개념이다 — 자세한 내용은 [`docs/methodology.md`](methodology.md), [`docs/limitations.md`](limitations.md) 참고.
- **분할**: `train_test_split(test_size=0.2, random_state=42)` — 스크립트 간 결과 비교가 가능하도록 통일. (유전자 기반 분할은 `10_gene_group_validation.py`에서 별도로 수행)
- **평가지표**: RMSE, MAE, R² (회귀), Accuracy·Precision·Recall·F1·ROC-AUC (분류)
- **제외 특성**: 결측률 90% 이상 컬럼, `CADD_RAW`(타겟과 상관계수 0.955 → 데이터 누수 위험)
- **범주형 인코딩**: 원-핫 인코딩 (`OneHotEncoder(handle_unknown="ignore")`), 유전자(`SYMBOL`)는 상위 30개 + 기타로 그룹화 후 인코딩
- **병렬처리 주의사항**: `RandomizedSearchCV`/`cross_validate`처럼 바깥에서 `n_jobs=-1`로 병렬화하는 경우, 안쪽 모델(RandomForest/XGBoost)의 `n_jobs`는 반드시 `1`로 고정한다 — 이중 병렬화 시 CPU 오버서브스크립션으로 실행 시간이 크게 늘어나는 문제를 `04_model_improvement.py` 1차 실행에서 겪었다 (`docs/development_log.md` 7번 항목 참고).

## 모델 개선 파이프라인 세부 단계 (`src/04_model_improvement.py`)
1. Baseline 5-fold CV — 원본 피처, 기본 하이퍼파라미터
2. Engineered 5-fold CV — AF 로그변환, EXON/INTRON 비율, Protein/CDS/cDNA position 파싱 추가
3. RandomizedSearchCV 튜닝 — RandomForest·XGBoost 대상, `n_iter=10, cv=3, scoring=neg_root_mean_squared_error`
4. Holdout 최종 비교 — baseline / engineered / tuned 조합을 동일 테스트셋에서 RMSE·MAE·R²로 비교
