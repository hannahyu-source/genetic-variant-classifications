# 통계적 가설검정 결과

## Test A. CLASS(상충 여부)에 따른 CADD_PHRED 차이
- H0: 상충(CLASS=1) 변이와 비상충(CLASS=0) 변이의 CADD_PHRED 평균/분포에 차이가 없다.

- 그룹 크기: CLASS=0 (n=47,792, mean=15.924), CLASS=1 (n=16,304, mean=14.986)
- Welch's t-test: t=-9.966, p=2.33e-23
- Mann-Whitney U: U=373846012, p=1.14e-14
- Cohen's d = -0.087 (무시할 수준)
- 결론: p<0.05 → 귀무가설 기각. 통계적으로는 유의하지만 Cohen's d=-0.087로 효과크기는 미미함 — n이 커서 작은 차이도 유의하게 나온 것.

## Test B. IMPACT 등급에 따른 CADD_PHRED 차이
- H0: IMPACT 네 그룹(HIGH/MODERATE/LOW/MODIFIER) 간 CADD_PHRED 분포에 차이가 없다.

- 그룹별 n / 평균:
  - HIGH: n=4,011, mean=33.036
  - MODERATE: n=32,951, mean=19.566
  - LOW: n=21,604, mean=8.825
  - MODIFIER: n=5,530, mean=6.783
- Kruskal-Wallis: H=24407.3, p=0.00e+00
- eta-squared(근사) = 0.381 (큰 효과)
- 사후검정 (Mann-Whitney, Bonferroni 보정 α=0.0083):
  - HIGH vs MODERATE: p=0.00e+00 (유의)
  - HIGH vs LOW: p=0.00e+00 (유의)
  - HIGH vs MODIFIER: p=0.00e+00 (유의)
  - MODERATE vs LOW: p=0.00e+00 (유의)
  - MODERATE vs MODIFIER: p=0.00e+00 (유의)
  - LOW vs MODIFIER: p=1.18e-142 (유의)

## Test C. Consequence 유형에 따른 CADD_PHRED 차이 (상위 8개 유형)
- H0: Consequence 상위 8개 그룹 간 CADD_PHRED 분포에 차이가 없다.

- 그룹별 n / 평균:
  - missense_variant: n=31,353, mean=19.590
  - synonymous_variant: n=17,666, mean=8.903
  - intron_variant: n=4,361, mean=6.209
  - splice_region_variant&intron_variant: n=3,358, mean=8.175
  - stop_gained: n=1,691, mean=39.469
  - frameshift_variant: n=1,126, mean=31.149
  - missense_variant&splice_region_variant: n=964, mean=22.295
  - 5_prime_UTR_variant: n=620, mean=10.062
- Kruskal-Wallis: H=23187.8, p=0.00e+00
- eta-squared(근사) = 0.379 (큰 효과)