# 작업 로그

## 2026-08-21

### 1. 프로젝트 구조 세팅
- `data/`, `docs/`, `outputs/`, `scripts/` 폴더 생성
- `clinvar_conflicting.csv`를 `data/`로 이동

### 2. 데이터 구조 파악 및 분석 방향 결정
- 데이터가 Kaggle "ClinVar Conflicting Classifications"임을 확인 (65,188행 × 46열)
- 원본 타겟 `CLASS`는 이진값(상충 여부)이라 회귀분석(RMSE/MAE/R²)과 맞지 않음을 확인
- 연속형 회귀 타겟으로 `CADD_PHRED`(변이 병원성 점수, 결측 1.68%)를 채택하기로 결정
- 회귀 vs 분류 두 방향을 제안하고, 회귀(방향 B) 진행으로 확정

### 3. 1차 모델 비교 파이프라인
- `scripts/train_compare_models.py` 작성 및 실행
- 특성: 대립유전자 빈도, IMPACT/Consequence/BIOTYPE/CLNVC/SIFT/PolyPhen, 유전자(상위 30개+기타)
- 결과 (`outputs/model_comparison.csv`, `.png`, feature importance 플롯):
  | 모델 | RMSE | MAE | R² |
  |---|---|---|---|
  | LinearRegression | 6.366 | 5.044 | 0.651 |
  | RandomForest | 6.343 | 4.906 | 0.653 |
  | XGBoost | 6.059 | 4.770 | 0.684 |

### 4. 탐색적 데이터 분석 (EDA)
- `scripts/eda.py` 작성 및 실행 → 플롯 11개(`outputs/eda/`), 요약(`docs/eda_summary.md`)
- 주요 발견: 결측 90%+ 컬럼 다수, `CADD_RAW`와 `CADD_PHRED` 상관 0.955(사실상 동일 정보, 특성에서 제외), `BLOSUM62`가 가장 강한 상관, `CLASS`는 `CADD_PHRED`와 거의 무관

### 5. 다음 분석 방향 논의
- 모델 개선 / SHAP 해석 / 분류(CLASS) 확장 / 통계적 가설검정 / 심화 시각화 5가지 제안
- 사용자가 "모델 개선부터" 진행 요청

### 6. 모델 개선 파이프라인 작성
- `scripts/model_improvement.py` 작성: 피처 엔지니어링(AF 로그변환, EXON/INTRON 비율 파싱, Protein/CDS/cDNA position 파싱) + 5-fold 교차검증 + RandomizedSearchCV 하이퍼파라미터 튜닝 + 최종 holdout 비교

### 7. 첫 실행 시도 및 문제 발생
- 백그라운드로 실행(task `b3xapdfzk`), 30분 이상 경과해도 완료 안 됨
- 원인 추정: 파이프라인 내부 모델(`n_jobs=-1`)과 `RandomizedSearchCV`/`cross_validate`(`n_jobs=-1`)의 이중 병렬화로 인한 CPU 오버서브스크립션
- 작업 중단 후 스크립트 수정: 내부 모델 `n_jobs=1`로 고정, 탐색/CV만 `n_jobs=-1` 유지, `RandomizedSearchCV` `n_iter` 15→10으로 축소, 출력 버퍼링 해제(`python -u`)
- 재실행 (task `bbwm0ufuv`), 진행 중

### 8. 문서화
- `docs/Problem-definition.md` 작성: 데이터 선정 이유, 오늘 풀 문제 3가지, 오늘 확인할 것 3가지
- 회귀분석 기준선 정의 및 계산 후 `Problem-definition.md`에 추가:
  - 순수 기준선(훈련 평균 예측): RMSE 10.770, MAE 9.107, R² 0.000
  - 모델 기준선(선형회귀, 원본 피처): RMSE 6.366, MAE 5.044, R² 0.651

### 9. 훈련/테스트 데이터 분할
- `scripts/split_train_test.py` 작성 및 실행
- `CADD_PHRED` 결측 1,092행 제외 후 80/20 분할 (`random_state=42`, 다른 모든 스크립트와 동일 기준)
- 저장: `data/train.csv`(51,276행), `data/test.csv`(12,820행)

### 10. 분석 리포트 작성
- `docs/analysis_report.md` 작성: 개요, 데이터 설명, EDA 요약, 기준선, 1차 모델 비교, 결론/다음 단계
- 모델 개선 결과는 백그라운드 작업 완료 후 추가 예정

### 11. GitHub 저장소 생성 및 푸시
- `git init`, `main` 브랜치로 초기 커밋 (README, docs, scripts, outputs, data)
- `gh repo create genetic-variant-classifications --public` 로 저장소 생성 및 푸시
- https://github.com/hannahyu-source/genetic-variant-classifications

### 12. 모델 개선 파이프라인 완료
- `model_improvement.py` 재실행 두 차례 시행착오 끝에 완료 (총 소요시간 8,413초 ≈ 140분)
  - 1차 시도: 파이프라인 내부 모델과 CV/탐색이 모두 `n_jobs=-1`이라 CPU 오버서브스크립션 발생 → 중단
  - 2차 시도: 내부 모델 `n_jobs=1`로 수정했으나 baseline RandomForest가 `max_depth=None`(깊이 제한 없음)이라 여전히 느림(13분+) → 중단
  - 3차 시도: RandomForest `max_depth=20` 제한 + 튜닝 탐색에서 `max_depth=None` 옵션 제거 후 재실행 → 완료
- 최종 결과 (holdout, `outputs/model_improvement/`):
  | 단계 | 최우수 모델 | RMSE | MAE | R² |
  |---|---|---|---|---|
  | Baseline | XGBoost | 6.063 | 4.769 | 0.683 |
  | +피처엔지니어링 | XGBoost | 5.856 | 4.583 | 0.704 |
  | +튜닝 | XGBoost | 5.817 | 4.537 | 0.708 |
- 피처 엔지니어링(로그변환, 위치 파싱)의 개선폭(+0.021)이 하이퍼파라미터 튜닝의 개선폭(+0.004)보다 큼을 확인
- `docs/analysis_report.md`에 결과 반영 완료

## 진행 중 / 다음에 할 일
- [ ] 모델 개선 결과 커밋 및 GitHub 푸시
- [ ] (선택) SHAP 해석, `CLASS` 분류 모델, 통계적 가설검정 등 추가 분석 방향
