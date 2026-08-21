"""
튜닝된 XGBoost 모델을 SHAP으로 해석
- 전역 특성 중요도 (원본 변수 단위로 원-핫 컬럼 집계)
- Beeswarm summary plot (샘플링)
- 상위 변수 Dependence plot
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
import numpy as np
import pandas as pd
import shap
from scipy import sparse
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_improvement import DATA_PATH, RANDOM_STATE, ROOT, TARGET, build_feature_sets, build_preprocessor

OUT_DIR = ROOT / "outputs" / "shap"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# scripts/model_improvement.py Step 3 튜닝 결과 (outputs/model_improvement/results.json)
BEST_XGB_PARAMS = dict(
    subsample=1.0,
    reg_lambda=2,
    reg_alpha=0.1,
    n_estimators=600,
    min_child_weight=3,
    max_depth=7,
    learning_rate=0.05,
    colsample_bytree=0.6,
    random_state=RANDOM_STATE,
    n_jobs=1,
)

SAMPLE_SIZE = 2000  # beeswarm plot용 샘플 (렌더링 속도/가독성)
TOP_N = 20


def to_dense(x):
    return x.toarray() if sparse.issparse(x) else np.asarray(x)


def build_feature_groups(preprocessor, numeric_features, categorical_features):
    """인코딩된 각 컬럼이 어떤 원본 변수에서 나왔는지 매핑 (원-핫 집계용)."""
    groups = list(numeric_features)
    onehot = preprocessor.named_transformers_["cat"].named_steps["onehot"]
    for col, cats in zip(categorical_features, onehot.categories_):
        groups.extend([col] * len(cats))
    return groups


def main():
    df_raw = pd.read_csv(DATA_PATH, low_memory=False)
    df_raw = df_raw.dropna(subset=[TARGET]).copy()
    df, base_num, eng_num, categorical = build_feature_sets(df_raw)

    eng_cols = eng_num + categorical
    X = df[eng_cols]
    y = df[TARGET]

    idx_train, idx_test = train_test_split(df.index, test_size=0.2, random_state=RANDOM_STATE)
    X_train, X_test = X.loc[idx_train], X.loc[idx_test]
    y_train, y_test = y.loc[idx_train], y.loc[idx_test]

    preprocessor = build_preprocessor(eng_num, categorical, scale_numeric=False)
    Xt_train = to_dense(preprocessor.fit_transform(X_train))
    Xt_test = to_dense(preprocessor.transform(X_test))
    feature_names = preprocessor.get_feature_names_out()
    groups = build_feature_groups(preprocessor, eng_num, categorical)
    assert len(groups) == Xt_train.shape[1]

    print("XGBoost(tuned) 재학습 중...")
    model = XGBRegressor(**BEST_XGB_PARAMS)
    model.fit(Xt_train, y_train)

    print("SHAP 값 계산 중 (TreeExplainer, 전체 테스트셋)...")
    explainer = shap.TreeExplainer(model)
    shap_values = explainer(Xt_test)  # shap.Explanation, full test set

    # ---------- 1) 원본 변수 단위로 집계한 전역 중요도 ----------
    mean_abs_shap = np.abs(shap_values.values).mean(axis=0)
    imp_df = pd.DataFrame({"feature": feature_names, "group": groups, "mean_abs_shap": mean_abs_shap})
    grouped_imp = imp_df.groupby("group")["mean_abs_shap"].sum().sort_values(ascending=False)
    grouped_imp.to_csv(OUT_DIR / "feature_importance_by_variable.csv", header=["mean_abs_shap"])

    fig, ax = plt.subplots(figsize=(8, 8))
    grouped_imp.head(TOP_N).sort_values().plot(kind="barh", ax=ax, color="#4C72B0")
    ax.set_xlabel("mean(|SHAP value|)  (원-핫 컬럼 합산)")
    ax.set_title(f"XGBoost(tuned) - 변수 단위 SHAP 중요도 Top {TOP_N}")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "01_importance_by_variable.png", dpi=150)
    plt.close(fig)

    # ---------- 2) 원-핫 컬럼 단위 상위 20개 (beeswarm) ----------
    rng = np.random.RandomState(RANDOM_STATE)
    sample_idx = rng.choice(Xt_test.shape[0], size=min(SAMPLE_SIZE, Xt_test.shape[0]), replace=False)
    shap_sample = shap_values[sample_idx]

    plt.figure(figsize=(9, 8))
    shap.summary_plot(shap_sample, feature_names=feature_names, max_display=TOP_N, show=False)
    plt.title(f"XGBoost(tuned) - SHAP Summary (n={len(sample_idx)} sample)")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "02_beeswarm_summary.png", dpi=150)
    plt.close()

    # ---------- 3) 컬럼 단위 bar plot ----------
    plt.figure(figsize=(8, 8))
    shap.summary_plot(shap_sample, feature_names=feature_names, plot_type="bar", max_display=TOP_N, show=False)
    plt.title(f"XGBoost(tuned) - mean(|SHAP|) by encoded column Top {TOP_N}")
    plt.tight_layout()
    plt.savefig(OUT_DIR / "03_bar_by_column.png", dpi=150)
    plt.close()

    # ---------- 4) 상위 원본 변수 dependence plot ----------
    top_vars = grouped_imp.head(6).index.tolist()
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))
    for ax, var in zip(axes.flat, top_vars):
        # 해당 변수에 속하는 인코딩 컬럼 중 SHAP 절대값 평균이 가장 큰 컬럼 하나를 대표로 표시
        var_cols = [i for i, g in enumerate(groups) if g == var]
        best_col = max(var_cols, key=lambda i: mean_abs_shap[i])
        shap.dependence_plot(
            best_col, shap_values.values[sample_idx], Xt_test[sample_idx],
            feature_names=feature_names, ax=ax, show=False, interaction_index=None,
        )
        ax.set_title(f"{var}  ({feature_names[best_col]})")
    fig.suptitle("Top 6 변수 - SHAP Dependence Plot")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "04_dependence_top6.png", dpi=150)
    plt.close(fig)

    print("\n=== 변수 단위 SHAP 중요도 Top 15 ===")
    print(grouped_imp.head(15))
    print(f"\n결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
