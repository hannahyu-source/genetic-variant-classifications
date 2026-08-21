# 데이터

## 원본 데이터셋

- **출처**: [ClinVar Conflicting Classifications](https://www.kaggle.com/datasets/kevinarvai/clinvar-conflicting) (Kaggle, kevinarvai 업로드)
- **원본 출처**: NCBI ClinVar + Ensembl VEP(Variant Effect Predictor) 주석을 결합해 만든 파생 데이터셋
- **파일명**: `clinvar_conflicting.csv`
- **크기**: 65,188행 × 46열
- **라이선스**: Kaggle 페이지에 명시된 라이선스를 따름(원본 ClinVar는 NCBI 공개 데이터, Kaggle 게시자가 VEP 주석을 추가해 재배포). 이 저장소는 학습/포트폴리오 목적의 재배포이며, 상업적 이용 전에는 원본 라이선스 조건을 다시 확인해야 한다.
- **버전/시점**: Kaggle 데이터셋 다운로드 시점 기준 스냅샷이며, 현재 ClinVar 데이터베이스와 동기화되어 있지 않다(자세한 내용은 [`docs/limitations.md`](../docs/limitations.md) 참고).

## data/raw/

- `clinvar_conflicting.csv` — 원본 데이터. 모든 파이프라인 스크립트가 이 파일을 읽어 자체적으로 전처리·분할한다. **수정하지 않는다.**

## data/processed/

- `train.csv` (51,276행), `test.csv` (12,820행) — `src/02_split_data.py`가 `CADD_PHRED` 결측 행을 제거한 뒤 80/20으로 분할해 저장한 참고용 스냅샷.
- **주의**: `src/03_baseline_models.py` 이후의 모든 스크립트는 이 파일을 읽지 않고, 원본 CSV를 각자 다시 읽어 동일한 `random_state=42`, `test_size=0.2` 조건으로 자체 분할한다. 따라서 이 두 파일은 "분할 결과를 확인/재사용하기 위한 산출물"이며, 파이프라인의 필수 입력은 아니다.

## 훈련/테스트 분할 방식

- **행 단위 랜덤 분할**: `train_test_split(test_size=0.2, random_state=42)` — 모든 회귀·분류 스크립트에서 동일하게 사용해 스크립트 간 결과를 비교할 수 있게 했다.
- **한계**: 같은 유전자(예: BRCA1)의 서로 다른 변이가 train/test 양쪽에 나뉘어 들어갈 수 있어, 모델이 유전자 정체성을 부분적으로 "암기"할 위험이 있다. 실제로 기존 랜덤 분할에서는 test 세트 유전자의 95.7%가 train에도 존재하는 것으로 확인됐다(`src/10_gene_group_validation.py`).
- **보완**: 이 한계를 정량화하기 위해 별도로 유전자(`SYMBOL`) 기준 `GroupShuffleSplit`/`GroupKFold` 검증을 수행한다 — 완전히 새로운 유전자에 대한 더 현실적인 성능 추정치를 제공한다. 결과는 [`results/generalization/`](../results/generalization/), 해석은 [`docs/model_validation.md`](../docs/model_validation.md) 참고.
