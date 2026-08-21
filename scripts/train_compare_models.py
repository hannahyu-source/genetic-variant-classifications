"""
ClinVar Conflicting Classifications - CADD_PHRED 회귀 예측 파이프라인
타겟: CADD_PHRED (변이 유해성 점수, 연속형)
모델: LinearRegression / RandomForestRegressor / XGBRegressor
평가: RMSE, MAE, R2
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "clinvar_conflicting.csv"
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

RANDOM_STATE = 42

TARGET = "CADD_PHRED"

NUMERIC_FEATURES = ["AF_ESP", "AF_EXAC", "AF_TGP", "ORIGIN", "STRAND", "LoFtool", "BLOSUM62"]
CATEGORICAL_FEATURES = ["CHROM", "IMPACT", "Consequence", "BIOTYPE", "CLNVC", "SIFT", "PolyPhen"]
GENE_COL = "SYMBOL"
TOP_N_GENES = 30  # 상위 N개 유전자만 개별 카테고리로, 나머지는 'Other'


def load_and_prepare():
    df = pd.read_csv(DATA_PATH, low_memory=False)

    # 타겟 결측 제거
    df = df.dropna(subset=[TARGET]).copy()

    # 유전자 고빈도 상위 N개만 유지, 나머지는 'Other'
    top_genes = df[GENE_COL].value_counts().nlargest(TOP_N_GENES).index
    df["GENE_GROUP"] = df[GENE_COL].where(df[GENE_COL].isin(top_genes), "Other")

    cat_features = CATEGORICAL_FEATURES + ["GENE_GROUP"]
    feature_cols = NUMERIC_FEATURES + cat_features

    X = df[feature_cols].copy()
    y = df[TARGET].copy()

    return X, y, NUMERIC_FEATURES, cat_features


def build_preprocessor(numeric_features, categorical_features, scale_numeric: bool):
    numeric_steps = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))
    numeric_pipe = Pipeline(numeric_steps)

    categorical_pipe = Pipeline([
        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])

    return ColumnTransformer([
        ("num", numeric_pipe, numeric_features),
        ("cat", categorical_pipe, categorical_features),
    ])


def evaluate(y_true, y_pred):
    rmse = np.sqrt(mean_squared_error(y_true, y_pred))
    mae = mean_absolute_error(y_true, y_pred)
    r2 = r2_score(y_true, y_pred)
    return {"RMSE": rmse, "MAE": mae, "R2": r2}


def main():
    X, y, numeric_features, categorical_features = load_and_prepare()

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE
    )

    models = {
        "LinearRegression": (LinearRegression(), True),
        "RandomForest": (
            RandomForestRegressor(
                n_estimators=300, max_depth=None, n_jobs=-1, random_state=RANDOM_STATE
            ),
            False,
        ),
        "XGBoost": (
            XGBRegressor(
                n_estimators=400,
                max_depth=6,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            ),
            False,
        ),
    }

    results = {}
    fitted_pipelines = {}
    for name, (estimator, scale_numeric) in models.items():
        preprocessor = build_preprocessor(numeric_features, categorical_features, scale_numeric)
        pipe = Pipeline([("preprocess", preprocessor), ("model", estimator)])
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)
        results[name] = evaluate(y_test, preds)
        fitted_pipelines[name] = pipe
        print(f"[{name}] RMSE={results[name]['RMSE']:.4f}  MAE={results[name]['MAE']:.4f}  R2={results[name]['R2']:.4f}")

    # 결과 저장
    results_df = pd.DataFrame(results).T[["RMSE", "MAE", "R2"]]
    results_df.to_csv(OUT_DIR / "model_comparison.csv")
    with open(OUT_DIR / "model_comparison.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # 비교 막대그래프
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, metric in zip(axes, ["RMSE", "MAE", "R2"]):
        results_df[metric].plot(kind="bar", ax=ax, color=["#4C72B0", "#55A868", "#C44E52"])
        ax.set_title(metric)
        ax.set_xlabel("")
        ax.tick_params(axis="x", rotation=0)
    fig.suptitle("Model Comparison: CADD_PHRED Regression")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "model_comparison.png", dpi=150)
    plt.close(fig)

    # RandomForest / XGBoost feature importance
    for name in ["RandomForest", "XGBoost"]:
        pipe = fitted_pipelines[name]
        preprocessor = pipe.named_steps["preprocess"]
        feature_names = preprocessor.get_feature_names_out()
        importances = pipe.named_steps["model"].feature_importances_
        imp_df = (
            pd.Series(importances, index=feature_names)
            .sort_values(ascending=False)
            .head(20)
        )
        fig, ax = plt.subplots(figsize=(8, 6))
        imp_df.sort_values().plot(kind="barh", ax=ax)
        ax.set_title(f"{name} - Top 20 Feature Importance")
        fig.tight_layout()
        fig.savefig(OUT_DIR / f"feature_importance_{name}.png", dpi=150)
        plt.close(fig)

    print("\n=== Model Comparison ===")
    print(results_df)
    print(f"\n결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
