# Genetic Variant Classifications — CADD_PHRED 회귀 예측

ClinVar 변이 데이터를 활용해 대립유전자 빈도, 변이 위치, 유전자 등의 특성으로 변이 병원성 점수(`CADD_PHRED`)를 예측하는 회귀 분석 프로젝트. 선형회귀 → 랜덤포레스트 → XGBoost 순으로 모델을 확장하며 RMSE, MAE, R²로 비교한다.

## 핵심 질문
1. 대립유전자 빈도, 변이 위치, 유전자 등의 특성으로 `CADD_PHRED`를 예측할 수 있는가?
2. 선형회귀 대비 랜덤포레스트·XGBoost가 예측 성능을 얼마나 개선하는가?
3. RMSE·MAE·R²로 비교했을 때 어떤 모델이 가장 우수하고, 어떤 특성이 가장 중요한가?

(자세한 문제 정의: [`docs/Problem-definition.md`](docs/Problem-definition.md))

## 데이터
- 원본: [ClinVar Conflicting Classifications](https://www.kaggle.com/datasets/kevinarvai/clinvar-conflicting) — `data/clinvar_conflicting.csv` (65,188행 × 46열)
- 회귀 타겟: `CADD_PHRED` (변이 병원성 점수, 결측 1.68%)
- 보조 타겟: `CLASS` (임상 해석 상충 여부, 이진값) — 별도 분류 파이프라인으로 확장 (아래 참고)
- 훈련/테스트 분할: `data/train.csv` / `data/test.csv` (80/20, `random_state=42`)

## 폴더 구조
```
data/     원본 및 분할 데이터
docs/     문제 정의, EDA 요약, 분석 리포트, 작업 로그, 워크플로우
outputs/  분석·모델 결과 (그래프, 지표 표)
scripts/  분석 파이프라인 스크립트
```

## 실행 방법
```bash
python scripts/eda.py                    # 탐색적 데이터 분석
python scripts/split_train_test.py       # 훈련/테스트 분할
python scripts/train_compare_models.py   # 1차 모델 비교 (LR/RF/XGBoost)
python scripts/model_improvement.py      # 피처 엔지니어링 + CV + 하이퍼파라미터 튜닝
python scripts/shap_interpretation.py    # 튜닝된 XGBoost SHAP 해석
python scripts/classify_conflicting.py   # CLASS(상충 여부) 분류로 확장
python scripts/ablation_sift_polyphen.py # SIFT/PolyPhen 제외 ablation 실험
```
파이프라인 세부 단계와 공통 규칙은 [`docs/workflow.md`](docs/workflow.md) 참고.

## 결과 요약 (최종, holdout 테스트 기준)
| 단계 | 모델 | RMSE | MAE | R² |
|---|---|---|---|---|
| Baseline | LinearRegression | 6.366 | 5.044 | 0.651 |
| Baseline | RandomForest | 6.164 | 4.814 | 0.672 |
| Baseline | XGBoost | 6.063 | 4.769 | 0.683 |
| +피처엔지니어링 | XGBoost | 5.856 | 4.583 | 0.704 |
| **+튜닝** | **XGBoost** | **5.817** | **4.537** | **0.708** |

→ 대립유전자 빈도·변이 위치·유전자 등의 특성으로 `CADD_PHRED` 변동의 약 71%를 설명 가능 (순수 평균 예측 기준선 R²=0 대비). **피처 엔지니어링(로그변환, 위치 파싱)의 효과가 하이퍼파라미터 튜닝보다 큼**(R² 개선폭 +0.021 vs +0.004).

**SHAP 해석 + Ablation**: 튜닝된 XGBoost는 `IMPACT`, `SIFT`, `PolyPhen`, `Consequence` 순으로 크게 의존. SIFT·PolyPhen을 제외하고 재학습한 ablation 실험 결과 R²가 0.708→0.598(15.5%↓)로 크게 하락 — SHAP에서 예상했던 "정보 중복"과 달리, 두 변수는 다른 특성이 포착 못하는 독립적인 예측력을 갖고 있음을 확인. (`outputs/shap/`, `outputs/ablation/`)

**분류 확장 (`CLASS`, 상충 여부)**: XGBoost 기준 ROC-AUC 0.791, F1 0.564 — 회귀보다 어려운 문제. 잘 알려진 질병 유전자(BRCA1/2, LDLR, MSH6 등)일수록 검사기관 간 해석 상충 가능성이 높게 나타남. (`outputs/classification/`)

전체 결과와 해석은 [`docs/analysis_report.md`](docs/analysis_report.md) 참고.

## 문서
| 문서 | 내용 |
|---|---|
| [`docs/Problem-definition.md`](docs/Problem-definition.md) | 데이터 선정 이유, 핵심 질문, 회귀분석 기준선 |
| [`docs/eda_summary.md`](docs/eda_summary.md) | EDA 수치 요약 |
| [`docs/analysis_report.md`](docs/analysis_report.md) | 종합 분석 리포트 (EDA + 모델 비교 + 해석) |
| [`docs/workflow.md`](docs/workflow.md) | 파이프라인 구조와 재현 실행 가이드 |
| [`docs/work_log.md`](docs/work_log.md) | 작업 진행 이력 |
