"""
Tabular Generation Engine — produces high-fidelity synthetic data 
using Gaussian Copula correlation preservation, empirical marginal 
distributions, and configurable privacy transforms.

Optimized for high TSTR (Train on Synthetic, Test on Real) scores.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd
from scipy import stats as sp_stats
from scipy.stats import norm, rankdata
from faker import Faker

from backend.core.schema import (
    DataType, FieldDefinition, TableDefinition, SchemaDefinition,
    FieldConstraint, PrivacyTransform, EdgeCase
)

logger = logging.getLogger(__name__)

PAKISTAN_NAMES = [
    "Ayesha Khan", "Ali Raza", "Fatima Ahmed", "Hassan Malik",
    "Maham Iqbal", "Usman Tariq", "Sana Siddiqui", "Bilal Shah",
    "Zainab Noor", "Hamza Qureshi", "Maryam Hussain", "Omar Farooq",
]
PAKISTAN_CITIES = [
    ("Lahore", "Punjab"), ("Karachi", "Sindh"), ("Islamabad", "ICT"),
    ("Rawalpindi", "Punjab"), ("Faisalabad", "Punjab"),
    ("Peshawar", "Khyber Pakhtunkhwa"), ("Multan", "Punjab"),
    ("Quetta", "Balochistan"),
]


def _is_pakistan_locale(locale: str) -> bool:
    return locale.lower() in {"pk", "en_pk", "ur_pk", "pa_pk"}


def _create_faker(locale: str) -> Faker:
    """Use a safe Faker fallback when a regional provider is unavailable."""
    try:
        return Faker(locale)
    except AttributeError:
        return Faker("en_US")


# ──────────────────────────── Statistical Profiling ────────────────────────────

class ColumnProfile:
    """Statistical profile for a single column."""

    def __init__(self, name: str, dtype: DataType, values: Optional[np.ndarray] = None):
        self.name = name
        self.dtype = dtype
        self.mean: float = 0.0
        self.std: float = 1.0
        self.min_val: float = 0.0
        self.max_val: float = 100.0
        self.quantiles: dict[float, float] = {}
        self.categories: list[str] = []
        self.cat_probs: np.ndarray = np.array([])
        self.null_rate: float = 0.0
        self.ecdf_values: np.ndarray = np.array([])

        if values is not None:
            self._fit(values)

    def _fit(self, values: np.ndarray) -> None:
        """Fit empirical distribution from sample data."""
        self.null_rate = float(pd.isna(values).mean())
        clean = values[~pd.isna(values)]

        if len(clean) == 0:
            return

        if self.dtype in (DataType.INTEGER, DataType.FLOAT, DataType.CURRENCY):
            numeric = pd.to_numeric(
                pd.Series(clean).astype(str).str.replace(r"[$,£€]", "", regex=True),
                errors="coerce"
            ).dropna().values

            if len(numeric) > 0:
                self.mean = float(np.mean(numeric))
                self.std = float(np.std(numeric)) or 1.0
                self.min_val = float(np.min(numeric))
                self.max_val = float(np.max(numeric))
                self.quantiles = {
                    q: float(np.quantile(numeric, q))
                    for q in [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99]
                }
                self.ecdf_values = np.sort(numeric)

        elif self.dtype in (DataType.CATEGORY, DataType.BOOLEAN):
            vals, counts = np.unique(clean.astype(str), return_counts=True)
            self.categories = vals.tolist()
            self.cat_probs = counts / counts.sum()


class TableProfile:
    """Statistical profile for an entire table, including correlation matrix."""

    def __init__(self, df: pd.DataFrame, table_def: TableDefinition):
        self.table_def = table_def
        self.column_profiles: dict[str, ColumnProfile] = {}
        self.correlation_matrix: Optional[np.ndarray] = None
        self.numeric_columns: list[str] = []

        self._fit(df)

    def _fit(self, df: pd.DataFrame) -> None:
        """Profile all columns and compute correlation matrix."""
        for field in self.table_def.fields:
            if field.name in df.columns:
                self.column_profiles[field.name] = ColumnProfile(
                    field.name, field.data_type, df[field.name].values
                )

        # Compute Pearson correlation matrix for numeric columns
        numeric_cols = []
        for field in self.table_def.fields:
            if field.data_type in (DataType.INTEGER, DataType.FLOAT, DataType.CURRENCY):
                if field.name in df.columns:
                    numeric_cols.append(field.name)

        self.numeric_columns = numeric_cols

        if len(numeric_cols) >= 2:
            numeric_df = df[numeric_cols].apply(
                lambda x: pd.to_numeric(
                    x.astype(str).str.replace(r"[$,£€]", "", regex=True),
                    errors="coerce"
                )
            ).dropna()

            if len(numeric_df) > 5:
                corr = numeric_df.corr().values
                # Make correlation matrix positive semi-definite
                eigvals, eigvecs = np.linalg.eigh(corr)
                eigvals = np.maximum(eigvals, 1e-8)
                self.correlation_matrix = eigvecs @ np.diag(eigvals) @ eigvecs.T
                # Normalize to correlation matrix
                d = np.sqrt(np.diag(self.correlation_matrix))
                self.correlation_matrix = self.correlation_matrix / np.outer(d, d)


# ──────────────────────────── Gaussian Copula Sampler ────────────────────────────

def _gaussian_copula_sample(
    n: int,
    correlation_matrix: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """
    Sample from a Gaussian copula to preserve correlation structure.
    Returns uniform marginals with the specified correlation.
    """
    dim = correlation_matrix.shape[0]

    # Generate correlated normal samples
    try:
        L = np.linalg.cholesky(correlation_matrix)
    except np.linalg.LinAlgError:
        # Fallback: add small diagonal noise
        eps = np.eye(dim) * 0.01
        L = np.linalg.cholesky(correlation_matrix + eps)

    z = rng.standard_normal((n, dim))
    correlated = z @ L.T

    # Transform to uniform marginals via CDF
    uniform = norm.cdf(correlated)
    return uniform


def _sample_from_ecdf(uniform_values: np.ndarray, ecdf_sorted: np.ndarray) -> np.ndarray:
    """Map uniform [0,1] samples to empirical distribution using inverse ECDF."""
    n = len(ecdf_sorted)
    if n == 0:
        return uniform_values

    indices = np.clip((uniform_values * n).astype(int), 0, n - 1)
    return ecdf_sorted[indices]


def _sample_from_stats(
    n: int,
    profile: ColumnProfile,
    rng: np.random.Generator,
    uniform_values: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Sample numeric values matching the empirical distribution."""
    if profile.ecdf_values is not None and len(profile.ecdf_values) > 10:
        if uniform_values is not None:
            return _sample_from_ecdf(uniform_values, profile.ecdf_values)
        else:
            u = rng.uniform(0, 1, n)
            return _sample_from_ecdf(u, profile.ecdf_values)

    # Fallback: normal distribution with clipping
    values = rng.normal(profile.mean, profile.std, n)
    values = np.clip(values, profile.min_val, profile.max_val)
    return values


# ──────────────────────────── Value Generators ────────────────────────────

def _generate_column_values(
    field: FieldDefinition,
    n: int,
    rng: np.random.Generator,
    fake: Faker,
    profile: Optional[ColumnProfile] = None,
    uniform_values: Optional[np.ndarray] = None,
    locale: str = "en_US",
) -> list[Any]:
    """Generate n values for a single column based on its type and constraints."""

    constraint = field.constraint

    if field.data_type == DataType.INTEGER:
        if profile and profile.ecdf_values is not None and len(profile.ecdf_values) > 0:
            vals = _sample_from_stats(n, profile, rng, uniform_values)
            return [int(round(v)) for v in vals]
        lo = int(constraint.min_value or 1)
        hi = int(constraint.max_value or 10000)
        return rng.integers(lo, hi + 1, n).tolist()

    if field.data_type in (DataType.FLOAT, DataType.CURRENCY):
        if profile and profile.ecdf_values is not None and len(profile.ecdf_values) > 0:
            vals = _sample_from_stats(n, profile, rng, uniform_values)
            return [round(float(v), 2) for v in vals]
        lo = constraint.min_value or 0.0
        hi = constraint.max_value or 1000.0
        return [round(float(v), 2) for v in rng.uniform(lo, hi, n)]

    if field.data_type == DataType.NAME:
        if _is_pakistan_locale(locale):
            return rng.choice(PAKISTAN_NAMES, n).tolist()
        return [fake.name() for _ in range(n)]

    if field.data_type == DataType.EMAIL:
        if _is_pakistan_locale(locale):
            names = rng.choice(PAKISTAN_NAMES, n)
            usernames = [name.lower().replace(" ", ".") for name in names]
            return [f"{username}@example.com" for username in usernames]
        names = [fake.user_name() for _ in range(n)]
        return [f"{name}@example.com" for name in names]

    if field.data_type == DataType.PHONE:
        if _is_pakistan_locale(locale):
            return [
                f"+92 3{int(rng.integers(0, 10))}{int(rng.integers(1000000, 9999999))}"
                for _ in range(n)
            ]
        return [fake.phone_number() for _ in range(n)]

    if field.data_type == DataType.ADDRESS:
        if _is_pakistan_locale(locale):
            return [
                f"House {int(rng.integers(1, 250))}, {city}, {province}"
                for city, province in rng.choice(PAKISTAN_CITIES, n)
            ]
        return [fake.city() for _ in range(n)]

    if field.data_type == DataType.DATE:
        start = datetime(2020, 1, 1)
        end = datetime(2025, 12, 31)
        delta = (end - start).days
        offsets = rng.integers(0, delta, n)
        return [(start + timedelta(days=int(d))).strftime("%Y-%m-%d") for d in offsets]

    if field.data_type == DataType.DATETIME:
        start = datetime(2020, 1, 1)
        end = datetime(2025, 12, 31)
        delta = int((end - start).total_seconds())
        offsets = rng.integers(0, delta, n)
        return [(start + timedelta(seconds=int(s))).isoformat() for s in offsets]

    if field.data_type == DataType.BOOLEAN:
        if profile and len(profile.categories) > 0:
            return rng.choice(profile.categories, n, p=profile.cat_probs).tolist()
        return rng.choice(["true", "false"], n).tolist()

    if field.data_type == DataType.CATEGORY:
        if profile and len(profile.categories) > 0:
            return rng.choice(profile.categories, n, p=profile.cat_probs).tolist()
        if constraint.allowed_values:
            return rng.choice(constraint.allowed_values, n).tolist()
        return [fake.word() for _ in range(n)]

    if field.data_type == DataType.UUID:
        return [fake.uuid4() for _ in range(n)]

    if field.data_type == DataType.URL:
        return [fake.url() for _ in range(n)]

    if field.data_type == DataType.TEXT:
        return [fake.paragraph(nb_sentences=2) for _ in range(n)]

    # Default: string
    if profile and profile.column_profiles if hasattr(profile, 'column_profiles') else False:
        pass
    if constraint.allowed_values:
        return rng.choice(constraint.allowed_values, n).tolist()

    avg_len = int(field.stats.get("avg_length", 10)) if field.stats else 10
    if avg_len > 50:
        return [fake.paragraph() for _ in range(n)]
    return [fake.word() for _ in range(n)]


# ──────────────────────────── Privacy Transforms ────────────────────────────

def apply_privacy(values: list[Any], transform: PrivacyTransform, salt: str = "synth2025") -> list[Any]:
    """Apply column-level privacy transformations."""
    if transform == PrivacyTransform.NONE:
        return values

    if transform == PrivacyTransform.MASK:
        def mask(v):
            s = str(v)
            if len(s) <= 2:
                return "**"
            return s[0] + "*" * (len(s) - 2) + s[-1]
        return [mask(v) if v is not None else None for v in values]

    if transform == PrivacyTransform.HASH_SHA256:
        def hash_val(v):
            if v is None:
                return None
            return hashlib.sha256(f"{salt}{v}".encode()).hexdigest()[:16]
        return [hash_val(v) for v in values]

    if transform == PrivacyTransform.LAPLACE_NOISE:
        rng = np.random.default_rng(42)
        def add_noise(v):
            if v is None:
                return None
            try:
                numeric = float(v)
                noise = rng.laplace(0, max(abs(numeric) * 0.05, 0.01))
                return round(numeric + noise, 2)
            except (ValueError, TypeError):
                return v
        return [add_noise(v) for v in values]

    if transform == PrivacyTransform.REDACT:
        return ["[REDACTED]" if v is not None else None for v in values]

    return values


# ──────────────────────────── Null & Outlier Injection ────────────────────────────

def inject_nulls(values: list[Any], rate: float, rng: np.random.Generator) -> list[Any]:
    """Randomly inject None values at the specified rate."""
    if rate <= 0:
        return values
    mask = rng.random(len(values)) < rate
    return [None if m else v for v, m in zip(values, mask)]


def inject_outliers(
    values: list[Any],
    field: FieldDefinition,
    rate: float,
    rng: np.random.Generator,
) -> list[Any]:
    """Inject realistic outlier values at the specified rate."""
    if rate <= 0 or field.data_type not in (DataType.INTEGER, DataType.FLOAT, DataType.CURRENCY):
        return values

    result = list(values)
    n_outliers = max(1, int(len(values) * rate))
    indices = rng.choice(len(values), n_outliers, replace=False)

    for idx in indices:
        v = result[idx]
        if v is None:
            continue
        try:
            numeric = float(v)
            # Generate outlier: 3-5x the value
            multiplier = rng.uniform(3.0, 5.0)
            if rng.random() < 0.5:
                multiplier = -multiplier  # Negative outlier
            outlier = round(numeric * multiplier, 2)
            result[idx] = int(outlier) if field.data_type == DataType.INTEGER else outlier
        except (ValueError, TypeError):
            pass

    return result


# ──────────────────────────── Edge Case Injection ────────────────────────────

def inject_edge_cases(
    df: pd.DataFrame,
    edge_cases: list[EdgeCase],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Inject enabled edge cases into random rows of the dataframe."""
    if not edge_cases:
        return df

    for ec in edge_cases:
        if not ec.enabled or not ec.field_target or ec.field_target not in df.columns:
            continue

        # Inject into 1-3 random rows
        n_inject = min(3, len(df))
        indices = rng.choice(len(df), n_inject, replace=False)

        for idx in indices:
            df.at[idx, ec.field_target] = ec.injection_value

    return df


# ──────────────────────────── Main Generation Function ────────────────────────────

def generate_tabular(
    table_def: TableDefinition,
    schema: SchemaDefinition,
    sample_df: Optional[pd.DataFrame] = None,
    edge_cases: Optional[list[EdgeCase]] = None,
    fk_values: Optional[dict[str, list[Any]]] = None,
) -> pd.DataFrame:
    """
    Generate synthetic tabular data preserving statistical properties.

    Args:
        table_def: Schema definition for the table
        schema: Parent schema with global settings
        sample_df: Optional real data sample for distribution fitting
        edge_cases: Optional edge cases to inject
        fk_values: Dict mapping FK column names to lists of valid parent key values
    """
    rng = np.random.default_rng(schema.seed)
    fake = _create_faker(schema.locale)
    Faker.seed(schema.seed)
    n = table_def.row_count

    # Build statistical profile from sample data
    profile: Optional[TableProfile] = None
    if sample_df is not None and len(sample_df) > 5:
        profile = TableProfile(sample_df, table_def)

    # Generate correlated uniform samples if we have a correlation matrix
    correlated_uniforms: Optional[np.ndarray] = None
    if profile and profile.correlation_matrix is not None and len(profile.numeric_columns) >= 2:
        correlated_uniforms = _gaussian_copula_sample(
            n, profile.correlation_matrix, rng
        )

    # Generate each column
    data: dict[str, list[Any]] = {}

    for col_idx, field in enumerate(table_def.fields):
        # Primary key: sequential IDs
        if field.is_primary_key and not field.is_foreign_key:
            data[field.name] = list(range(1, n + 1))
            continue

        # Foreign key: sample from parent values
        if field.is_foreign_key and fk_values and field.name in fk_values:
            parent_vals = fk_values[field.name]
            data[field.name] = rng.choice(parent_vals, n).tolist()
            continue

        # Get correlated uniform for this column if available
        col_uniform = None
        if correlated_uniforms is not None and field.name in (profile.numeric_columns if profile else []):
            num_idx = profile.numeric_columns.index(field.name)
            if num_idx < correlated_uniforms.shape[1]:
                col_uniform = correlated_uniforms[:, num_idx]

        # Get column profile
        col_profile = None
        if profile:
            col_profile = profile.column_profiles.get(field.name)

        # Generate values
        if (
            field.data_type == DataType.EMAIL
            and _is_pakistan_locale(schema.locale)
            and "name" in data
        ):
            email_counts: dict[str, int] = {}
            generated_emails = []
            for name in data["name"]:
                username = str(name).lower().replace(" ", ".")
                email_counts[username] = email_counts.get(username, 0) + 1
                suffix = email_counts[username]
                generated_emails.append(
                    f"{username}{suffix if suffix > 1 else ''}@example.com"
                )
            values = [
                email for email in generated_emails
            ]
        else:
            values = _generate_column_values(
                field, n, rng, fake, col_profile, col_uniform, schema.locale
            )

        # Apply outlier injection
        values = inject_outliers(values, field, schema.outlier_rate, rng)

        # Apply null injection
        null_rate = field.constraint.null_rate or schema.null_rate
        if field.constraint.nullable and null_rate > 0 and not field.is_primary_key:
            values = inject_nulls(values, null_rate, rng)

        # Apply privacy transforms
        values = apply_privacy(values, field.privacy)

        data[field.name] = values

    df = pd.DataFrame(data)

    # Inject edge cases
    if edge_cases:
        df = inject_edge_cases(df, edge_cases, rng)

    return df


# ──────────────────────────── Fidelity Metrics ────────────────────────────

def compute_fidelity_metrics(
    real_df: pd.DataFrame,
    synth_df: pd.DataFrame,
    table_def: TableDefinition,
) -> dict[str, Any]:
    """
    Compute fidelity metrics comparing real vs synthetic distributions.
    Returns per-column and overall metrics for the fidelity dashboard.
    """
    metrics: dict[str, Any] = {"columns": {}, "overall": {}}

    numeric_cols = []
    for field in table_def.fields:
        if field.data_type in (DataType.INTEGER, DataType.FLOAT, DataType.CURRENCY):
            if field.name in real_df.columns and field.name in synth_df.columns:
                numeric_cols.append(field.name)

    for col in numeric_cols:
        real_vals = pd.to_numeric(
            real_df[col].astype(str).str.replace(r"[$,£€]", "", regex=True),
            errors="coerce"
        ).dropna()
        synth_vals = pd.to_numeric(
            synth_df[col].astype(str).str.replace(r"[$,£€]", "", regex=True),
            errors="coerce"
        ).dropna()

        if len(real_vals) < 5 or len(synth_vals) < 5:
            continue

        # KS test (distribution similarity)
        ks_stat, ks_pval = sp_stats.ks_2samp(real_vals, synth_vals)

        # Mean/Std comparison
        mean_diff = abs(real_vals.mean() - synth_vals.mean()) / (real_vals.std() or 1)
        std_ratio = (synth_vals.std() or 1) / (real_vals.std() or 1)

        # Use a padded range for constant columns so density histograms remain finite.
        lower = min(float(real_vals.min()), float(synth_vals.min()))
        upper = max(float(real_vals.max()), float(synth_vals.max()))
        if lower == upper:
            padding = max(abs(lower) * 0.01, 0.5)
            lower -= padding
            upper += padding
        bin_edges = np.linspace(lower, upper, 21)
        real_hist, _ = np.histogram(real_vals, bins=bin_edges, density=True)
        synth_hist, _ = np.histogram(synth_vals, bins=bin_edges, density=True)

        metrics["columns"][col] = {
            "ks_statistic": round(float(ks_stat), 4),
            "ks_p_value": round(float(ks_pval), 4),
            "mean_real": round(float(real_vals.mean()), 2),
            "mean_synth": round(float(synth_vals.mean()), 2),
            "std_real": round(float(real_vals.std()), 2),
            "std_synth": round(float(synth_vals.std()), 2),
            "mean_deviation": round(float(mean_diff), 4),
            "std_ratio": round(float(std_ratio), 4),
            "real_histogram": real_hist.tolist(),
            "synth_histogram": synth_hist.tolist(),
            "bin_edges": bin_edges.tolist(),
        }

    # Categorical columns
    for field in table_def.fields:
        if field.data_type in (DataType.CATEGORY, DataType.BOOLEAN):
            col = field.name
            if col in real_df.columns and col in synth_df.columns:
                real_freq = real_df[col].value_counts(normalize=True).to_dict()
                synth_freq = synth_df[col].value_counts(normalize=True).to_dict()
                all_cats = set(real_freq.keys()) | set(synth_freq.keys())
                freq_diff = sum(
                    abs(real_freq.get(c, 0) - synth_freq.get(c, 0))
                    for c in all_cats
                ) / max(len(all_cats), 1)

                metrics["columns"][col] = {
                    "type": "categorical",
                    "real_frequencies": real_freq,
                    "synth_frequencies": synth_freq,
                    "avg_frequency_deviation": round(float(freq_diff), 4),
                }

    # Correlation preservation (for numeric cols)
    if len(numeric_cols) >= 2:
        real_numeric = real_df[numeric_cols].apply(
            lambda x: pd.to_numeric(x.astype(str).str.replace(r"[$,£€]", "", regex=True), errors="coerce")
        ).dropna()
        synth_numeric = synth_df[numeric_cols].apply(
            lambda x: pd.to_numeric(x.astype(str).str.replace(r"[$,£€]", "", regex=True), errors="coerce")
        ).dropna()

        if len(real_numeric) > 5 and len(synth_numeric) > 5:
            real_corr = real_numeric.corr().values
            synth_corr = synth_numeric.corr().values
            corr_diff = np.abs(real_corr - synth_corr).mean()
            metrics["overall"]["correlation_deviation"] = round(float(corr_diff), 4)
            metrics["overall"]["real_correlation"] = real_corr.tolist()
            metrics["overall"]["synth_correlation"] = synth_corr.tolist()

    if len(numeric_cols) < 2:
        metrics["overall"]["copula_status"] = "needs_two_numeric_columns"
    elif len(real_df) <= 5 or len(synth_df) <= 5:
        metrics["overall"]["copula_status"] = "needs_more_than_five_rows"
    elif "correlation_deviation" in metrics["overall"]:
        metrics["overall"]["copula_status"] = "measured"

    # Overall score (0-100, higher is better)
    col_scores = []
    for col, m in metrics["columns"].items():
        if "ks_statistic" in m:
            col_scores.append(max(0, 1 - m["ks_statistic"]))
        if "avg_frequency_deviation" in m:
            col_scores.append(max(0, 1 - m["avg_frequency_deviation"]))

    if col_scores:
        corr_bonus = 1 - metrics["overall"].get("correlation_deviation", 0.1)
        overall = (sum(col_scores) / len(col_scores)) * 0.7 + max(0, corr_bonus) * 0.3
        metrics["overall"]["fidelity_score"] = round(overall * 100, 1)
    else:
        metrics["overall"]["fidelity_score"] = 0

    return metrics
