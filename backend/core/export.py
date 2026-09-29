"""
Export Module — multi-format exporters for CSV, JSON, SQL dump, PDF, and bulk ZIP.
All exports are streamed in-memory (zero disk persistence).
"""

from __future__ import annotations

import io
import csv
import json
import zipfile
from typing import Any

import pandas as pd

from backend.core.schema import SchemaDefinition


def export_csv(df: pd.DataFrame, table_name: str = "data") -> bytes:
    """Export a DataFrame as CSV bytes."""
    buf = io.StringIO()
    df.to_csv(buf, index=False, quoting=csv.QUOTE_ALL)
    return buf.getvalue().encode("utf-8")


def export_json(tables: dict[str, pd.DataFrame]) -> bytes:
    """Export all tables as a combined JSON document."""
    data = {}
    for name, df in tables.items():
        data[name] = df.to_dict(orient="records")
    return json.dumps(data, indent=2, default=str).encode("utf-8")


def _sql_type(dtype_str: str) -> str:
    """Map DataType to SQL type."""
    mapping = {
        "integer": "INTEGER",
        "float": "REAL",
        "currency": "DECIMAL(12,2)",
        "boolean": "BOOLEAN",
        "date": "DATE",
        "datetime": "TIMESTAMP",
        "text": "TEXT",
        "uuid": "VARCHAR(36)",
    }
    return mapping.get(dtype_str, "VARCHAR(255)")


def export_sql(tables: dict[str, pd.DataFrame], schema: SchemaDefinition) -> bytes:
    """Export as SQL DDL + DML dump."""
    lines: list[str] = []
    lines.append("-- Synthetic Data Platform — SQL Export")
    lines.append("-- Generated for HackDataV2 AI Hackathon\n")

    # DDL: CREATE TABLE statements
    for table_def in schema.tables:
        cols = []
        pks = []
        fks = []

        for field in table_def.fields:
            col_sql = f"  {field.name} {_sql_type(field.data_type.value)}"
            if not field.constraint.nullable and not field.is_foreign_key:
                col_sql += " NOT NULL"
            if field.constraint.unique:
                col_sql += " UNIQUE"
            cols.append(col_sql)

            if field.is_primary_key:
                pks.append(field.name)

            if field.is_foreign_key and field.fk_reference_table:
                fks.append(
                    f"  FOREIGN KEY ({field.name}) REFERENCES "
                    f"{field.fk_reference_table}({field.fk_reference_column})"
                )

        if pks:
            cols.append(f"  PRIMARY KEY ({', '.join(pks)})")

        cols.extend(fks)

        lines.append(f"CREATE TABLE IF NOT EXISTS {table_def.name} (")
        lines.append(",\n".join(cols))
        lines.append(");\n")

    # DML: INSERT statements
    for table_def in schema.tables:
        df = tables.get(table_def.name)
        if df is None or len(df) == 0:
            continue

        lines.append(f"\n-- Data for {table_def.name}")
        col_names = ", ".join(df.columns)

        for _, row in df.iterrows():
            values = []
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    values.append("NULL")
                elif isinstance(val, (int, float)):
                    values.append(str(val))
                else:
                    escaped = str(val).replace("'", "''")
                    values.append(f"'{escaped}'")

            lines.append(
                f"INSERT INTO {table_def.name} ({col_names}) VALUES ({', '.join(values)});"
            )

    lines.append("\n-- End of export")
    return "\n".join(lines).encode("utf-8")


def export_zip(
    tables: dict[str, pd.DataFrame],
    schema: SchemaDefinition,
    pdfs: list[bytes] | None = None,
    pdf_prefix: str = "document",
    recon_data: list[dict] | None = None,
) -> bytes:
    """
    Export everything into a single ZIP archive.
    Includes: individual CSVs, combined JSON, SQL dump, PDFs, and reconciliation ledger.
    """
    buf = io.BytesIO()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # CSV files
        for name, df in tables.items():
            csv_bytes = export_csv(df, name)
            zf.writestr(f"csv/{name}.csv", csv_bytes)

        # Combined JSON
        json_bytes = export_json(tables)
        zf.writestr("data.json", json_bytes)

        # SQL dump
        sql_bytes = export_sql(tables, schema)
        zf.writestr("schema_and_data.sql", sql_bytes)

        # PDF documents
        if pdfs:
            for i, pdf_bytes in enumerate(pdfs):
                zf.writestr(f"documents/{pdf_prefix}_{i+1:04d}.pdf", pdf_bytes)

        # Reconciliation ledger
        if recon_data:
            recon_json = json.dumps(recon_data, indent=2, default=str).encode("utf-8")
            zf.writestr("reconciliation_ledger.json", recon_json)

            # Also export as CSV
            if recon_data and "grand_total" in recon_data[0]:
                # Invoice reconciliation
                rows = []
                for r in recon_data:
                    rows.append({
                        "invoice_number": r.get("invoice_number"),
                        "date": r.get("date"),
                        "client": r.get("client"),
                        "num_items": r.get("num_items"),
                        "subtotal": r.get("subtotal"),
                        "tax_amount": r.get("tax_amount"),
                        "grand_total": r.get("grand_total"),
                    })
                recon_df = pd.DataFrame(rows)
                zf.writestr(
                    "reconciliation_ledger.csv",
                    export_csv(recon_df, "reconciliation")
                )
            elif recon_data and "closing_balance" in recon_data[0]:
                # Statement reconciliation
                rows = []
                for r in recon_data:
                    rows.append({
                        "account_holder": r.get("account_holder"),
                        "period_start": r.get("period_start"),
                        "period_end": r.get("period_end"),
                        "opening_balance": r.get("opening_balance"),
                        "closing_balance": r.get("closing_balance"),
                        "total_debits": r.get("total_debits"),
                        "total_credits": r.get("total_credits"),
                        "balance_check": r.get("balance_check"),
                    })
                recon_df = pd.DataFrame(rows)
                zf.writestr(
                    "reconciliation_ledger.csv",
                    export_csv(recon_df, "reconciliation")
                )

    return buf.getvalue()
