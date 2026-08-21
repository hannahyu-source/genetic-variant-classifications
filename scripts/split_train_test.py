"""
회귀분석을 위한 훈련/테스트 데이터 분할
타겟: CADD_PHRED (결측 행 제거 후 분할)
분할 비율: 80% 훈련 / 20% 테스트, random_state=42 (다른 모든 스크립트와 동일 기준 유지)
"""
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "data" / "clinvar_conflicting.csv"
OUT_DIR = ROOT / "data"

RANDOM_STATE = 42
TEST_SIZE = 0.2
TARGET = "CADD_PHRED"


def main():
    df = pd.read_csv(DATA_PATH, low_memory=False)

    before = len(df)
    df = df.dropna(subset=[TARGET]).copy()
    dropped = before - len(df)

    train_df, test_df = train_test_split(
        df, test_size=TEST_SIZE, random_state=RANDOM_STATE
    )

    train_path = OUT_DIR / "train.csv"
    test_path = OUT_DIR / "test.csv"
    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)

    print(f"원본 행 수: {before:,}")
    print(f"타겟({TARGET}) 결측으로 제외된 행: {dropped:,}")
    print(f"분할 후 전체: {len(df):,}")
    print(f"훈련 세트: {len(train_df):,} ({len(train_df)/len(df)*100:.1f}%) -> {train_path}")
    print(f"테스트 세트: {len(test_df):,} ({len(test_df)/len(df)*100:.1f}%) -> {test_path}")
    print(f"\n타겟 평균 비교 - train: {train_df[TARGET].mean():.3f}  test: {test_df[TARGET].mean():.3f}")
    print(f"타겟 표준편차 비교 - train: {train_df[TARGET].std():.3f}  test: {test_df[TARGET].std():.3f}")


if __name__ == "__main__":
    main()
