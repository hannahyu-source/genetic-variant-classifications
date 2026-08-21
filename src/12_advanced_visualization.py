"""
심화 시각화 5종
1. 회귀 잔차 플롯 (Residual Plot)
2. PCA / t-SNE 2D 임베딩
3. 분류기 보정 곡선 (Calibration Curve)
4. 유전자 x IMPACT 히트맵
5. 2D Partial Dependence (변수 간 상호작용)
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
from sklearn.calibration import calibration_curve
from sklearn.decomposition import PCA
from sklearn.inspection import PartialDependenceDisplay
from sklearn.manifold import TSNE
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier, XGBRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PATH, RANDOM_STATE, ROOT, TARGET, build_feature_sets, build_preprocessor

# 각 플롯은 다루는 연구 질문에 따라 서로 다른 results/ 하위 폴더에 저장한다.
OUT_DIR_REGRESSION = ROOT / "results" / "regression"
OUT_DIR_EXPLAIN = ROOT / "results" / "explainability"
OUT_DIR_CLASSIFICATION = ROOT / "results" / "classification"
OUT_DIR_BIO = ROOT / "results" / "biological_insights"
for _d in (OUT_DIR_REGRESSION, OUT_DIR_EXPLAIN, OUT_DIR_CLASSIFICATION, OUT_DIR_BIO):
    _d.mkdir(parents=True, exist_ok=True)

# results/regression/model_improvement/results.json 의 XGBoost 튜닝 최적 파라미터
BEST_XGB_REG_PARAMS = dict(
    subsample=1.0, reg_lambda=2, reg_alpha=0.1, n_estimators=600,
    min_child_weight=3, max_depth=7, learning_rate=0.05, colsample_bytree=0.6,
    random_state=RANDOM_STATE, n_jobs=1,
)
# classify_conflicting.py와 동일한 XGBoost 분류기 설정
XGB_CLF_PARAMS = dict(
    n_estimators=400, max_depth=6, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    eval_metric="logloss", random_state=RANDOM_STATE, n_jobs=1,
)


def main():
    df_raw = pd.read_csv(DATA_PATH, low_memory=False)
    df_full, base_num, eng_num, categorical = build_feature_sets(df_raw)

    # ===== 공통: 회귀용 데이터 (CADD_PHRED 결측 제거) =====
    df_reg = df_full.dropna(subset=[TARGET]).copy()
    reg_cols = eng_num + categorical
    idx_train, idx_test = train_test_split(df_reg.index, test_size=0.2, random_state=RANDOM_STATE)
    Xr_train, Xr_test = df_reg.loc[idx_train, reg_cols], df_reg.loc[idx_test, reg_cols]
    yr_train, yr_test = df_reg.loc[idx_train, TARGET], df_reg.loc[idx_test, TARGET]

    print("튜닝된 XGBoost 회귀 파이프라인 재학습...")
    pre_reg = build_preprocessor(eng_num, categorical, scale_numeric=False)
    pipe_reg = Pipeline([("preprocess", pre_reg), ("model", XGBRegressor(**BEST_XGB_REG_PARAMS))])
    pipe_reg.fit(Xr_train, yr_train)
    preds_reg = pipe_reg.predict(Xr_test)

    # ===== 1. 잔차 플롯 =====
    print("[1/5] 잔차 플롯...")
    residuals = yr_test.values - preds_reg
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    axes[0].scatter(yr_test, preds_reg, alpha=0.12, s=8, color="#4C72B0")
    lims = [0, max(yr_test.max(), preds_reg.max())]
    axes[0].plot(lims, lims, "k--", alpha=0.6, label="y = x (완벽 예측)")
    axes[0].set_xlabel("실제 CADD_PHRED")
    axes[0].set_ylabel("예측 CADD_PHRED")
    axes[0].set_title("예측값 vs 실제값")
    axes[0].legend()

    axes[1].scatter(preds_reg, residuals, alpha=0.12, s=8, color="#C44E52")
    axes[1].axhline(0, color="k", linestyle="--", alpha=0.6)
    axes[1].set_xlabel("예측 CADD_PHRED")
    axes[1].set_ylabel("잔차 (실제 - 예측)")
    axes[1].set_title("잔차 플롯")

    fig.suptitle("회귀 진단: 튜닝된 XGBoost (R²=0.708)")
    fig.tight_layout()
    fig.savefig(OUT_DIR_REGRESSION / "01_residual_plot.png", dpi=150)
    plt.close(fig)

    # ===== 2. PCA / t-SNE 2D 임베딩 =====
    # PCA/t-SNE는 거리 기반이라 스케일이 큰 변수(위치 정보 등)가 지배하지 않도록
    # 반드시 표준화된 preprocessor를 별도로 사용한다 (트리 모델용 pre_reg는 스케일링 없음).
    print("[2/5] PCA/t-SNE 임베딩...")
    pre_embed = build_preprocessor(eng_num, categorical, scale_numeric=True)
    pre_embed.fit(Xr_train)
    Xt_test = pre_embed.transform(Xr_test)
    if hasattr(Xt_test, "toarray"):
        Xt_test = Xt_test.toarray()

    impact_test = df_reg.loc[idx_test, "IMPACT"].values
    class_test = df_reg.loc[idx_test, "CLASS"].values

    pca = PCA(n_components=2, random_state=RANDOM_STATE)
    pca_coords = pca.fit_transform(Xt_test)

    rng = np.random.RandomState(RANDOM_STATE)
    sample_n = min(4000, Xt_test.shape[0])
    sample_idx = rng.choice(Xt_test.shape[0], size=sample_n, replace=False)
    tsne = TSNE(n_components=2, perplexity=30, random_state=RANDOM_STATE, init="pca")
    tsne_coords = tsne.fit_transform(Xt_test[sample_idx])

    fig, axes = plt.subplots(2, 2, figsize=(13, 12))
    impact_order = ["HIGH", "MODERATE", "LOW", "MODIFIER"]
    impact_colors = {"HIGH": "#C44E52", "MODERATE": "#DD8452", "LOW": "#55A868", "MODIFIER": "#4C72B0"}
    class_colors = {0: "#4C72B0", 1: "#C44E52"}

    for imp in impact_order:
        mask = impact_test == imp
        axes[0, 0].scatter(pca_coords[mask, 0], pca_coords[mask, 1], s=6, alpha=0.35, color=impact_colors[imp], label=imp)
    axes[0, 0].set_title(f"PCA (설명분산 {pca.explained_variance_ratio_.sum()*100:.1f}%) - IMPACT")
    axes[0, 0].legend(markerscale=3)

    for c in [0, 1]:
        mask = class_test == c
        axes[0, 1].scatter(pca_coords[mask, 0], pca_coords[mask, 1], s=6, alpha=0.35, color=class_colors[c],
                            label=f"CLASS={c}")
    axes[0, 1].set_title("PCA - CLASS")
    axes[0, 1].legend(markerscale=3)

    impact_sample = impact_test[sample_idx]
    class_sample = class_test[sample_idx]
    for imp in impact_order:
        mask = impact_sample == imp
        axes[1, 0].scatter(tsne_coords[mask, 0], tsne_coords[mask, 1], s=6, alpha=0.35, color=impact_colors[imp], label=imp)
    axes[1, 0].set_title(f"t-SNE (n={sample_n} 샘플) - IMPACT")
    axes[1, 0].legend(markerscale=3)

    for c in [0, 1]:
        mask = class_sample == c
        axes[1, 1].scatter(tsne_coords[mask, 0], tsne_coords[mask, 1], s=6, alpha=0.35, color=class_colors[c],
                            label=f"CLASS={c}")
    axes[1, 1].set_title(f"t-SNE (n={sample_n} 샘플) - CLASS")
    axes[1, 1].legend(markerscale=3)

    fig.suptitle("특성 공간 2D 임베딩")
    fig.tight_layout()
    fig.savefig(OUT_DIR_EXPLAIN / "02_pca_tsne_embedding.png", dpi=150)
    plt.close(fig)

    # ===== 3. 분류기 보정 곡선 =====
    print("[3/5] 분류기 보정 곡선...")
    numeric_clf = eng_num + ["CADD_PHRED"]
    X_clf = df_full[numeric_clf + categorical]
    y_clf = df_full["CLASS"]
    Xc_train, Xc_test, yc_train, yc_test = train_test_split(
        X_clf, y_clf, test_size=0.2, random_state=RANDOM_STATE, stratify=y_clf
    )
    neg, pos = (yc_train == 0).sum(), (yc_train == 1).sum()
    pre_clf = build_preprocessor(numeric_clf, categorical, scale_numeric=False)
    pipe_clf = Pipeline([
        ("preprocess", pre_clf),
        ("model", XGBClassifier(scale_pos_weight=neg / pos, **XGB_CLF_PARAMS)),
    ])
    pipe_clf.fit(Xc_train, yc_train)
    proba = pipe_clf.predict_proba(Xc_test)[:, 1]

    prob_true, prob_pred = calibration_curve(yc_test, proba, n_bins=10, strategy="quantile")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    axes[0].plot(prob_pred, prob_true, marker="o", color="#4C72B0", label="XGBoost")
    axes[0].plot([0, 1], [0, 1], "k--", alpha=0.6, label="완벽 보정")
    axes[0].set_xlabel("예측 확률 (평균)")
    axes[0].set_ylabel("실제 관측 비율")
    axes[0].set_title("보정 곡선 (Reliability Diagram)")
    axes[0].legend()

    axes[1].hist(proba, bins=30, color="#8172B2", alpha=0.8)
    axes[1].set_xlabel("예측 확률 (CLASS=1)")
    axes[1].set_ylabel("빈도")
    axes[1].set_title("예측 확률 분포")

    fig.suptitle("분류기 확률 보정 상태")
    fig.tight_layout()
    fig.savefig(OUT_DIR_CLASSIFICATION / "03_calibration_curve.png", dpi=150)
    plt.close(fig)

    # ===== 4. 유전자 x IMPACT 히트맵 =====
    print("[4/5] 유전자 x IMPACT 히트맵...")
    top_genes = df_full["SYMBOL"].value_counts().nlargest(12).index.tolist()
    sub = df_full[df_full["SYMBOL"].isin(top_genes)]

    pivot_cadd = sub.pivot_table(index="SYMBOL", columns="IMPACT", values="CADD_PHRED", aggfunc="mean")
    pivot_conflict = sub.pivot_table(index="SYMBOL", columns="IMPACT", values="CLASS", aggfunc="mean")
    impact_cols = [c for c in impact_order if c in pivot_cadd.columns]
    pivot_cadd = pivot_cadd.reindex(index=top_genes, columns=impact_cols)
    pivot_conflict = pivot_conflict.reindex(index=top_genes, columns=impact_cols)

    fig, axes = plt.subplots(1, 2, figsize=(11, 7))
    for ax, pivot, title, cmap, fmt in [
        (axes[0], pivot_cadd, "평균 CADD_PHRED", "YlOrRd", "{:.1f}"),
        (axes[1], pivot_conflict, "상충(CLASS=1) 비율", "PuBu", "{:.2f}"),
    ]:
        im = ax.imshow(pivot.values, cmap=cmap, aspect="auto")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        for i in range(pivot.shape[0]):
            for j in range(pivot.shape[1]):
                v = pivot.values[i, j]
                if not np.isnan(v):
                    ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=8)
        ax.set_title(title)
        fig.colorbar(im, ax=ax, fraction=0.046)

    fig.suptitle(f"상위 {len(top_genes)}개 유전자 x IMPACT")
    fig.tight_layout()
    fig.savefig(OUT_DIR_BIO / "04_gene_impact_heatmap.png", dpi=150)
    plt.close(fig)

    # ===== 5. 2D Partial Dependence (상호작용) =====
    # sklearn의 PDP 그리드는 np.percentile(NaN 무시 안 함)을 사용해 결측치가 있으면
    # 그리드 범위가 깨진다 (BLOSUM62는 결측 60%). 파이프라인이 내부적으로 median으로
    # 대체하는 것과 동일하게 미리 결측을 채워서 전달한다.
    print("[5/5] 2D Partial Dependence (BLOSUM62 x log_AF_TGP)...")
    pdp_sample = Xr_train.sample(n=min(3000, len(Xr_train)), random_state=RANDOM_STATE).copy()
    pdp_sample["BLOSUM62"] = pdp_sample["BLOSUM62"].fillna(Xr_train["BLOSUM62"].median())
    fig, ax = plt.subplots(figsize=(7, 6))
    PartialDependenceDisplay.from_estimator(
        pipe_reg, pdp_sample, features=[("BLOSUM62", "log_AF_TGP")],
        grid_resolution=15, ax=ax,
    )
    ax.set_title("2D Partial Dependence: BLOSUM62 x log_AF_TGP -> CADD_PHRED 예측")
    fig.tight_layout()
    fig.savefig(OUT_DIR_EXPLAIN / "05_pdp_interaction.png", dpi=150)
    plt.close(fig)

    print(f"\n결과 저장 위치: {OUT_DIR_REGRESSION}, {OUT_DIR_EXPLAIN}, {OUT_DIR_CLASSIFICATION}, {OUT_DIR_BIO}")


if __name__ == "__main__":
    main()
