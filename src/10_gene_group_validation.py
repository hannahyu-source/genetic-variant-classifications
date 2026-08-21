"""
유전자 기반 Group Split 검증 (일반화 테스트)
지금까지의 train/test 분할은 행 단위 랜덤 분할이라 같은 유전자(예: BRCA1)의
변이가 train/test 양쪽에 섞여 들어갈 수 있었다 — 모델이 유전자 정체성을
암기했을 위험이 있다. GroupShuffleSplit/GroupKFold로 유전자(SYMBOL) 단위로
묶어서 분할해, 한 번도 본 적 없는 새 유전자에 대해서도 성능이 유지되는지 확인한다.
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
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBRegressor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PATH, RANDOM_STATE, ROOT, TARGET, build_feature_sets, build_preprocessor

OUT_DIR = ROOT / "results" / "generalization"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# results/regression/model_improvement/results.json 의 XGBoost 튜닝 최적 파라미터
BEST_XGB_PARAMS = dict(
    subsample=1.0, reg_lambda=2, reg_alpha=0.1, n_estimators=600,
    min_child_weight=3, max_depth=7, learning_rate=0.05, colsample_bytree=0.6,
    random_state=RANDOM_STATE, n_jobs=1,
)


def evaluate(y_true, y_pred):
    return {
        "RMSE": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "MAE": float(mean_absolute_error(y_true, y_pred)),
        "R2": float(r2_score(y_true, y_pred)),
    }


def fit_predict(X_train, y_train, X_test, eng_num, categorical):
    pre = build_preprocessor(eng_num, categorical, scale_numeric=False)
    pipe = Pipeline([("preprocess", pre), ("model", XGBRegressor(**BEST_XGB_PARAMS))])
    pipe.fit(X_train, y_train)
    return pipe.predict(X_test)


def main():
    df_raw = pd.read_csv(DATA_PATH, low_memory=False)
    df_raw = df_raw.dropna(subset=[TARGET, "SYMBOL"]).copy()
    df, base_num, eng_num, categorical = build_feature_sets(df_raw)

    cols = eng_num + categorical
    X = df[cols]
    y = df[TARGET]
    groups = df["SYMBOL"]

    print(f"전체 변이 수: {len(df):,}, 고유 유전자 수: {groups.nunique():,}")

    results = {}

    # ---------- (a) 기존 방식: 행 단위 랜덤 분할 ----------
    print("\n[1/2] 행 단위 랜덤 분할 (기존 방식)...")
    idx_train, idx_test = train_test_split(df.index, test_size=0.2, random_state=RANDOM_STATE)
    Xr_train, Xr_test = X.loc[idx_train], X.loc[idx_test]
    yr_train, yr_test = y.loc[idx_train], y.loc[idx_test]

    genes_train = set(groups.loc[idx_train])
    genes_test = set(groups.loc[idx_test])
    overlap = genes_train & genes_test
    print(f"  train 유전자 {len(genes_train):,}개, test 유전자 {len(genes_test):,}개, "
          f"겹치는 유전자 {len(overlap):,}개 ({len(overlap)/len(genes_test)*100:.1f}% of test genes)")

    preds_random = fit_predict(Xr_train, yr_train, Xr_test, eng_num, categorical)
    results["랜덤 분할 (기존)"] = evaluate(yr_test, preds_random)
    r = results["랜덤 분할 (기존)"]
    print(f"  RMSE={r['RMSE']:.3f}  MAE={r['MAE']:.3f}  R2={r['R2']:.3f}")

    # ---------- (b) 유전자 단위 Group Split ----------
    print("\n[2/2] 유전자 단위 Group Split (미지 유전자 검증)...")
    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=RANDOM_STATE)
    idx_train_g, idx_test_g = next(gss.split(X, y, groups=groups))
    Xg_train, Xg_test = X.iloc[idx_train_g], X.iloc[idx_test_g]
    yg_train, yg_test = y.iloc[idx_train_g], y.iloc[idx_test_g]

    genes_train_g = set(groups.iloc[idx_train_g])
    genes_test_g = set(groups.iloc[idx_test_g])
    assert len(genes_train_g & genes_test_g) == 0, "그룹 분할인데 유전자가 겹침"
    print(f"  train 유전자 {len(genes_train_g):,}개, test 유전자 {len(genes_test_g):,}개, 겹침 0개 (보장됨)")
    print(f"  test 세트 행 수: {len(idx_test_g):,}")

    preds_group = fit_predict(Xg_train, yg_train, Xg_test, eng_num, categorical)
    results["유전자 Group Split (신규 유전자)"] = evaluate(yg_test, preds_group)
    r = results["유전자 Group Split (신규 유전자)"]
    print(f"  RMSE={r['RMSE']:.3f}  MAE={r['MAE']:.3f}  R2={r['R2']:.3f}")

    # ---------- (c) 5-fold GroupKFold로 안정성 확인 ----------
    print("\n[추가] 5-fold GroupKFold (안정성 확인)...")
    gkf = GroupKFold(n_splits=5)
    fold_scores = {"RMSE": [], "MAE": [], "R2": []}
    for fold_i, (tr_idx, te_idx) in enumerate(gkf.split(X, y, groups=groups), 1):
        preds_fold = fit_predict(X.iloc[tr_idx], y.iloc[tr_idx], X.iloc[te_idx], eng_num, categorical)
        m = evaluate(y.iloc[te_idx], preds_fold)
        for k in fold_scores:
            fold_scores[k].append(m[k])
        print(f"  fold {fold_i}: RMSE={m['RMSE']:.3f}  MAE={m['MAE']:.3f}  R2={m['R2']:.3f}")

    gkf_summary = {k: {"mean": float(np.mean(v)), "std": float(np.std(v))} for k, v in fold_scores.items()}
    print(f"  GroupKFold 평균: RMSE={gkf_summary['RMSE']['mean']:.3f}±{gkf_summary['RMSE']['std']:.3f}  "
          f"R2={gkf_summary['R2']['mean']:.3f}±{gkf_summary['R2']['std']:.3f}")

    # ---------- 저장 ----------
    results_df = pd.DataFrame(results).T[["RMSE", "MAE", "R2"]]
    results_df.to_csv(OUT_DIR / "split_comparison.csv")

    gkf_df = pd.DataFrame(gkf_summary).T
    gkf_df.to_csv(OUT_DIR / "groupkfold_summary.csv")

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5))
    colors = ["#4C72B0", "#C44E52"]
    for ax, metric in zip(axes, ["RMSE", "MAE", "R2"]):
        results_df[metric].plot(kind="bar", ax=ax, color=colors)
        ax.set_title(metric)
        ax.set_xticklabels(["랜덤 분할\n(기존)", "Group Split\n(신규 유전자)"], rotation=0)
    fig.suptitle("일반화 검증: 랜덤 분할 vs 유전자 기반 Group Split")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "split_comparison.png", dpi=150)
    plt.close(fig)

    r2_drop = results["랜덤 분할 (기존)"]["R2"] - results["유전자 Group Split (신규 유전자)"]["R2"]
    print(f"\nR2 하락폭 (랜덤 -> Group): {r2_drop:.3f}")
    print(f"결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
