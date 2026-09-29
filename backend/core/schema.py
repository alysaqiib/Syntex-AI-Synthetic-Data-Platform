"""
Schema Models — defines the universal schema representation for all engines.
Handles ingestion from CSV samples, JSON schemas, and SQL DDL.
"""

from __future__ import annotations
import io
import re
import csv
import json
import hashlib
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# ──────────────────────────── Enums ────────────────────────────

class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    EMAIL = "email"
    PHONE = "phone"
    CURRENCY = "currency"
    ADDRESS = "address"
    NAME = "name"
    TEXT = "text"
    UUID = "uuid"
    URL = "url"
    CATEGORY = "category"


class Cardinality(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_MANY = "N:N"


class PrivacyTransform(str, Enum):
    NONE = "none"
    MASK = "mask"
    HASH_SHA256 = "hash_sha256"
    LAPLACE_NOISE = "laplace_noise"
    REDACT = "redact"


# ──────────────────────────── Field & Table Models ────────────────────────────

class FieldConstraint(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    allowed_values: Optional[list[str]] = None
    unique: bool = False
    nullable: bool = False
    null_rate: float = Field(default=0.0, ge=0.0, le=1.0)


class FieldDefinition(BaseModel):
    name: str
    data_type: DataType = DataType.STRING
    semantic_type: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    fk_reference_table: Optional[str] = None
    fk_reference_column: Optional[str] = None
    constraint: FieldConstraint = Field(default_factory=FieldConstraint)
    privacy: PrivacyTransform = PrivacyTransform.NONE
    privacy_transform: Optional[str] = None
    description: Optional[str] = None
    sample_values: list[Any] = Field(default_factory=list)

    # Statistical profile (populated after CSV ingestion)
    stats: dict[str, Any] = Field(default_factory=dict)

    @field_validator("privacy", mode="before")
    @classmethod
    def normalize_privacy(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_low = v.lower().strip()
            alias_map = {
                "differential_privacy": "laplace_noise",
                "laplace": "laplace_noise",
                "laplace_noise": "laplace_noise",
                "generalize": "redact",
                "redact": "redact",
                "pseudonymize": "hash_sha256",
                "hash": "hash_sha256",
                "hash_sha256": "hash_sha256",
                "mask": "mask",
                "none": "none",
            }
            return alias_map.get(v_low, v_low)
        return v

    def model_post_init(self, __context: Any) -> None:
        if self.privacy_transform and self.privacy == PrivacyTransform.NONE:
            normalized = self.normalize_privacy(self.privacy_transform)
            try:
                self.privacy = PrivacyTransform(normalized)
            except Exception:
                pass


class ForeignKeyRelation(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    cardinality: Cardinality = Cardinality.ONE_TO_MANY
    min_children: int = Field(default=1, ge=0)
    max_children: int = Field(default=5, ge=1)


class TableDefinition(BaseModel):
    name: str
    fields: list[FieldDefinition]
    row_count: int = Field(default=100, ge=1, le=100000)
    description: Optional[str] = None

    @property
    def primary_keys(self) -> list[FieldDefinition]:
        return [f for f in self.fields if f.is_primary_key]

    @property
    def foreign_keys(self) -> list[FieldDefinition]:
        return [f for f in self.fields if f.is_foreign_key]

    def get_field(self, name: str) -> Optional[FieldDefinition]:
        for f in self.fields:
            if f.name == name:
                return f
        return None


class SchemaDefinition(BaseModel):
    """Top-level schema model containing one or more tables and their relations."""
    tables: list[TableDefinition]
    relations: list[ForeignKeyRelation] = Field(default_factory=list)
    seed: int = Field(default=42)
    null_rate: float = Field(default=0.02, ge=0.0, le=0.5)
    outlier_rate: float = Field(default=0.01, ge=0.0, le=0.2)
    locale: str = "en_US"

    def get_table(self, name: str) -> Optional[TableDefinition]:
        for t in self.tables:
            if t.name == name:
                return t
        return None


# ──────────────────────────── Document Models ────────────────────────────

class TaxRegion(str, Enum):
    US = "us_sales_tax"
    UK_EU = "uk_eu_vat"
    EU = "eu_vat_20"
    UK = "uk_vat_20"
    CA = "ca_gst_pst"
    PK = "pk_gst"
    NONE = "none"


class InvoiceLineItem(BaseModel):
    product_name: str
    quantity: int = Field(ge=1)
    unit_price: float = Field(ge=0.01)

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class InvoiceConfig(BaseModel):
    count: int = Field(default=1, ge=1, le=200)
    tax_region: TaxRegion = TaxRegion.US
    tax_rate: Optional[float] = None  # override auto rate
    min_line_items: int = Field(default=2, ge=1, le=20)
    max_line_items: int = Field(default=6, ge=1, le=20)
    currency_symbol: str = "$"
    locale: str = "en_US"
    seed: int = 42

    @field_validator("tax_region", mode="before")
    @classmethod
    def normalize_tax_region(cls, v: Any) -> Any:
        if isinstance(v, str):
            v_low = v.lower().strip()
            alias_map = {
                "eu_vat_20": TaxRegion.EU,
                "uk_vat_20": TaxRegion.UK,
                "ca_gst_pst": TaxRegion.CA,
                "us_sales_tax": TaxRegion.US,
                "uk_eu_vat": TaxRegion.UK_EU,
                "pk_gst": TaxRegion.PK,
                "none": TaxRegion.NONE,
            }
            return alias_map.get(v_low, v)
        return v


class BankStatementConfig(BaseModel):
    count: int = Field(default=1, ge=1, le=200)
    opening_balance: float = Field(default=1000.0)
    num_transactions: int = Field(default=30, ge=5, le=200)
    days_span: int = Field(default=30, ge=7, le=365)
    include_large_refunds: int = Field(default=0, ge=0, le=10)
    currency_symbol: str = "$"
    locale: str = "en_US"
    seed: int = 42


class DocumentRequest(BaseModel):
    doc_type: str = "invoice"  # "invoice" or "bank_statement"
    invoice_config: Optional[InvoiceConfig] = None
    statement_config: Optional[BankStatementConfig] = None
    natural_language_query: Optional[str] = None


# ──────────────────────────── Edge Case Models ────────────────────────────

class EdgeCase(BaseModel):
    id: str
    category: str
    description: str
    enabled: bool = True
    field_target: Optional[str] = None
    injection_value: Optional[Any] = None


# ──────────────────────────── Generation Config ────────────────────────────

class GenerationConfig(BaseModel):
    """Unified configuration for a synthetic data generation request."""
    schema_def: SchemaDefinition
    edge_cases: list[EdgeCase] = Field(default_factory=list)
    use_ai: bool = True
    ai_provider: str = "gemini"  # "gemini", "groq", or "offline"
    export_format: str = "csv"  # "csv", "json", "sql", "zip"


# ──────────────────────────── Schema Ingestors ────────────────────────────

# Map of common column names -> semantic data types
SEMANTIC_HINTS: dict[str, DataType] = {
    "name": DataType.NAME, "first_name": DataType.NAME, "last_name": DataType.NAME,
    "full_name": DataType.NAME, "customer_name": DataType.NAME,
    "email": DataType.EMAIL, "email_address": DataType.EMAIL,
    "phone": DataType.PHONE, "phone_number": DataType.PHONE, "telephone": DataType.PHONE,
    "address": DataType.ADDRESS, "street": DataType.ADDRESS, "city": DataType.ADDRESS,
    "price": DataType.CURRENCY, "amount": DataType.CURRENCY, "total": DataType.CURRENCY,
    "cost": DataType.CURRENCY, "salary": DataType.CURRENCY, "revenue": DataType.CURRENCY,
    "unit_price": DataType.CURRENCY, "balance": DataType.CURRENCY,
    "date": DataType.DATE, "created_at": DataType.DATETIME, "updated_at": DataType.DATETIME,
    "order_date": DataType.DATE, "birth_date": DataType.DATE, "dob": DataType.DATE,
    "timestamp": DataType.DATETIME,
    "url": DataType.URL, "website": DataType.URL, "link": DataType.URL,
    "id": DataType.INTEGER, "uuid": DataType.UUID,
    "description": DataType.TEXT, "bio": DataType.TEXT, "notes": DataType.TEXT,
    "category": DataType.CATEGORY, "type": DataType.CATEGORY, "status": DataType.CATEGORY,
    "is_active": DataType.BOOLEAN, "active": DataType.BOOLEAN, "verified": DataType.BOOLEAN,
}


def _sanitize_csv_cell(value: str) -> str:
    """Neutralize formula injection characters in CSV cells."""
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def infer_data_type(column_name: str, sample_values: list[str]) -> DataType:
    """Infer DataType from column name hints and sample values."""
    col_lower = column_name.lower().strip().replace(" ", "_")

    # Check semantic hints first
    for hint_key, hint_type in SEMANTIC_HINTS.items():
        if hint_key in col_lower:
            return hint_type

    # Check if column ends with common suffixes
    if col_lower.endswith("_id"):
        return DataType.INTEGER

    # Analyze sample values
    clean = [v for v in sample_values if v and v.strip()]
    if not clean:
        return DataType.STRING

    # Check for boolean
    bool_vals = {"true", "false", "yes", "no", "0", "1"}
    if all(v.lower().strip() in bool_vals for v in clean[:20]):
        return DataType.BOOLEAN

    # Check for integer
    try:
        [int(v.replace(",", "")) for v in clean[:20]]
        return DataType.INTEGER
    except (ValueError, TypeError):
        pass

    # Check for float/currency
    try:
        [float(v.replace(",", "").replace("$", "").replace("£", "").replace("€", "")) for v in clean[:20]]
        return DataType.FLOAT
    except (ValueError, TypeError):
        pass

    # Check for date patterns
    date_patterns = [
        r"\d{4}-\d{2}-\d{2}", r"\d{2}/\d{2}/\d{4}", r"\d{2}-\d{2}-\d{4}"
    ]
    if any(re.match(p, clean[0].strip()) for p in date_patterns):
        return DataType.DATE

    # Check for email
    if any("@" in v and "." in v for v in clean[:5]):
        return DataType.EMAIL

    # Preserve low-cardinality string dimensions such as plan, tier, or region.
    unique_values = set(clean)
    if 1 < len(unique_values) <= 20:
        return DataType.CATEGORY

    # Default
    avg_len = sum(len(v) for v in clean[:20]) / len(clean[:20])
    if avg_len > 80:
        return DataType.TEXT

    return DataType.STRING


def ingest_csv(file_content: str | bytes, table_name: str = "table_1") -> TableDefinition:
    """Parse a CSV file from memory and produce a TableDefinition with stats."""
    import pandas as pd
    import numpy as np

    if isinstance(file_content, bytes):
        file_content = file_content.decode("utf-8", errors="replace")

    # Sanitize
    lines = file_content.splitlines()
    sanitized_lines = []
    for line in lines:
        reader = csv.reader(io.StringIO(line))
        for row in reader:
            sanitized_lines.append([_sanitize_csv_cell(cell) for cell in row])

    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in sanitized_lines:
        writer.writerow(row)
    buf.seek(0)

    df = pd.read_csv(buf)

    fields = []
    for col in df.columns:
        sample_vals = df[col].dropna().astype(str).head(50).tolist()
        dtype = infer_data_type(col, sample_vals)

        stats: dict[str, Any] = {}
        if dtype in (DataType.INTEGER, DataType.FLOAT, DataType.CURRENCY):
            numeric_col = pd.to_numeric(
                df[col].astype(str).str.replace(r"[$,£€]", "", regex=True),
                errors="coerce"
            )
            stats = {
                "mean": float(numeric_col.mean()) if not numeric_col.isna().all() else 0,
                "std": float(numeric_col.std()) if not numeric_col.isna().all() else 1,
                "min": float(numeric_col.min()) if not numeric_col.isna().all() else 0,
                "max": float(numeric_col.max()) if not numeric_col.isna().all() else 0,
                "q25": float(numeric_col.quantile(0.25)) if not numeric_col.isna().all() else 0,
                "q50": float(numeric_col.quantile(0.50)) if not numeric_col.isna().all() else 0,
                "q75": float(numeric_col.quantile(0.75)) if not numeric_col.isna().all() else 0,
                "null_rate": float(df[col].isna().mean()),
            }
        elif dtype == DataType.CATEGORY:
            vc = df[col].value_counts(normalize=True).head(20)
            stats = {
                "categories": vc.index.tolist(),
                "frequencies": vc.values.tolist(),
                "null_rate": float(df[col].isna().mean()),
            }
        else:
            stats = {
                "null_rate": float(df[col].isna().mean()),
                "unique_count": int(df[col].nunique()),
                "avg_length": float(df[col].astype(str).str.len().mean()),
            }

        is_pk = (
            col.lower().endswith("_id") and df[col].nunique() == len(df)
        ) or col.lower() == "id"

        fields.append(FieldDefinition(
            name=col,
            data_type=dtype,
            is_primary_key=is_pk,
            sample_values=sample_vals[:10],
            stats=stats,
            constraint=FieldConstraint(
                nullable=df[col].isna().any(),
                null_rate=float(df[col].isna().mean()),
            )
        ))

    return TableDefinition(name=table_name, fields=fields, row_count=len(df))


def ingest_json_schema(json_str: str, table_name: str = "table_1") -> TableDefinition:
    """Parse a JSON schema definition into a TableDefinition."""
    data = json.loads(json_str)

    if "fields" in data:
        fields = []
        for fd in data["fields"]:
            fields.append(FieldDefinition(
                name=fd["name"],
                data_type=DataType(fd.get("data_type", "string")),
                is_primary_key=fd.get("is_primary_key", False),
                is_foreign_key=fd.get("is_foreign_key", False),
                fk_reference_table=fd.get("fk_reference_table"),
                fk_reference_column=fd.get("fk_reference_column"),
                constraint=FieldConstraint(**fd.get("constraint", {})),
                privacy=PrivacyTransform(fd.get("privacy", "none")),
                description=fd.get("description"),
                sample_values=fd.get("sample_values", []),
            ))
        return TableDefinition(
            name=data.get("name", table_name),
            fields=fields,
            row_count=data.get("row_count", 100),
            description=data.get("description"),
        )

    # Auto-infer from flat key/value sample
    fields = []
    for key, val in data.items():
        dtype = infer_data_type(key, [str(val)])
        fields.append(FieldDefinition(name=key, data_type=dtype))
    return TableDefinition(name=table_name, fields=fields)


def ingest_sql_ddl(ddl: str) -> list[TableDefinition]:
    """Parse SQL DDL CREATE TABLE statements into TableDefinitions."""
    tables = []
    # Match CREATE TABLE blocks
    create_re = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\((.*?)\)\s*;",
        re.IGNORECASE | re.DOTALL
    )

    type_map = {
        "int": DataType.INTEGER, "integer": DataType.INTEGER, "bigint": DataType.INTEGER,
        "smallint": DataType.INTEGER, "tinyint": DataType.INTEGER, "serial": DataType.INTEGER,
        "float": DataType.FLOAT, "double": DataType.FLOAT, "decimal": DataType.FLOAT,
        "numeric": DataType.FLOAT, "real": DataType.FLOAT, "money": DataType.CURRENCY,
        "varchar": DataType.STRING, "char": DataType.STRING, "text": DataType.TEXT,
        "nvarchar": DataType.STRING,
        "bool": DataType.BOOLEAN, "boolean": DataType.BOOLEAN,
        "date": DataType.DATE, "datetime": DataType.DATETIME, "timestamp": DataType.DATETIME,
        "uuid": DataType.UUID,
    }

    for match in create_re.finditer(ddl):
        tbl_name = match.group(1)
        body = match.group(2)

        fields = []
        fk_relations = []

        # Parse columns and table-level constraints
        for line in body.split(","):
            line = line.strip()
            if not line:
                continue

            # Table-level FK constraint
            fk_match = re.match(
                r"(?:CONSTRAINT\s+\w+\s+)?FOREIGN\s+KEY\s*\((\w+)\)\s*REFERENCES\s+(\w+)\s*\((\w+)\)",
                line, re.IGNORECASE
            )
            if fk_match:
                fk_col, ref_tbl, ref_col = fk_match.groups()
                # Update the field
                for f in fields:
                    if f.name == fk_col:
                        f.is_foreign_key = True
                        f.fk_reference_table = ref_tbl
                        f.fk_reference_column = ref_col
                fk_relations.append(ForeignKeyRelation(
                    from_table=tbl_name, from_column=fk_col,
                    to_table=ref_tbl, to_column=ref_col,
                ))
                continue

            # Table-level PK constraint
            pk_match = re.match(
                r"(?:CONSTRAINT\s+\w+\s+)?PRIMARY\s+KEY\s*\((.+?)\)", line, re.IGNORECASE
            )
            if pk_match:
                pk_cols = [c.strip().strip("`\"") for c in pk_match.group(1).split(",")]
                for f in fields:
                    if f.name in pk_cols:
                        f.is_primary_key = True
                continue

            # Column definition
            col_match = re.match(
                r"[`\"]?(\w+)[`\"]?\s+(\w+)(?:\([\d,]+\))?(.*)$", line, re.IGNORECASE
            )
            if col_match:
                col_name = col_match.group(1)
                col_type_str = col_match.group(2).lower()
                col_rest = col_match.group(3).upper()

                dtype = type_map.get(col_type_str, DataType.STRING)
                # Override with semantic hints
                semantic = SEMANTIC_HINTS.get(col_name.lower())
                if semantic:
                    dtype = semantic

                is_pk = "PRIMARY KEY" in col_rest or "AUTOINCREMENT" in col_rest
                is_nullable = "NOT NULL" not in col_rest
                is_unique = "UNIQUE" in col_rest

                fields.append(FieldDefinition(
                    name=col_name,
                    data_type=dtype,
                    is_primary_key=is_pk,
                    constraint=FieldConstraint(nullable=is_nullable, unique=is_unique or is_pk),
                ))

        tables.append(TableDefinition(name=tbl_name, fields=fields))

    return tables


# ──────────────────────────── Presets ────────────────────────────

def get_ecommerce_preset() -> SchemaDefinition:
    """Return the default e-commerce relational preset."""
    customers = TableDefinition(
        name="customers",
        fields=[
            FieldDefinition(name="customer_id", data_type=DataType.INTEGER, is_primary_key=True,
                            constraint=FieldConstraint(unique=True)),
            FieldDefinition(name="name", data_type=DataType.NAME),
            FieldDefinition(name="email", data_type=DataType.EMAIL),
            FieldDefinition(name="phone", data_type=DataType.PHONE,
                            constraint=FieldConstraint(nullable=True, null_rate=0.1)),
            FieldDefinition(name="city", data_type=DataType.ADDRESS),
            FieldDefinition(name="signup_date", data_type=DataType.DATE),
        ],
        row_count=50,
        description="Customer master table",
    )

    orders = TableDefinition(
        name="orders",
        fields=[
            FieldDefinition(name="order_id", data_type=DataType.INTEGER, is_primary_key=True,
                            constraint=FieldConstraint(unique=True)),
            FieldDefinition(name="customer_id", data_type=DataType.INTEGER,
                            is_foreign_key=True, fk_reference_table="customers",
                            fk_reference_column="customer_id"),
            FieldDefinition(name="order_date", data_type=DataType.DATE),
            FieldDefinition(name="status", data_type=DataType.CATEGORY,
                            constraint=FieldConstraint(
                                allowed_values=["pending", "shipped", "delivered", "cancelled"])),
            FieldDefinition(name="total_amount", data_type=DataType.CURRENCY),
        ],
        row_count=150,
        description="Order headers",
    )

    order_items = TableDefinition(
        name="order_items",
        fields=[
            FieldDefinition(name="item_id", data_type=DataType.INTEGER, is_primary_key=True,
                            constraint=FieldConstraint(unique=True)),
            FieldDefinition(name="order_id", data_type=DataType.INTEGER,
                            is_foreign_key=True, fk_reference_table="orders",
                            fk_reference_column="order_id"),
            FieldDefinition(name="product_name", data_type=DataType.STRING),
            FieldDefinition(name="quantity", data_type=DataType.INTEGER,
                            constraint=FieldConstraint(min_value=1, max_value=20)),
            FieldDefinition(name="unit_price", data_type=DataType.CURRENCY,
                            constraint=FieldConstraint(min_value=0.99, max_value=999.99)),
        ],
        row_count=400,
        description="Order line items — each row belongs to exactly one order",
    )

    relations = [
        ForeignKeyRelation(
            from_table="orders", from_column="customer_id",
            to_table="customers", to_column="customer_id",
            cardinality=Cardinality.ONE_TO_MANY, min_children=1, max_children=5,
        ),
        ForeignKeyRelation(
            from_table="order_items", from_column="order_id",
            to_table="orders", to_column="order_id",
            cardinality=Cardinality.ONE_TO_MANY, min_children=1, max_children=6,
        ),
    ]

    return SchemaDefinition(tables=[customers, orders, order_items], relations=relations)


def get_hr_preset() -> SchemaDefinition:
    """Return an HR department preset schema."""
    departments = TableDefinition(
        name="departments",
        fields=[
            FieldDefinition(name="dept_id", data_type=DataType.INTEGER, is_primary_key=True,
                            constraint=FieldConstraint(unique=True)),
            FieldDefinition(name="dept_name", data_type=DataType.STRING),
            FieldDefinition(name="location", data_type=DataType.ADDRESS),
        ],
        row_count=10,
    )

    employees = TableDefinition(
        name="employees",
        fields=[
            FieldDefinition(name="employee_id", data_type=DataType.INTEGER, is_primary_key=True,
                            constraint=FieldConstraint(unique=True)),
            FieldDefinition(name="name", data_type=DataType.NAME),
            FieldDefinition(name="email", data_type=DataType.EMAIL),
            FieldDefinition(name="dept_id", data_type=DataType.INTEGER,
                            is_foreign_key=True, fk_reference_table="departments",
                            fk_reference_column="dept_id"),
            FieldDefinition(name="salary", data_type=DataType.CURRENCY,
                            constraint=FieldConstraint(min_value=30000, max_value=200000)),
            FieldDefinition(name="hire_date", data_type=DataType.DATE),
            FieldDefinition(name="is_active", data_type=DataType.BOOLEAN),
        ],
        row_count=100,
    )

    return SchemaDefinition(
        tables=[departments, employees],
        relations=[
            ForeignKeyRelation(
                from_table="employees", from_column="dept_id",
                to_table="departments", to_column="dept_id",
                cardinality=Cardinality.ONE_TO_MANY, min_children=5, max_children=20,
            ),
        ],
    )
