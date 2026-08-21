"""
분류 확장: CLASS(임상 해석 상충 여부) 예측
모델: LogisticRegression / RandomForestClassifier / XGBClassifier
평가: Accuracy, Precision, Recall, F1, ROC-AUC (CLASS가 0:74.8% / 1:25.2%로 불균형 -> class_weight/scale_pos_weight 적용)
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
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay, RocCurveDisplay, accuracy_score, f1_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PATH, RANDOM_STATE, ROOT, build_feature_sets, build_preprocessor

OUT_DIR = ROOT / "results" / "classification"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "CLASS"


def main():
    df_raw = pd.read_csv(DATA_PATH, low_memory=False)
    df, base_num, eng_num, categorical = build_feature_sets(df_raw)

    numeric_features = eng_num + ["CADD_PHRED"]  # 회귀 타겟이었던 CADD_PHRED를 여기선 특성으로 사용 (누수 아님, CLASS와 별개)
    X = df[numeric_features + categorical]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
    scale_pos_weight = neg / pos
    print(f"훈련셋 클래스 분포 - 0: {neg:,}  1: {pos:,}  (scale_pos_weight={scale_pos_weight:.3f})")

    models = {
        "LogisticRegression": (
            LogisticRegression(max_iter=1000, class_weight="balanced", random_state=RANDOM_STATE), True
        ),
        "RandomForest": (
            RandomForestClassifier(
                n_estimators=300, max_depth=20, class_weight="balanced",
                random_state=RANDOM_STATE, n_jobs=1,
            ), False
        ),
        "XGBoost": (
            XGBClassifier(
                n_estimators=400, max_depth=6, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8, scale_pos_weight=scale_pos_weight,
                eval_metric="logloss", random_state=RANDOM_STATE, n_jobs=1,
            ), False
        ),
    }

    results = {}
    fitted = {}
    for name, (estimator, scale) in models.items():
        pre = build_preprocessor(numeric_features, categorical, scale)
        pipe = Pipeline([("preprocess", pre), ("model", estimator)])
        pipe.fit(X_train, y_train)
        preds = pipe.predict(X_test)
        proba = pipe.predict_proba(X_test)[:, 1]

        results[name] = {
            "Accuracy": accuracy_score(y_test, preds),
            "Precision": precision_score(y_test, preds),
            "Recall": recall_score(y_test, preds),
            "F1": f1_score(y_test, preds),
            "ROC_AUC": roc_auc_score(y_test, proba),
        }
        fitted[name] = pipe
        r = results[name]
        print(f"[{name}] Acc={r['Accuracy']:.3f}  Prec={r['Precision']:.3f}  Rec={r['Recall']:.3f}  "
              f"F1={r['F1']:.3f}  ROC-AUC={r['ROC_AUC']:.3f}")

    results_df = pd.DataFrame(results).T[["Accuracy", "Precision", "Recall", "F1", "ROC_AUC"]]
    results_df.to_csv(OUT_DIR / "classification_comparison.csv")

    # 비교 막대그래프
    fig, ax = plt.subplots(figsize=(9, 5))
    results_df.plot(kind="bar", ax=ax)
    ax.set_title("분류 모델 비교: CLASS(상충 여부) 예측")
    ax.set_ylim(0, 1)
    ax.tick_params(axis="x", rotation=0)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "classification_comparison.png", dpi=150)
    plt.close(fig)

    # 혼동행렬 (3개 모델)
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, (name, pipe) in zip(axes, fitted.items()):
        ConfusionMatrixDisplay.from_estimator(
            pipe, X_test, y_test, ax=ax, display_labels=["비상충(0)", "상충(1)"], colorbar=False
        )
        ax.set_title(name)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "confusion_matrices.png", dpi=150)
    plt.close(fig)

    # ROC curve 비교
    fig, ax = plt.subplots(figsize=(6, 6))
    for name, pipe in fitted.items():
        RocCurveDisplay.from_estimator(pipe, X_test, y_test, ax=ax, name=name)
    ax.plot([0, 1], [0, 1], "k--", alpha=0.4)
    ax.set_title("ROC Curve 비교")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "roc_curves.png", dpi=150)
    plt.close(fig)

    # XGBoost feature importance
    pipe = fitted["XGBoost"]
    pre = pipe.named_steps["preprocess"]
    feature_names = pre.get_feature_names_out()
    importances = pipe.named_steps["model"].feature_importances_
    imp = pd.Series(importances, index=feature_names).sort_values(ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(8, 6))
    imp.sort_values().plot(kind="barh", ax=ax)
    ax.set_title("XGBoost - CLASS 예측 Top 20 특성 중요도")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "feature_importance_XGBoost.png", dpi=150)
    plt.close(fig)

    print("\n=== 분류 모델 비교 ===")
    print(results_df)
    print(f"\n결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
