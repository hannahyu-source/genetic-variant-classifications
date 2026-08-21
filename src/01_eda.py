"""
ClinVar Conflicting Classifications - 탐색적 데이터 분석 (EDA)
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "raw" / "clinvar_conflicting.csv"
OUT_DIR = ROOT / "results" / "eda"
OUT_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR = ROOT / "docs"
DOCS_DIR.mkdir(exist_ok=True)

pd.set_option("display.max_columns", None)


def savefig(fig, name):
    fig.tight_layout()
    fig.savefig(OUT_DIR / name, dpi=150)
    plt.close(fig)


def main():
    df = pd.read_csv(DATA_PATH, low_memory=False)
    n_rows, n_cols = df.shape

    report_lines = []
    report_lines.append("# EDA Summary - ClinVar Conflicting Classifications\n")
    report_lines.append(f"- 전체 행 수: {n_rows:,}")
    report_lines.append(f"- 전체 컬럼 수: {n_cols}")

    # 1. 결측치 현황
    missing = df.isna().mean().sort_values(ascending=False) * 100
    missing.to_csv(OUT_DIR / "missing_ratio.csv", header=["missing_pct"])

    fig, ax = plt.subplots(figsize=(8, 12))
    missing[missing > 0].sort_values().plot(kind="barh", ax=ax, color="#C44E52")
    ax.set_xlabel("Missing %")
    ax.set_title("Missing Value Ratio by Column")
    savefig(fig, "01_missing_ratio.png")

    report_lines.append("\n## 결측치 상위 10개 컬럼")
    for col, pct in missing.head(10).items():
        report_lines.append(f"- {col}: {pct:.1f}%")

    # 2. 타겟(CLASS) 분포
    class_counts = df["CLASS"].value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(5, 4))
    class_counts.plot(kind="bar", ax=ax, color=["#4C72B0", "#DD8452"])
    ax.set_xticklabels(["0 (Not Conflicting)", "1 (Conflicting)"], rotation=0)
    ax.set_title("CLASS Distribution (Original Classification Target)")
    ax.set_ylabel("Count")
    savefig(fig, "02_class_distribution.png")

    report_lines.append("\n## CLASS 분포 (원본 분류 타겟)")
    report_lines.append(f"- 0 (비상충): {class_counts[0]:,} ({class_counts[0]/n_rows*100:.1f}%)")
    report_lines.append(f"- 1 (상충): {class_counts[1]:,} ({class_counts[1]/n_rows*100:.1f}%)")

    # 3. CADD_PHRED 분포 (회귀 타겟)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    df["CADD_PHRED"].dropna().plot(kind="hist", bins=50, ax=axes[0], color="#55A868")
    axes[0].set_title("CADD_PHRED Distribution")
    axes[0].set_xlabel("CADD_PHRED")
    df["CADD_PHRED"].dropna().plot(kind="box", ax=axes[1])
    axes[1].set_title("CADD_PHRED Boxplot")
    savefig(fig, "03_cadd_phred_distribution.png")

    report_lines.append("\n## CADD_PHRED 분포 (회귀 타겟 후보)")
    desc = df["CADD_PHRED"].describe()
    for stat in ["count", "mean", "std", "min", "25%", "50%", "75%", "max"]:
        report_lines.append(f"- {stat}: {desc[stat]:.3f}")
    report_lines.append(f"- 결측 비율: {df['CADD_PHRED'].isna().mean()*100:.2f}%")

    # 4. CLASS별 CADD_PHRED 비교 (상충 여부와 유해성 점수 관계)
    fig, ax = plt.subplots(figsize=(6, 4))
    df.boxplot(column="CADD_PHRED", by="CLASS", ax=ax)
    ax.set_title("CADD_PHRED by CLASS")
    ax.set_xlabel("CLASS (0=Not Conflicting, 1=Conflicting)")
    plt.suptitle("")
    savefig(fig, "04_cadd_by_class.png")

    # 5. IMPACT 분포 및 IMPACT별 CADD_PHRED
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    df["IMPACT"].value_counts().plot(kind="bar", ax=axes[0], color="#4C72B0")
    axes[0].set_title("IMPACT Count")
    axes[0].tick_params(axis="x", rotation=0)
    df.boxplot(column="CADD_PHRED", by="IMPACT", ax=axes[1])
    axes[1].set_title("CADD_PHRED by IMPACT")
    plt.suptitle("")
    savefig(fig, "05_impact.png")

    # 6. Consequence 상위 15개
    top_cons = df["Consequence"].value_counts().nlargest(15)
    fig, ax = plt.subplots(figsize=(8, 6))
    top_cons.sort_values().plot(kind="barh", ax=ax, color="#8172B2")
    ax.set_title("Top 15 Consequence Types")
    savefig(fig, "06_consequence_top15.png")

    # 7. 염색체(CHROM)별 변이 수
    chrom_order = [str(i) for i in range(1, 23)] + ["X", "Y", "MT"]
    chrom_counts = df["CHROM"].astype(str).value_counts()
    chrom_counts = chrom_counts.reindex([c for c in chrom_order if c in chrom_counts.index])
    fig, ax = plt.subplots(figsize=(10, 4))
    chrom_counts.plot(kind="bar", ax=ax, color="#64B5CD")
    ax.set_title("Variant Count by Chromosome")
    savefig(fig, "07_chrom_counts.png")

    # 8. 수치형 변수 상관관계
    numeric_cols = ["AF_ESP", "AF_EXAC", "AF_TGP", "ORIGIN", "LoFtool", "BLOSUM62",
                     "CADD_PHRED", "CADD_RAW", "CLASS"]
    corr = df[numeric_cols].corr()
    fig, ax = plt.subplots(figsize=(8, 7))
    im = ax.imshow(corr, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(numeric_cols)))
    ax.set_yticks(range(len(numeric_cols)))
    ax.set_xticklabels(numeric_cols, rotation=45, ha="right")
    ax.set_yticklabels(numeric_cols)
    for i in range(len(numeric_cols)):
        for j in range(len(numeric_cols)):
            ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im)
    ax.set_title("Numeric Feature Correlation")
    savefig(fig, "08_correlation_heatmap.png")

    report_lines.append("\n## CADD_PHRED와 수치형 변수 상관관계")
    cadd_corr = corr["CADD_PHRED"].drop("CADD_PHRED").sort_values(ascending=False)
    for col, val in cadd_corr.items():
        report_lines.append(f"- {col}: {val:.3f}")

    # 9. 대립유전자 빈도(AF) 분포 - 0이 매우 많은지 확인
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, col in zip(axes, ["AF_ESP", "AF_EXAC", "AF_TGP"]):
        df[df[col] > 0][col].plot(kind="hist", bins=50, ax=ax, color="#DD8452")
        ax.set_title(f"{col} (>0 only)")
        zero_pct = (df[col] == 0).mean() * 100
        ax.set_xlabel(f"zero ratio: {zero_pct:.1f}%")
    savefig(fig, "09_allele_frequency.png")

    # 10. SIFT / PolyPhen 카테고리 분포
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    df["SIFT"].value_counts().plot(kind="bar", ax=axes[0], color="#4C72B0")
    axes[0].set_title("SIFT Categories")
    axes[0].tick_params(axis="x", rotation=45)
    df["PolyPhen"].value_counts().plot(kind="bar", ax=axes[1], color="#55A868")
    axes[1].set_title("PolyPhen Categories")
    axes[1].tick_params(axis="x", rotation=45)
    savefig(fig, "10_sift_polyphen.png")

    # 11. 유전자(SYMBOL) 상위 20
    top_genes = df["SYMBOL"].value_counts().nlargest(20)
    fig, ax = plt.subplots(figsize=(8, 7))
    top_genes.sort_values().plot(kind="barh", ax=ax, color="#8172B2")
    ax.set_title("Top 20 Genes by Variant Count")
    savefig(fig, "11_top_genes.png")

    report_lines.append(f"\n## 기타 카디널리티")
    report_lines.append(f"- 고유 유전자(SYMBOL) 수: {df['SYMBOL'].nunique():,}")
    report_lines.append(f"- 고유 Consequence 종류: {df['Consequence'].nunique()}")
    report_lines.append(f"- 고유 염색체: {df['CHROM'].nunique()}")

    with open(DOCS_DIR / "eda_summary.md", "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    print("\n".join(report_lines))
    print(f"\n플롯 저장 위치: {OUT_DIR}")
    print(f"요약 문서: {DOCS_DIR / 'eda_summary.md'}")


if __name__ == "__main__":
    main()
