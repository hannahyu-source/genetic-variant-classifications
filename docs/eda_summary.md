# EDA Summary - ClinVar Conflicting Classifications

- 전체 행 수: 65,188
- 전체 컬럼 수: 46

## 결측치 상위 10개 컬럼
- MOTIF_POS: 100.0%
- MOTIF_NAME: 100.0%
- MOTIF_SCORE_CHANGE: 100.0%
- HIGH_INF_POS: 100.0%
- DISTANCE: 99.8%
- SSR: 99.8%
- CLNSIGINCL: 99.7%
- CLNDISDBINCL: 99.7%
- CLNDNINCL: 99.7%
- INTRON: 86.5%

## CLASS 분포 (원본 분류 타겟)
- 0 (비상충): 48,754 (74.8%)
- 1 (상충): 16,434 (25.2%)

## CADD_PHRED 분포 (회귀 타겟 후보)
- count: 64096.000
- mean: 15.686
- std: 10.836
- min: 0.001
- 25%: 7.141
- 50%: 14.090
- 75%: 24.100
- max: 99.000
- 결측 비율: 1.68%

## CADD_PHRED와 수치형 변수 상관관계
- CADD_RAW: 0.955
- ORIGIN: 0.060
- CLASS: -0.038
- LoFtool: -0.039
- AF_EXAC: -0.155
- AF_ESP: -0.164
- AF_TGP: -0.167
- BLOSUM62: -0.303

## 기타 카디널리티
- 고유 유전자(SYMBOL) 수: 2,328
- 고유 Consequence 종류: 48
- 고유 염색체: 24