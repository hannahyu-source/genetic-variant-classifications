"""
Ablation: SIFT/PolyPhen 제외 시 튜닝된 XGBoost(CADD_PHRED 회귀) 성능 변화 확인
SHAP 해석에서 SIFT/PolyPhen이 CADD와 유사한 개념(단백질 기능 손상)을 측정하는
도구라 정보 중복 가능성이 제기되어, 이 둘을 뺐을 때 "독립적인" 설명력이
얼마나 남는지 정량화한다.
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
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from model_improvement import DATA_PATH, RANDOM_STATE, ROOT, TARGET, build_feature_sets, build_preprocessor

OUT_DIR = ROOT / "outputs" / "ablation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# outputs/model_improvement/results.json 의 XGBoost 튜닝 최적 파라미터
BEST_XGB_PARAMS = dict(
    subsample=1.0, reg_lambda=2, reg_alpha=0.1, n_estimators=600,
    min_child_weight=3, max_depth=7, learning_rate=0.05, colsample_bytree=0.6,
    random_state=RANDOM_STATE, n_jobs=1,
)

DROP_FEATURES = ["SIFT", "PolyPhen"]


def evaluate(y_true, y_pred):
    return {
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "R2": float(r2_score(y_true, y_pred)),
    }


def main():
    df_raw = pd.read_csv(DATA_PATH, low_memory=False)
    df_raw = df_raw.dropna(subset=[TARGET]).copy()
    df, base_num, eng_num, categorical = build_feature_sets(df_raw)

    full_categorical = categorical
    reduced_categorical = [c for c in categorical if c not in DROP_FEATURES]

    idx_train, idx_test = train_test_split(df.index, test_size=0.2, random_state=RANDOM_STATE)
    y_train, y_test = df[TARGET].loc[idx_train], df[TARGET].loc[idx_test]

    results = {}
    for label, cat_cols in [("full (SIFT+PolyPhen 포함)", full_categorical),
                             ("ablation (SIFT+PolyPhen 제외)", reduced_categorical)]:
        cols = eng_num + cat_cols
        X_train, X_test = df[cols].loc[idx_train], df[cols].loc[idx_test]

        pre = build_preprocessor(eng_num, cat_cols, scale_numeric=False)
        model = XGBRegressor(**BEST_XGB_PARAMS)
        pipe = Pipeline([("preprocess", pre), ("model", model)])
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)

        results[label] = evaluate(y_test, preds)
        r = results[label]
        print(f"[{label}] RMSE={r['RMSE']:.3f}  MAE={r['MAE']:.3f}  R2={r['R2']:.3f}")

    results_df = pd.DataFrame(results).T[["RMSE", "MAE", "R2"]]
    results_df.to_csv(OUT_DIR / "ablation_comparison.csv")

    full_r2 = results_df.loc["full (SIFT+PolyPhen 포함)", "R2"]
    ablation_r2 = results_df.loc["ablation (SIFT+PolyPhen 제외)", "R2"]
    drop_pct = (full_r2 - ablation_r2) / full_r2 * 100
    print(f"\nR2 하락: {full_r2:.3f} -> {ablation_r2:.3f}  ({drop_pct:.1f}% 감소)")

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    colors = ["#4C72B0", "#C44E52"]
    for ax, metric in zip(axes, ["RMSE", "MAE", "R2"]):
        results_df[metric].plot(kind="bar", ax=ax, color=colors)
        ax.set_title(metric)
        ax.set_xticklabels(["Full", "SIFT/PolyPhen\n제외"], rotation=0)
    fig.suptitle("Ablation: SIFT/PolyPhen 제외 시 튜닝된 XGBoost 성능 변화")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "ablation_comparison.png", dpi=150)
    plt.close(fig)

    print(f"\n결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
