"""
분류 임계값(threshold) 조정을 통한 Precision-Recall 트레이드오프 분석
- classify_conflicting.py에서 가장 우수했던 XGBoost 분류기 사용
- 기본 임계값(0.5) vs F1 최대화 임계값 vs 상황별(고재현율/고정밀) 임계값 비교
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
from sklearn.metrics import (
    average_precision_score, f1_score, precision_recall_curve,
    precision_score, recall_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PATH, RANDOM_STATE, ROOT, build_feature_sets, build_preprocessor

OUT_DIR = ROOT / "results" / "classification" / "threshold_analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "CLASS"


def metrics_at_threshold(y_true, proba, threshold):
    preds = (proba >= threshold).astype(int)
    return {
        "threshold": threshold,
        "Precision": precision_score(y_true, preds, zero_division=0),
        "Recall": recall_score(y_true, preds, zero_division=0),
        "F1": f1_score(y_true, preds, zero_division=0),
    }


def main():
    df_raw = pd.read_csv(DATA_PATH, low_memory=False)
    df, base_num, eng_num, categorical = build_feature_sets(df_raw)

    numeric_features = eng_num + ["CADD_PHRED"]
    X = df[numeric_features + categorical]
    y = df[TARGET]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )
    neg, pos = (y_train == 0).sum(), (y_train == 1).sum()
    scale_pos_weight = neg / pos

    pre = build_preprocessor(numeric_features, categorical, scale_numeric=False)
    model = XGBClassifier(
        n_estimators=400, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, scale_pos_weight=scale_pos_weight,
        eval_metric="logloss", random_state=RANDOM_STATE, n_jobs=1,
    )
    pipe = Pipeline([("preprocess", pre), ("model", model)])
    pipe.fit(X_train, y_train)
    proba = pipe.predict_proba(X_test)[:, 1]

    precisions, recalls, thresholds = precision_recall_curve(y_test, proba)
    ap = average_precision_score(y_test, proba)

    # F1을 최대화하는 임계값 탐색 (thresholds는 precisions/recalls보다 1개 적음)
    f1_scores = 2 * precisions[:-1] * recalls[:-1] / (precisions[:-1] + recalls[:-1] + 1e-12)
    best_idx = np.argmax(f1_scores)
    best_f1_threshold = thresholds[best_idx]

    # 상황별 임계값: 고재현율(선별 스크리닝용, Recall>=0.9 만족하는 가장 높은 threshold)
    high_recall_candidates = thresholds[recalls[:-1] >= 0.9]
    high_recall_threshold = high_recall_candidates.max() if len(high_recall_candidates) else thresholds.min()

    # 고정밀(확신 있는 플래깅용, Precision>=0.7 만족하는 가장 낮은 threshold)
    high_precision_candidates = thresholds[precisions[:-1] >= 0.7]
    high_precision_threshold = high_precision_candidates.min() if len(high_precision_candidates) else thresholds.max()

    scenarios = {
        "기본 (0.5)": 0.5,
        "F1 최대화": float(best_f1_threshold),
        "고재현율 (Recall>=0.9)": float(high_recall_threshold),
        "고정밀 (Precision>=0.7)": float(high_precision_threshold),
    }

    rows = []
    for name, th in scenarios.items():
        m = metrics_at_threshold(y_test, proba, th)
        m["scenario"] = name
        rows.append(m)
    result_df = pd.DataFrame(rows)[["scenario", "threshold", "Precision", "Recall", "F1"]]
    result_df.to_csv(OUT_DIR / "threshold_scenarios.csv", index=False)

    print(f"Average Precision (AP) = {ap:.3f}")
    print(result_df.to_string(index=False))

    # ---------- 플롯 1: Precision-Recall curve ----------
    fig, ax = plt.subplots(figsize=(6.5, 6))
    ax.plot(recalls, precisions, label=f"XGBoost (AP={ap:.3f})", color="#4C72B0")
    baseline = y_test.mean()
    ax.axhline(baseline, linestyle="--", color="gray", alpha=0.6, label=f"무작위 기준선 (Precision={baseline:.3f})")
    for name, th in scenarios.items():
        m = metrics_at_threshold(y_test, proba, th)
        ax.scatter(m["Recall"], m["Precision"], zorder=5)
        ax.annotate(name, (m["Recall"], m["Precision"]), textcoords="offset points", xytext=(6, 6), fontsize=9)
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Precision-Recall Curve (XGBoost, CLASS 예측)")
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "precision_recall_curve.png", dpi=150)
    plt.close(fig)

    # ---------- 플롯 2: 임계값에 따른 Precision/Recall/F1 변화 ----------
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(thresholds, precisions[:-1], label="Precision", color="#4C72B0")
    ax.plot(thresholds, recalls[:-1], label="Recall", color="#DD8452")
    ax.plot(thresholds, f1_scores, label="F1", color="#55A868")
    for name, th in scenarios.items():
        ax.axvline(th, linestyle=":", alpha=0.5)
        ax.text(th, 1.02, name, rotation=90, fontsize=8, ha="right", va="bottom")
    ax.set_xlabel("임계값 (threshold)")
    ax.set_ylabel("점수")
    ax.set_ylim(0, 1.15)
    ax.set_title("임계값에 따른 Precision/Recall/F1 트레이드오프")
    ax.legend(loc="center right")
    fig.tight_layout()
    fig.savefig(OUT_DIR / "threshold_tradeoff.png", dpi=150)
    plt.close(fig)

    print(f"\n결과 저장 위치: {OUT_DIR}")


if __name__ == "__main__":
    main()
