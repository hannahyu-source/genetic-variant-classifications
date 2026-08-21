"""
모델 개선: 피처 엔지니어링 + K-fold 교차검증 + 하이퍼파라미터 튜닝
타겟: CADD_PHRED
비교: 기존(baseline) 모델 vs 개선(engineered + tuned) 모델
"""
import json
import re
import time
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
from sklearn.metrics import make_scorer, mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, RandomizedSearchCV, cross_validate, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBRegressor

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "clinvar_conflicting.csv"
OUT_DIR = ROOT / "outputs" / "model_improvement"
OUT_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
TARGET = "CADD_PHRED"

BASE_NUMERIC = ["AF_ESP", "AF_EXAC", "AF_TGP", "ORIGIN", "STRAND", "LoFtool", "BLOSUM62"]
CATEGORICAL_FEATURES = ["CHROM", "IMPACT", "Consequence", "BIOTYPE", "CLNVC", "SIFT", "PolyPhen"]
GENE_COL = "SYMBOL"
TOP_N_GENES = 30


def parse_position_range(value):
    """'123', '800-802', '?-117' 등을 단일 숫자로 파싱 (범위는 평균)."""
    if pd.isna(value):
        return np.nan
    nums = re.findall(r"\d+", str(value))
    if not nums:
        return np.nan
    nums = [int(n) for n in nums]
    return float(np.mean(nums))


def parse_ratio(value):
    """'6/12' -> 0.5 형태의 EXON/INTRON 비율 파싱."""
    if pd.isna(value):
        return np.nan
    m = re.match(r"^(\d+)/(\d+)$", str(value))
    if not m:
        return np.nan
    num, denom = int(m.group(1)), int(m.group(2))
    return num / denom if denom else np.nan


def load_base(df):
    top_genes = df[GENE_COL].value_counts().nlargest(TOP_N_GENES).index
    df["GENE_GROUP"] = df[GENE_COL].where(df[GENE_COL].isin(top_genes), "Other")
    return df


def build_feature_sets(df):
    df = load_base(df.copy())

    # --- 엔지니어링 피처 ---
    for col in ["AF_ESP", "AF_EXAC", "AF_TGP"]:
        df[f"log_{col}"] = np.log1p(df[col])
    df["EXON_ratio"] = df["EXON"].apply(parse_ratio)
    df["INTRON_ratio"] = df["INTRON"].apply(parse_ratio)
    df["Protein_position_num"] = df["Protein_position"].apply(parse_position_range)
    df["CDS_position_num"] = df["CDS_position"].apply(parse_position_range)
    df["cDNA_position_num"] = df["cDNA_position"].apply(parse_position_range)

    engineered_numeric = [
        "log_AF_ESP", "log_AF_EXAC", "log_AF_TGP",  # AF 로그변환 (원본 대체)
        "ORIGIN", "STRAND", "LoFtool", "BLOSUM62",
        "EXON_ratio", "INTRON_ratio",
        "Protein_position_num", "CDS_position_num", "cDNA_position_num",
    ]
    categorical = CATEGORICAL_FEATURES + ["GENE_GROUP"]

    return df, BASE_NUMERIC, engineered_numeric, categorical


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


def rmse_scorer():
    return make_scorer(lambda yt, yp: np.sqrt(mean_squared_error(yt, yp)), greater_is_better=False)


SCORING = {
    "RMSE": rmse_scorer(),
    "MAE": "neg_mean_absolute_error",
    "R2": "r2",
}


def summarize_cv(cv_results):
    out = {}
    for metric in ["RMSE", "MAE", "R2"]:
        scores = cv_results[f"test_{metric}"]
        if metric in ("RMSE", "MAE"):
            scores = -scores  # neg -> positive
        out[metric] = {"mean": float(np.mean(scores)), "std": float(np.std(scores))}
    return out


def evaluate_holdout(y_true, y_pred):
    return {
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "R2": float(r2_score(y_true, y_pred)),
    }


def main():
    t0 = time.time()
    df_raw = pd.read_csv(DATA_PATH, low_memory=False)
    df_raw = df_raw.dropna(subset=[TARGET]).copy()

    df, base_num, eng_num, categorical = build_feature_sets(df_raw)

    base_cols = base_num + categorical
    eng_cols = eng_num + categorical

    X_base = df[base_cols]
    X_eng = df[eng_cols]
    y = df[TARGET]

    idx_train, idx_test = train_test_split(
        df.index, test_size=0.2, random_state=RANDOM_STATE
    )

    Xb_train, Xb_test = X_base.loc[idx_train], X_base.loc[idx_test]
    Xe_train, Xe_test = X_eng.loc[idx_train], X_eng.loc[idx_test]
    y_train, y_test = y.loc[idx_train], y.loc[idx_test]

    kfold = KFold(n_splits=5, shuffle=True, random_state=RANDOM_STATE)

    results = {"cv": {}, "holdout": {}, "tuning": {}}

    # ---------- 1) Baseline 5-fold CV (기존 피처) ----------
    print("=== Step 1: Baseline 5-fold CV (기존 피처셋) ===")
    baseline_models = {
        "LinearRegression": (LinearRegression(), True),
        "RandomForest": (RandomForestRegressor(n_estimators=300, max_depth=20, random_state=RANDOM_STATE, n_jobs=1), False),
        "XGBoost": (XGBRegressor(n_estimators=400, max_depth=6, learning_rate=0.05,
                                  subsample=0.8, colsample_bytree=0.8,
                                  random_state=RANDOM_STATE, n_jobs=1), False),
    }
    for name, (estimator, scale) in baseline_models.items():
        pre = build_preprocessor(base_num, categorical, scale)
        pipe = Pipeline([("preprocess", pre), ("model", estimator)])
        cv_res = cross_validate(pipe, Xb_train, y_train, cv=kfold, scoring=SCORING, n_jobs=-1)
        summary = summarize_cv(cv_res)
        results["cv"][f"baseline_{name}"] = summary
        print(f"[baseline-{name}] RMSE={summary['RMSE']['mean']:.3f}±{summary['RMSE']['std']:.3f}  "
              f"MAE={summary['MAE']['mean']:.3f}±{summary['MAE']['std']:.3f}  "
              f"R2={summary['R2']['mean']:.3f}±{summary['R2']['std']:.3f}")

    # ---------- 2) 엔지니어링 피처로 5-fold CV ----------
    print("\n=== Step 2: 5-fold CV (엔지니어링 피처셋) ===")
    engineered_models = {
        "LinearRegression": (LinearRegression(), True),
        "RandomForest": (RandomForestRegressor(n_estimators=300, max_depth=20, random_state=RANDOM_STATE, n_jobs=1), False),
        "XGBoost": (XGBRegressor(n_estimators=400, max_depth=6, learning_rate=0.05,
                                  subsample=0.8, colsample_bytree=0.8,
                                  random_state=RANDOM_STATE, n_jobs=1), False),
    }
    for name, (estimator, scale) in engineered_models.items():
        pre = build_preprocessor(eng_num, categorical, scale)
        pipe = Pipeline([("preprocess", pre), ("model", estimator)])
        cv_res = cross_validate(pipe, Xe_train, y_train, cv=kfold, scoring=SCORING, n_jobs=-1)
        summary = summarize_cv(cv_res)
        results["cv"][f"engineered_{name}"] = summary
        print(f"[engineered-{name}] RMSE={summary['RMSE']['mean']:.3f}±{summary['RMSE']['std']:.3f}  "
              f"MAE={summary['MAE']['mean']:.3f}±{summary['MAE']['std']:.3f}  "
              f"R2={summary['R2']['mean']:.3f}±{summary['R2']['std']:.3f}")

    # ---------- 3) 하이퍼파라미터 튜닝 (RF, XGB, 엔지니어링 피처) ----------
    print("\n=== Step 3: 하이퍼파라미터 튜닝 (RandomizedSearchCV) ===")
    tuned_pipelines = {}

    rf_pre = build_preprocessor(eng_num, categorical, scale_numeric=False)
    rf_pipe = Pipeline([("preprocess", rf_pre), ("model", RandomForestRegressor(random_state=RANDOM_STATE, n_jobs=1))])
    rf_param_dist = {
        "model__n_estimators": [200, 300, 400, 500],
        "model__max_depth": [10, 15, 20, 30],
        "model__min_samples_split": [2, 5, 10],
        "model__min_samples_leaf": [1, 2, 4],
        "model__max_features": ["sqrt", "log2", 0.5],
    }
    rf_search = RandomizedSearchCV(
        rf_pipe, rf_param_dist, n_iter=10, cv=3,
        scoring="neg_root_mean_squared_error", random_state=RANDOM_STATE, n_jobs=-1, verbose=0,
    )
    rf_search.fit(Xe_train, y_train)
    tuned_pipelines["RandomForest"] = rf_search.best_estimator_
    results["tuning"]["RandomForest"] = {
        "best_params": rf_search.best_params_,
        "best_cv_rmse": -rf_search.best_score_,
    }
    print(f"[RF tuned] best_cv_RMSE={-rf_search.best_score_:.3f}  params={rf_search.best_params_}")

    xgb_pre = build_preprocessor(eng_num, categorical, scale_numeric=False)
    xgb_pipe = Pipeline([("preprocess", xgb_pre), ("model", XGBRegressor(random_state=RANDOM_STATE, n_jobs=1))])
    xgb_param_dist = {
        "model__n_estimators": [200, 300, 400, 600],
        "model__max_depth": [3, 4, 5, 6, 7, 8],
        "model__learning_rate": [0.01, 0.03, 0.05, 0.1],
        "model__subsample": [0.6, 0.8, 1.0],
        "model__colsample_bytree": [0.6, 0.8, 1.0],
        "model__min_child_weight": [1, 3, 5],
        "model__reg_alpha": [0, 0.1, 1],
        "model__reg_lambda": [1, 1.5, 2],
    }
    xgb_search = RandomizedSearchCV(
        xgb_pipe, xgb_param_dist, n_iter=10, cv=3,
        scoring="neg_root_mean_squared_error", random_state=RANDOM_STATE, n_jobs=-1, verbose=0,
    )
    xgb_search.fit(Xe_train, y_train)
    tuned_pipelines["XGBoost"] = xgb_search.best_estimator_
    results["tuning"]["XGBoost"] = {
        "best_params": xgb_search.best_params_,
        "best_cv_rmse": -xgb_search.best_score_,
    }
    print(f"[XGB tuned] best_cv_RMSE={-xgb_search.best_score_:.3f}  params={xgb_search.best_params_}")

    # ---------- 4) 최종 holdout 평가: baseline vs engineered vs tuned ----------
    print("\n=== Step 4: Holdout Test 최종 비교 ===")

    # baseline (원본 피처, 튜닝 전 기본 하이퍼파라미터)
    for name, (estimator, scale) in baseline_models.items():
        pre = build_preprocessor(base_num, categorical, scale)
        pipe = Pipeline([("preprocess", pre), ("model", estimator)])
        pipe.fit(Xb_train, y_train)
        preds = pipe.predict(Xb_test)
        results["holdout"][f"baseline_{name}"] = evaluate_holdout(y_test, preds)

    # engineered + default params
    for name, (estimator, scale) in engineered_models.items():
        pre = build_preprocessor(eng_num, categorical, scale)
        pipe = Pipeline([("preprocess", pre), ("model", estimator)])
        pipe.fit(Xe_train, y_train)
        preds = pipe.predict(Xe_test)
        results["holdout"][f"engineered_{name}"] = evaluate_holdout(y_test, preds)

    # engineered + tuned (RF, XGB만 해당)
    for name, pipe in tuned_pipelines.items():
        preds = pipe.predict(Xe_test)
        results["holdout"][f"tuned_{name}"] = evaluate_holdout(y_test, preds)
        print(f"[tuned-{name}] RMSE={results['holdout'][f'tuned_{name}']['RMSE']:.3f}  "
              f"MAE={results['holdout'][f'tuned_{name}']['MAE']:.3f}  "
              f"R2={results['holdout'][f'tuned_{name}']['R2']:.3f}")

    # ---------- 저장 ----------
    with open(OUT_DIR / "results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    holdout_df = pd.DataFrame(results["holdout"]).T[["RMSE", "MAE", "R2"]]
    holdout_df.to_csv(OUT_DIR / "holdout_comparison.csv")

    # 시각화: XGBoost 기준 baseline -> engineered -> tuned 개선 추이
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    stages = ["baseline_XGBoost", "engineered_XGBoost", "tuned_XGBoost"]
    stage_labels = ["Baseline", "+Feature Eng.", "+Tuning"]
    for ax, metric in zip(axes, ["RMSE", "MAE", "R2"]):
        vals = [results["holdout"][s][metric] for s in stages]
        ax.bar(stage_labels, vals, color=["#4C72B0", "#55A868", "#C44E52"])
        ax.set_title(f"XGBoost {metric}")
    fig.suptitle("XGBoost Improvement: Baseline -> Feature Engineering -> Tuning")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "xgboost_improvement_stages.png", dpi=150)
    plt.close(fig)

    # 시각화: 전체 holdout 비교 (9개 조합)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    for ax, metric in zip(axes, ["RMSE", "MAE", "R2"]):
        holdout_df[metric].plot(kind="barh", ax=ax, color="#8172B2")
        ax.set_title(metric)
    fig.suptitle("All Models Holdout Comparison (baseline / engineered / tuned)")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "all_holdout_comparison.png", dpi=150)
    plt.close(fig)

    print("\n=== 최종 Holdout 비교표 ===")
    print(holdout_df)
    print(f"\n총 소요시간: {time.time()-t0:.1f}초")
    print(f"결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
