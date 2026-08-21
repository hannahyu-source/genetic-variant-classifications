# 분석 워크플로우

`work_log.md`가 "무엇을 언제 했는지"를 기록한 로그라면, 이 문서는 "파이프라인이 어떻게 구성되어 있고 어떤 순서로 실행하는지"를 정리한 재현 가이드다.

## 폴더 구조
```
data/     원본 및 분할 데이터 (clinvar_conflicting.csv, train.csv, test.csv)
docs/     문제 정의, EDA 요약, 분석 리포트, 작업 로그, 워크플로우 문서
outputs/  분석/모델 결과물 (그래프, 지표 표, JSON)
scripts/  분석 파이프라인 스크립트
```

## 파이프라인 단계

| 순서 | 스크립트 | 입력 | 출력 | 역할 |
|---|---|---|---|---|
| 1 | `scripts/eda.py` | `data/clinvar_conflicting.csv` | `outputs/eda/*.png`, `docs/eda_summary.md` | 결측치·분포·상관관계 탐색 |
| 2 | `scripts/split_train_test.py` | `data/clinvar_conflicting.csv` | `data/train.csv`, `data/test.csv` | 80/20 훈련·테스트 분할 |
| 3 | `scripts/train_compare_models.py` | `data/clinvar_conflicting.csv` | `outputs/model_comparison.*`, `outputs/feature_importance_*.png` | LR/RF/XGBoost 1차 비교 (기본 하이퍼파라미터) |
| 4 | `scripts/model_improvement.py` | `data/clinvar_conflicting.csv` | `outputs/model_improvement/*` | 피처 엔지니어링 + 5-fold CV + 하이퍼파라미터 튜닝 + 최종 비교 |
| 5 | `scripts/shap_interpretation.py` | `data/clinvar_conflicting.csv` | `outputs/shap/*` | 튜닝된 XGBoost를 SHAP `TreeExplainer`로 해석 (`model_improvement.py`에서 import) |
| 6 | `scripts/classify_conflicting.py` | `data/clinvar_conflicting.csv` | `outputs/classification/*` | `CLASS`(상충 여부) 분류로 확장 — LR/RF/XGB, Accuracy·Precision·Recall·F1·ROC-AUC |
| 7 | `scripts/ablation_sift_polyphen.py` | `data/clinvar_conflicting.csv` | `outputs/ablation/*` | SIFT/PolyPhen 제외 시 튜닝된 XGBoost 성능 변화 검증 |
| 8 | `scripts/statistical_tests.py` | `data/clinvar_conflicting.csv` | `outputs/stats/*` | CLASS/IMPACT/Consequence 그룹 간 CADD_PHRED 차이 가설검정 (t-test, Mann-Whitney, Kruskal-Wallis, 효과크기) |
| 9 | `scripts/threshold_analysis.py` | `data/clinvar_conflicting.csv` | `outputs/threshold_analysis/*` | XGBoost 분류기 임계값별 Precision-Recall 트레이드오프 분석 |
| 10 | `scripts/advanced_visualizations.py` | `data/clinvar_conflicting.csv` | `outputs/advanced_viz/*` | 잔차플롯, PCA/t-SNE 임베딩, 분류기 보정곡선, 유전자x IMPACT 히트맵, 2D PDP 상호작용 |
| 11 | `scripts/build_report_pdf.py` | `docs/analysis_report.md` | `docs/analysis_report.pdf` | Markdown 리포트를 스타일 적용 HTML로 변환 후 Chrome headless로 PDF 인쇄 (최종 보고서) |

문서 산출물: `docs/Problem-definition.md`(문제 정의·기준선), `docs/analysis_report.md`(종합 리포트), `docs/work_log.md`(작업 이력)

## 재현 실행 순서
```bash
python scripts/eda.py
python scripts/split_train_test.py
python scripts/train_compare_models.py
python scripts/model_improvement.py
```
`train_compare_models.py`와 `model_improvement.py`는 각자 내부에서 원본 CSV를 읽어 자체적으로 분할하므로 `split_train_test.py`가 먼저 실행되지 않아도 동작하지만, 분석 흐름상 먼저 실행해 `data/train.csv`·`data/test.csv`를 확보해두는 것을 권장한다.

## 공통 규칙 (모든 스크립트에서 동일하게 적용)
- **타겟**: `CADD_PHRED` (결측 행 제외)
- **분할**: `train_test_split(test_size=0.2, random_state=42)` — 스크립트 간 결과 비교가 가능하도록 통일
- **평가지표**: RMSE, MAE, R²
- **제외 특성**: 결측률 90% 이상 컬럼, `CADD_RAW`(타겟과 상관계수 0.955 → 데이터 누수 위험)
- **범주형 인코딩**: 원-핫 인코딩 (`OneHotEncoder(handle_unknown="ignore")`), 유전자(`SYMBOL`)는 상위 30개 + 기타로 그룹화 후 인코딩
- **병렬처리 주의사항**: `RandomizedSearchCV`/`cross_validate`처럼 바깥에서 `n_jobs=-1`로 병렬화하는 경우, 안쪽 모델(RandomForest/XGBoost)의 `n_jobs`는 반드시 `1`로 고정한다 — 이중 병렬화 시 CPU 오버서브스크립션으로 실행 시간이 크게 늘어나는 문제를 `model_improvement.py` 1차 실행에서 겪었다 (`work_log.md` 7번 항목 참고).

## 모델 개선 파이프라인 세부 단계 (`model_improvement.py`)
1. Baseline 5-fold CV — 원본 피처, 기본 하이퍼파라미터
2. Engineered 5-fold CV — AF 로그변환, EXON/INTRON 비율, Protein/CDS/cDNA position 파싱 추가
3. RandomizedSearchCV 튜닝 — RandomForest·XGBoost 대상, `n_iter=10, cv=3, scoring=neg_root_mean_squared_error`
4. Holdout 최종 비교 — baseline / engineered / tuned 조합을 동일 테스트셋에서 RMSE·MAE·R²로 비교
