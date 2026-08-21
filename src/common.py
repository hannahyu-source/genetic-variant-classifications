"""
파이프라인 공통 모듈: 경로, 피처 엔지니어링, 전처리기 빌더
05~12번 스크립트가 04_model_improvement.py에서 학습한 피처셋/전처리 로직을
공유하기 위해 사용한다 (숫자로 시작하는 모듈은 `import`할 수 없어 별도 분리).
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DATA_PATH = DATA_DIR / "raw" / "clinvar_conflicting.csv"
PROCESSED_DIR = DATA_DIR / "processed"
RESULTS_DIR = ROOT / "results"
DOCS_DIR = ROOT / "docs"

# 하위 호환: 기존 스크립트들이 DATA_PATH로 참조
DATA_PATH = RAW_DATA_PATH

RANDOM_STATE = 42
TARGET = "CADD_PHRED"

BASE_NUMERIC = ["AF_ESP", "AF_EXAC", "AF_TGP", "ORIGIN", "STRAND", "LoFtool", "BLOSUM62"]
CATEGORICAL_FEATURES = ["CHROM", "IMPACT", "Consequence", "BIOTYPE", "CLNVC", "SIFT", "PolyPhen"]
GENE_COL = "SYMBOL"
TOP_N_GENES = 30  # 상위 N개 유전자만 개별 카테고리로, 나머지는 'Other'


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
    """원본 피처(base)와 엔지니어링 피처(engineered) 두 세트를 구성."""
    df = load_base(df.copy())

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
