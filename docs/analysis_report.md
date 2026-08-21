# 분석 리포트: ClinVar 변이 병원성 점수(CADD_PHRED) 회귀 예측

## 1. 개요
- **데이터**: `data/clinvar_conflicting.csv` (ClinVar Conflicting Classifications, 65,188행 × 46열)
- **목표**: 대립유전자 빈도, 변이 위치, 유전자, 기능적 영향 등의 특성으로 변이의 병원성 점수(`CADD_PHRED`)를 예측하는 회귀 모델을 구축하고, 선형회귀·랜덤포레스트·XGBoost 세 모델을 RMSE·MAE·R²로 비교한다.
- 문제 정의와 선정 이유는 `docs/Problem-definition.md` 참고.

## 2. 데이터 설명
- 원본 타겟 `CLASS`(임상 해석 상충 여부, 이진값)는 0(비상충) 74.8%, 1(상충) 25.2%로 불균형 — 이번 회귀분석의 타겟이 아니라 참고용 변수로만 사용.
- 회귀 타겟 `CADD_PHRED`(연속형, 변이 유해성 점수)는 결측률 1.68%로 낮아 타겟으로 채택. 결측 행은 분석에서 제외.
- `MOTIF_*`, `DISTANCE`, `SSR`, `CLN*INCL` 등은 결측률 86~100%로 모델링에서 제외.
- 고카디널리티 변수: 유전자(`SYMBOL`) 2,328종, `Consequence` 48종 — 유전자는 상위 30종 + 기타로 그룹화하여 사용.

## 3. 탐색적 데이터 분석(EDA) 요약
전체 플롯: `outputs/eda/` (11개), 원자료 요약: `docs/eda_summary.md`

- **결측치**: 상위 결측 컬럼은 대부분 예측에 거의 쓸모없는 수준(90%+)으로 확인되어 제거 결정에 근거가 됨.
  ![결측치 비율](../outputs/eda/01_missing_ratio.png)
- **CADD_PHRED 분포**: 평균 15.7, 표준편차 10.8, 우측 꼬리가 긴 분포(0.001~99).
  ![CADD_PHRED 분포](../outputs/eda/03_cadd_phred_distribution.png)
- **상관관계**: `CADD_RAW`와 `CADD_PHRED`는 상관계수 0.955로 사실상 동일 정보 → 특성에서 `CADD_RAW` 제외(데이터 누수 방지). `BLOSUM62`(아미노산 치환 점수)가 가장 강한 상관(-0.303), 대립유전자 빈도는 약한 음의 상관(-0.15~-0.17). `CLASS`는 `CADD_PHRED`와 거의 무관(-0.038) — 상충 여부와 유해성 점수는 독립적인 정보.
  ![상관관계 히트맵](../outputs/eda/08_correlation_heatmap.png)
- **IMPACT별 차이**: HIGH 등급일수록 `CADD_PHRED` 중앙값이 뚜렷하게 높음 — 강력한 예측 변수로 확인.
  ![IMPACT별 CADD_PHRED](../outputs/eda/05_impact.png)
- **대립유전자 빈도**: 0값이 대부분(zero-inflated)이라 로그변환 등 추가 처리가 필요함을 확인.
  ![대립유전자 빈도 분포](../outputs/eda/09_allele_frequency.png)

## 4. 회귀분석 기준선
| 기준선 | RMSE | MAE | R² |
|---|---|---|---|
| 순수 기준선 (훈련 평균만 예측) | 10.770 | 9.107 | 0.000 |
| 모델 기준선 (선형회귀, 원본 피처) | 6.366 | 5.044 | 0.651 |

선형회귀만으로도 순수 기준선 대비 RMSE 약 41% 감소, R² 0→0.65로 개선 — 특성들이 실질적인 설명력을 가짐을 확인. 상세: `docs/Problem-definition.md` 참고.

## 5. 모델 비교 (1차: 원본 피처, 기본 하이퍼파라미터)
학습/테스트 분할: 80/20 (`data/train.csv` / `data/test.csv`, random_state=42)

| 모델 | RMSE | MAE | R² |
|---|---|---|---|
| LinearRegression | 6.366 | 5.044 | 0.651 |
| RandomForest | 6.343 | 4.906 | 0.653 |
| **XGBoost** | **6.059** | **4.770** | **0.684** |

![모델 비교](../outputs/model_comparison.png)

**해석**:
- XGBoost가 세 지표 모두에서 최우수 — IMPACT/Consequence/SIFT/PolyPhen 등 변수 간 비선형 상호작용을 트리 기반 모델이 더 잘 포착.
- RandomForest는 선형회귀 대비 근소한 개선에 그침 — 기본 하이퍼파라미터(트리 수 300, 깊이 제한 없음)로는 XGBoost의 부스팅 방식만큼의 이득을 내지 못함.
- XGBoost의 특성 중요도 상위 변수는 `outputs/feature_importance_XGBoost.png` 참고.

## 6. 결론 및 다음 단계
- 유전 변이의 대립유전자 빈도·기능적 영향·아미노산 치환 정보만으로 `CADD_PHRED`의 상당 부분(R²≈0.65~0.68)을 설명할 수 있음을 확인했다.
- 현재 **모델 개선 단계**(피처 엔지니어링: 로그변환·위치 파싱, 5-fold 교차검증, RandomizedSearchCV 하이퍼파라미터 튜닝)를 진행 중이며, 완료되는 대로 baseline → 엔지니어링 → 튜닝 단계별 개선폭을 이 리포트에 추가할 예정이다. (결과 파일 예정 위치: `outputs/model_improvement/`)
- 추후 확장 가능한 분석 방향: SHAP 기반 모델 해석, 원본 분류 타겟(`CLASS`) 예측 모델 구축, Consequence/CLASS 그룹 간 통계적 가설검정.
