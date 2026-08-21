"""
잔차 플롯 이상 패턴 원인 규명
10-1절에서 발견: 실제 CADD_PHRED 23~36 구간에 세로로 밀집된 띠가 있고,
이 구간에서 예측값이 0~40까지 크게 흩어짐. 원인을 진단한다.
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_improvement import DATA_PATH, RANDOM_STATE, ROOT, TARGET, build_feature_sets, build_preprocessor

OUT_DIR = ROOT / "outputs" / "residual_investigation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BEST_XGB_PARAMS = dict(
    subsample=1.0, reg_lambda=2, reg_alpha=0.1, n_estimators=600,
    min_child_weight=3, max_depth=7, learning_rate=0.05, colsample_bytree=0.6,
    random_state=RANDOM_STATE, n_jobs=1,
)

BAND_LOW, BAND_HIGH = 23, 36


def main():
    df_raw = pd.read_csv(DATA_PATH, low_memory=False)
    df_raw = df_raw.dropna(subset=[TARGET]).copy()
    df, base_num, eng_num, categorical = build_feature_sets(df_raw)

    cols = eng_num + categorical
    idx_train, idx_test = train_test_split(df.index, test_size=0.2, random_state=RANDOM_STATE)
    X_train, X_test = df.loc[idx_train, cols], df.loc[idx_test, cols]
    y_train, y_test = df.loc[idx_train, TARGET], df.loc[idx_test, TARGET]

    print("튜닝된 XGBoost 재학습...")
    pre = build_preprocessor(eng_num, categorical, scale_numeric=False)
    pipe = Pipeline([("preprocess", pre), ("model", XGBRegressor(**BEST_XGB_PARAMS))])
    pipe.fit(X_train, y_train)
    preds = pipe.predict(X_test)

    test_df = df.loc[idx_test].copy()
    test_df["pred"] = preds
    test_df["residual"] = test_df[TARGET] - test_df["pred"]

    # ===== 1. 실제 CADD_PHRED 23~36 구간이 정말로 밀도가 높은지 확인 =====
    print(f"\n[1] 실제 CADD_PHRED 값 분포 (density 확인, 전체 데이터 기준)")
    full_counts = df[TARGET].value_counts()
    band_vals = full_counts[(full_counts.index >= BAND_LOW) & (full_counts.index <= BAND_HIGH)]
    print(f"  {BAND_LOW}~{BAND_HIGH} 구간 고유값 수: {len(band_vals)}, 상위 10개 최빈값:")
    print(band_vals.sort_values(ascending=False).head(10))
    print(f"  전체 데이터 중 {BAND_LOW}~{BAND_HIGH} 구간 비율: "
          f"{((df[TARGET] >= BAND_LOW) & (df[TARGET] <= BAND_HIGH)).mean()*100:.1f}%")

    # ===== 2. 밴드 내 잔차가 큰 이유: Consequence/IMPACT 구성 확인 =====
    band_mask = (test_df[TARGET] >= BAND_LOW) & (test_df[TARGET] <= BAND_HIGH)
    band = test_df[band_mask]
    print(f"\n[2] 밴드({BAND_LOW}~{BAND_HIGH}) 내 test 샘플 수: {len(band):,}")
    print(f"  밴드 내 잔차 표준편차: {band['residual'].std():.3f} (전체 test 잔차 표준편차: {test_df['residual'].std():.3f})")

    print("\n  밴드 내 Consequence 상위 8개 및 예측값 평균:")
    cons_group = band.groupby("Consequence").agg(n=("pred", "size"), pred_mean=("pred", "mean"),
                                                    actual_mean=(TARGET, "mean"))
    cons_group = cons_group.sort_values("n", ascending=False).head(8)
    print(cons_group)

    print("\n  밴드 내 IMPACT별 예측값 평균:")
    impact_group = band.groupby("IMPACT").agg(n=("pred", "size"), pred_mean=("pred", "mean"),
                                                 actual_mean=(TARGET, "mean"))
    print(impact_group.sort_values("n", ascending=False))

    # ===== 3. 시각화: 밴드 내 예측값을 Consequence로 색칠 =====
    top_cons_band = band["Consequence"].value_counts().nlargest(6).index.tolist()
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    colors = plt.cm.tab10(np.linspace(0, 1, len(top_cons_band)))
    for c, color in zip(top_cons_band, colors):
        sub = band[band["Consequence"] == c]
        axes[0].scatter(sub[TARGET], sub["pred"], s=10, alpha=0.5, color=color, label=c[:25])
    axes[0].plot([BAND_LOW, BAND_HIGH], [BAND_LOW, BAND_HIGH], "k--", alpha=0.5)
    axes[0].set_xlabel("실제 CADD_PHRED")
    axes[0].set_ylabel("예측 CADD_PHRED")
    axes[0].set_title(f"밴드({BAND_LOW}~{BAND_HIGH}) 내 예측값 - Consequence별 색칠")
    axes[0].legend(fontsize=7, loc="upper left")

    impact_colors = {"HIGH": "#C44E52", "MODERATE": "#DD8452", "LOW": "#55A868", "MODIFIER": "#4C72B0"}
    for imp, color in impact_colors.items():
        sub = band[band["IMPACT"] == imp]
        if len(sub):
            axes[1].scatter(sub[TARGET], sub["pred"], s=10, alpha=0.5, color=color, label=imp)
    axes[1].plot([BAND_LOW, BAND_HIGH], [BAND_LOW, BAND_HIGH], "k--", alpha=0.5)
    axes[1].set_xlabel("실제 CADD_PHRED")
    axes[1].set_ylabel("예측 CADD_PHRED")
    axes[1].set_title(f"밴드({BAND_LOW}~{BAND_HIGH}) 내 예측값 - IMPACT별 색칠")
    axes[1].legend(fontsize=8)

    fig.suptitle("잔차 이상 패턴 진단: 밴드 내부 구성")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "band_breakdown.png", dpi=150)
    plt.close(fig)

    # ===== 4. 밴드 내에서 잔차가 가장 큰 상위 사례 확인 =====
    band_sorted = band.reindex(band["residual"].abs().sort_values(ascending=False).index)
    top_err_cols = ["CHROM", "POS", "SYMBOL", "Consequence", "IMPACT", "SIFT", "PolyPhen",
                     "BLOSUM62", TARGET, "pred", "residual"]
    print("\n[3] 밴드 내 잔차 절대값 상위 15개 사례:")
    print(band_sorted[top_err_cols].head(15).to_string(index=False))

    band_sorted[top_err_cols].head(50).to_csv(OUT_DIR / "band_top_errors.csv", index=False)

    print(f"\n결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
