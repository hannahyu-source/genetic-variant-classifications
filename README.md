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
- 참고 타겟(미사용): `CLASS` (임상 해석 상충 여부, 이진값 — 별도 분류 문제에 적합)
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
```
파이프라인 세부 단계와 공통 규칙은 [`docs/workflow.md`](docs/workflow.md) 참고.

## 결과 요약 (1차 비교, 기본 하이퍼파라미터)
| 모델 | RMSE | MAE | R² |
|---|---|---|---|
| LinearRegression | 6.366 | 5.044 | 0.651 |
| RandomForest | 6.343 | 4.906 | 0.653 |
| XGBoost | 6.059 | 4.770 | 0.684 |

→ 대립유전자 빈도·변이 위치·유전자 등의 특성만으로 `CADD_PHRED` 변동의 약 65~68%를 설명 가능 (순수 평균 예측 기준선 대비 RMSE 약 41~44% 감소). 자세한 근거와 기준선 정의는 [`docs/Problem-definition.md`](docs/Problem-definition.md), 전체 해석은 [`docs/analysis_report.md`](docs/analysis_report.md) 참고.

피처 엔지니어링(로그변환, 위치 파싱)과 하이퍼파라미터 튜닝을 적용한 개선 결과는 진행 중이며 완료 후 리포트에 반영 예정.

## 문서
| 문서 | 내용 |
|---|---|
| [`docs/Problem-definition.md`](docs/Problem-definition.md) | 데이터 선정 이유, 핵심 질문, 회귀분석 기준선 |
| [`docs/eda_summary.md`](docs/eda_summary.md) | EDA 수치 요약 |
| [`docs/analysis_report.md`](docs/analysis_report.md) | 종합 분석 리포트 (EDA + 모델 비교 + 해석) |
| [`docs/workflow.md`](docs/workflow.md) | 파이프라인 구조와 재현 실행 가이드 |
| [`docs/work_log.md`](docs/work_log.md) | 작업 진행 이력 |
