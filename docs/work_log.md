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

### 13. 모델 개선 결과 커밋·푸시
- `README.md`, `docs/analysis_report.md`, `docs/work_log.md` 업데이트 후 `outputs/model_improvement/`와 함께 커밋·푸시 완료

### 14. SHAP 모델 해석
- `shap` 패키지 설치 후 `scripts/shap_interpretation.py` 작성·실행
- 튜닝된 XGBoost(`model_improvement.py` Step 3 best params)를 동일 엔지니어링 피처로 재학습 후 `TreeExplainer`로 SHAP 값 계산
- 원-핫 인코딩된 컬럼을 원본 변수 단위로 집계하는 로직 추가(`build_feature_groups`) — 개별 카테고리별이 아니라 변수 단위로 해석 가능하게 함
- 첫 실행 시 플롯 제목의 한글이 `DejaVu Sans` 폰트에서 깨짐(tofu box) → `plt.rcParams["font.family"] = "Malgun Gothic"` 추가 후 재실행
- 결과: `IMPACT > SIFT > PolyPhen > Consequence` 순으로 중요 — SIFT·PolyPhen이 CADD와 유사한 개념을 측정하는 도구라 정보 중복 가능성 확인

### 15. 분류(CLASS)로 확장
- `scripts/classify_conflicting.py` 작성·실행: LogisticRegression/RandomForest/XGBoost로 `CLASS`(상충 여부, 0:74.8%/1:25.2%) 예측
- 회귀와 동일 피처 + `CADD_PHRED`를 특성으로 추가(타겟이 다르므로 누수 아님), `class_weight`/`scale_pos_weight`로 불균형 보정
- 결과: XGBoost 최우수 (Accuracy=0.717, F1=0.564, ROC-AUC=0.791) — 회귀(R²≈0.71)보다 어려운 문제로 확인
- XGBoost feature importance 상위권에 `IMPACT_HIGH`, 대립유전자 빈도, 그리고 BRCA1/2·LDLR·MSH6 등 잘 알려진 질병 유전자들이 랭크됨
- `docs/analysis_report.md`(7·8·9장), `README.md`에 SHAP·분류 결과 반영

### 16. SIFT/PolyPhen 제외 Ablation 실험
- `scripts/ablation_sift_polyphen.py` 작성·실행: 튜닝된 XGBoost(회귀)를 SIFT·PolyPhen 없이 동일 조건(같은 튜닝 파라미터, 같은 train/test 분할)으로 재학습해 비교
- 결과: R² 0.708→0.598 (15.5% 하락), RMSE 5.817→6.826
- SHAP에서 예상했던 "정보 중복"과 반대 — SIFT·PolyPhen은 다른 특성이 포착 못하는 독립적인 예측 정보를 담고 있었음을 확인. SHAP 중요도만으로는 대체 가능성(중복 여부)을 판단할 수 없고, ablation이 필요하다는 교훈을 얻음
- `docs/analysis_report.md`(7-1절, 결론), `README.md`에 반영

### 17. 통계적 가설검정
- `scripts/statistical_tests.py` 작성·실행: CLASS(Welch's t-test + Mann-Whitney), IMPACT/Consequence(Kruskal-Wallis + 효과크기) 검정
- 콘솔 출력 시 em-dash(—) 문자로 `UnicodeEncodeError`(cp949) 발생 → `sys.stdout.reconfigure(encoding="utf-8")` 추가로 해결 (파일 저장 자체는 문제 없었음)
- 결과: IMPACT(eta²=0.381)·Consequence(eta²=0.379)는 큰 효과, CLASS는 통계적으로 유의하나 효과크기 무시할 수준(Cohen's d=-0.087) — 표본 크기(n≈6만)로 인한 "통계적 유의 vs 실질적 의미" 괴리를 확인
- `docs/analysis_report.md`(9장 신설, 결론 갱신), `README.md`, `docs/workflow.md`에 반영

### 18. 분류 임계값(threshold) 조정 — Precision-Recall 트레이드오프
- `scripts/threshold_analysis.py` 작성·실행: `classify_conflicting.py`의 XGBoost 분류기를 재학습해 `precision_recall_curve`로 임계값별 Precision/Recall/F1 계산
- 4개 시나리오 비교: 기본(0.5), F1 최대화(0.495), 고재현율(Recall≥0.9 → threshold=0.344), 고정밀(Precision≥0.7 → threshold=0.810)
- 결과: 기본 임계값이 이미 F1 최적점에 근접(AP=0.533), 고정밀 시나리오는 Recall이 0.088까지 붕괴 — 임계값 조정으로 해결 안 되는 특성 신호의 한계로 결론
- `docs/analysis_report.md`(8-1절 신설, 결론 갱신), `README.md`, `docs/workflow.md`에 반영

### 19. 심화 시각화 5종
- `scripts/advanced_visualizations.py` 작성: 잔차플롯, PCA/t-SNE 임베딩, 분류기 보정곡선, 유전자×IMPACT 히트맵, 2D PDP 상호작용
- 1차 실행 결과 2개 플롯에 버그 발견 및 수정:
  - PCA/t-SNE: 트리 모델용(스케일링 없음) preprocessor를 재사용해 위치 정보 등 스케일 큰 변수가 지배 → 설명분산 100%로 무의미. `scale_numeric=True` 전용 preprocessor로 교체 후 재실행(설명분산 37.6%로 정상화)
  - 2D PDP: `BLOSUM62`(결측 60%)에 NaN이 남아있어 sklearn이 `np.percentile`(NaN 무시 안 함)로 그리드를 깨뜨림 → 중앙값으로 결측 대체 후 재실행
- 주요 발견: (1) 고유해성 변이(CADD_PHRED>40)에서 모델이 체계적으로 과소예측, (2) t-SNE에서 IMPACT는 뚜렷한 군집을 형성하지만 CLASS는 모든 군집에 고르게 섞여 있음, (3) 분류기 예측 확률이 전반적으로 과대평가(overconfident, scale_pos_weight 부작용), (4) 유전자×IMPACT 히트맵에서 HIGH 등급은 상충 비율이 낮고 LOW/MODIFIER는 급증, (5) BLOSUM62·대립유전자 빈도 간 상호작용 확인
- `docs/analysis_report.md`(10장 신설, 결론 갱신), `README.md`, `docs/workflow.md`에 반영

### 20. 최종 보고서 PDF 생성
- `scripts/build_report_pdf.py` 작성: `docs/analysis_report.md`를 python-markdown으로 HTML 변환 → 표지·스타일 적용 → Chrome headless(`--print-to-pdf`)로 PDF 인쇄
- 1차 생성본에서 10장(심화 시각화) 이미지 5개가 마크다운 이미지 문법이 아니라 파일명 텍스트로만 적혀 있어 실제로 삽입 안 된 것을 발견 → `analysis_report.md` 수정 후 재생성 (18개→23개 이미지)
- 결과: `docs/analysis_report.pdf` (약 3MB, 표지+11개 섹션+그래프 23개)
- `.gitignore`에 빌드 중간 산출물 `docs/_report_build.html` 추가
- `README.md`, `docs/workflow.md`에 반영

### 21. 유전자 기반 Group Split 일반화 검증
- `scripts/gene_group_validation.py` 작성·실행: 기존 랜덤 분할 vs `GroupShuffleSplit`/`GroupKFold`(유전자 `SYMBOL` 단위) 비교
- `SYMBOL` 결측 16행 때문에 `GroupShuffleSplit`이 `ValueError: Input contains NaN`으로 실패 → dropna 대상에 `SYMBOL` 추가해 해결
- 진단: 기존 랜덤 분할은 test 유전자의 95.7%가 train에도 존재 — 우려했던 리키지가 실제로 큼
- 결과: 완전히 새로운 유전자(1,860개로 학습, 466개로 검증)에서 R² 0.709→0.639(단일 분할), GroupKFold 5-fold 평균 R²=0.653±0.025로 일관되게 재현
- 결론: 성능 하락은 있으나 치명적이지 않음 — 모델이 유전자를 암기한 게 아니라 일반화 가능한 특성(IMPACT, Consequence, BLOSUM62 등)으로 예측
- `docs/analysis_report.md`(11장 신설, 결론 갱신), `README.md`, `docs/workflow.md`에 반영, PDF 재생성

### 22. 잔차 이상 패턴(23~36 구간) 원인 규명
- `scripts/residual_anomaly_investigation.py` 작성·실행: 튜닝된 XGBoost 재학습 후 밴드 내 실제값 분포, Consequence/IMPACT 구성, 잔차 절대값 상위 사례 분석
- 원인 1: `CADD_PHRED`가 정수로 양자화되어 있음(34.0이 1,431번 등장 등) — 이 구간이 전체 데이터의 29.6%를 차지, 잔차 플롯의 "세로 띠"는 x축 이산화로 인한 과다 중첩(overplotting) 착시
- 원인 2: 밴드 내 잔차 표준편차(4.67)가 전체(5.82)보다 오히려 낮음 — 실제로는 이 구간에서 모델이 더 나쁘지 않음
- 원인 3(실재하는 편향): missense_variant/MODERATE(밴드의 81%)는 평균 2.7점 과소예측, stop_gained/HIGH는 평균 2.3점 과대예측 — 그룹 평균으로의 수축(shrinkage) 경향
- 원인 4(실재하는 한계): 개별 최대 오차 사례는 SIFT/PolyPhen이 "무해" 판정해도 실제 CADD는 높은 경우에 집중(BRCA1/2, PMM2, BUB1B 등) — SIFT/PolyPhen 의존도가 이런 사례에서 예측을 그르침
- `docs/analysis_report.md`(10-1-A 신설, 결론 갱신), `README.md`, `docs/workflow.md`에 반영, PDF 재생성

## 진행 중 / 다음에 할 일
- [ ] 잔차 이상 패턴 규명 결과 및 최신 PDF 커밋·GitHub 푸시
- [ ] (선택) CLASS 예측에 특화된 추가 특성(검사기관 수, 질병 카테고리 등) 발굴, 분류기 확률 보정(Platt scaling), SIFT/PolyPhen 오분류 사례의 공통 보존성 특성 발굴
