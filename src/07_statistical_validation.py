"""
통계적 가설검정: CADD_PHRED가 CLASS / IMPACT / Consequence 그룹에 따라
유의미하게 다른지 검정한다. 표본 크기가 커서(n~6만) p-value만으로는
"통계적으로 유의미"와 "실질적으로 의미있음"을 구분하기 어려우므로,
효과크기(Cohen's d, eta-squared)를 함께 계산해 실질적 크기를 판단한다.
"""
import sys
from itertools import combinations
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PATH, ROOT, TARGET

OUT_DIR = ROOT / "results" / "statistical_validation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ALPHA = 0.05


def cohens_d(a, b):
    na, nb = len(a), len(b)
    pooled_std = np.sqrt(((na - 1) * a.std(ddof=1) ** 2 + (nb - 1) * b.std(ddof=1) ** 2) / (na + nb - 2))
    return (a.mean() - b.mean()) / pooled_std


def eta_squared_kruskal(h_stat, n, k):
    """Kruskal-Wallis H를 이용한 근사 eta-squared (epsilon-squared)."""
    return (h_stat - k + 1) / (n - k)


def main():
    df = pd.read_csv(DATA_PATH, low_memory=False)
    df = df.dropna(subset=[TARGET]).copy()

    log_lines = ["# 통계적 가설검정 결과\n"]

    # ================= Test A: CLASS (상충 여부) =================
    log_lines.append("## Test A. CLASS(상충 여부)에 따른 CADD_PHRED 차이")
    log_lines.append("- H0: 상충(CLASS=1) 변이와 비상충(CLASS=0) 변이의 CADD_PHRED 평균/분포에 차이가 없다.\n")

    g0 = df.loc[df["CLASS"] == 0, TARGET]
    g1 = df.loc[df["CLASS"] == 1, TARGET]

    t_stat, t_p = stats.ttest_ind(g1, g0, equal_var=False)  # Welch's t-test
    u_stat, u_p = stats.mannwhitneyu(g1, g0, alternative="two-sided")
    d = cohens_d(g1, g0)

    log_lines.append(f"- 그룹 크기: CLASS=0 (n={len(g0):,}, mean={g0.mean():.3f}), CLASS=1 (n={len(g1):,}, mean={g1.mean():.3f})")
    log_lines.append(f"- Welch's t-test: t={t_stat:.3f}, p={t_p:.2e}")
    log_lines.append(f"- Mann-Whitney U: U={u_stat:.0f}, p={u_p:.2e}")
    log_lines.append(f"- Cohen's d = {d:.3f} ({'무시할 수준' if abs(d) < 0.2 else '작음' if abs(d) < 0.5 else '중간' if abs(d) < 0.8 else '큼'})")
    log_lines.append(f"- 결론: p{'<' if t_p < ALPHA else '>='}{ALPHA} → 귀무가설 {'기각' if t_p < ALPHA else '기각 못함'}. "
                      f"통계적으로는 {'유의' if t_p < ALPHA else '비유의'}하지만 Cohen's d={d:.3f}로 효과크기는 "
                      f"{'미미함 — n이 커서 작은 차이도 유의하게 나온 것' if abs(d) < 0.2 else '존재함'}.\n")

    # ================= Test B: IMPACT =================
    log_lines.append("## Test B. IMPACT 등급에 따른 CADD_PHRED 차이")
    log_lines.append("- H0: IMPACT 네 그룹(HIGH/MODERATE/LOW/MODIFIER) 간 CADD_PHRED 분포에 차이가 없다.\n")

    impact_groups = {name: g[TARGET].values for name, g in df.groupby("IMPACT")}
    order = ["HIGH", "MODERATE", "LOW", "MODIFIER"]
    order = [o for o in order if o in impact_groups]
    h_stat, h_p = stats.kruskal(*[impact_groups[o] for o in order])
    eta2 = eta_squared_kruskal(h_stat, len(df), len(order))

    log_lines.append("- 그룹별 n / 평균:")
    for o in order:
        log_lines.append(f"  - {o}: n={len(impact_groups[o]):,}, mean={impact_groups[o].mean():.3f}")
    log_lines.append(f"- Kruskal-Wallis: H={h_stat:.1f}, p={h_p:.2e}")
    log_lines.append(f"- eta-squared(근사) = {eta2:.3f} ({'큰 효과' if eta2 > 0.14 else '중간 효과' if eta2 > 0.06 else '작은 효과'})")

    # 사후검정: 쌍별 Mann-Whitney + Bonferroni 보정
    pairs = list(combinations(order, 2))
    bonferroni_alpha = ALPHA / len(pairs)
    log_lines.append(f"- 사후검정 (Mann-Whitney, Bonferroni 보정 α={bonferroni_alpha:.4f}):")
    for a, b in pairs:
        _, p = stats.mannwhitneyu(impact_groups[a], impact_groups[b], alternative="two-sided")
        sig = "유의" if p < bonferroni_alpha else "비유의"
        log_lines.append(f"  - {a} vs {b}: p={p:.2e} ({sig})")
    log_lines.append("")

    # ================= Test C: Consequence (상위 8개) =================
    log_lines.append("## Test C. Consequence 유형에 따른 CADD_PHRED 차이 (상위 8개 유형)")
    log_lines.append("- H0: Consequence 상위 8개 그룹 간 CADD_PHRED 분포에 차이가 없다.\n")

    top8 = df["Consequence"].value_counts().nlargest(8).index.tolist()
    cons_groups = {c: df.loc[df["Consequence"] == c, TARGET].values for c in top8}
    h_stat2, h_p2 = stats.kruskal(*[cons_groups[c] for c in top8])
    eta2_c = eta_squared_kruskal(h_stat2, sum(len(v) for v in cons_groups.values()), len(top8))

    log_lines.append("- 그룹별 n / 평균:")
    for c in top8:
        log_lines.append(f"  - {c}: n={len(cons_groups[c]):,}, mean={cons_groups[c].mean():.3f}")
    log_lines.append(f"- Kruskal-Wallis: H={h_stat2:.1f}, p={h_p2:.2e}")
    log_lines.append(f"- eta-squared(근사) = {eta2_c:.3f} ({'큰 효과' if eta2_c > 0.14 else '중간 효과' if eta2_c > 0.06 else '작은 효과'})")

    # ---------- 저장 ----------
    with open(OUT_DIR / "statistical_tests.md", "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

    # ---------- 시각화 ----------
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    axes[0].boxplot([g0, g1], tick_labels=["CLASS=0\n(비상충)", "CLASS=1\n(상충)"], showfliers=False)
    axes[0].set_title(f"CLASS별 CADD_PHRED\n(Cohen's d={d:.3f})")
    axes[0].set_ylabel("CADD_PHRED")

    axes[1].boxplot([impact_groups[o] for o in order], tick_labels=order, showfliers=False)
    axes[1].set_title(f"IMPACT별 CADD_PHRED\n(eta²={eta2:.3f})")

    axes[2].boxplot([cons_groups[c] for c in top8], tick_labels=[c[:12] for c in top8], showfliers=False)
    axes[2].set_title(f"Consequence별 CADD_PHRED (상위8)\n(eta²={eta2_c:.3f})")
    axes[2].tick_params(axis="x", rotation=60)

    fig.tight_layout()
    fig.savefig(OUT_DIR / "group_comparison_boxplots.png", dpi=150)
    plt.close(fig)

    print("\n".join(log_lines))
    print(f"\n결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
