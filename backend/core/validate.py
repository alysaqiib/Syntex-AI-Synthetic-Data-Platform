"""
Validation Module — automated TSTR readiness checker, referential integrity 
validator, and mathematical reconciliation tester.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

from backend.core.schema import SchemaDefinition, DataType
from backend.engines.relational import validate_referential_integrity
from backend.engines.tabular import compute_fidelity_metrics

logger = logging.getLogger(__name__)


def validate_tstr_readiness(
    synth_tables: dict[str, pd.DataFrame],
    schema: SchemaDefinition,
    real_tables: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    """
    Comprehensive validation of synthetic data quality.

    Checks:
    1. Referential integrity (zero orphans)
    2. Mathematical reconciliation (cross-table totals)
    3. Statistical fidelity (distribution preservation)
    4. Null rate compliance
    5. Unique constraint satisfaction
    6. Data type consistency
    """
    results = {
        "overall_status": "pass",
        "checks": [],
        "fidelity_metrics": {},
        "summary": {},
    }

    # ── Check 1: Referential Integrity ──
    if schema.relations:
        ri_result = validate_referential_integrity(synth_tables, schema)
        status = "pass" if ri_result["valid"] else "fail"
        results["checks"].append({
            "name": "Referential Integrity",
            "status": status,
            "icon": "✅" if status == "pass" else "❌",
            "details": ri_result["details"],
            "orphan_count": ri_result["orphan_count"],
        })
        if status == "fail":
            results["overall_status"] = "fail"
    else:
        results["checks"].append({
            "name": "Referential Integrity",
            "status": "skip",
            "icon": "⏭️",
            "details": "No relations defined",
        })

    # ── Check 2: Mathematical Reconciliation ──
    reconciliation_checks = []
    for table_def in schema.tables:
        df = synth_tables.get(table_def.name)
        if df is None:
            continue

        # Check for total columns that should reconcile with child line items
        total_field = None
        for field in table_def.fields:
            if field.data_type == DataType.CURRENCY and "total" in field.name.lower():
                total_field = field
                break

        if total_field is None:
            continue

        # Find child table with qty * price
        for rel in schema.relations:
            if rel.to_table == table_def.name:
                child_name = rel.from_table
                child_df = synth_tables.get(child_name)
                child_def = schema.get_table(child_name)
                if child_df is None or child_def is None:
                    continue

                qty_col = None
                price_col = None
                for cf in child_def.fields:
                    if "qty" in cf.name.lower() or "quantity" in cf.name.lower():
                        qty_col = cf.name
                    if "price" in cf.name.lower():
                        price_col = cf.name

                if qty_col and price_col:
                    # Verify reconciliation
                    child_df["_check_total"] = (
                        pd.to_numeric(child_df[qty_col], errors="coerce").fillna(0) *
                        pd.to_numeric(child_df[price_col], errors="coerce").fillna(0)
                    )
                    order_sums = child_df.groupby(rel.from_column)["_check_total"].sum()

                    mismatches = 0
                    for _, row in df.iterrows():
                        pk_val = row[rel.to_column]
                        expected = order_sums.get(pk_val, 0)
                        actual = pd.to_numeric(
                            str(row[total_field.name]).replace("$", "").replace(",", ""),
                            errors="coerce"
                        ) or 0

                        if abs(expected - actual) > 0.01:
                            mismatches += 1

                    child_df.drop(columns=["_check_total"], inplace=True, errors="ignore")

                    reconciliation_checks.append({
                        "parent": table_def.name,
                        "child": child_name,
                        "column": total_field.name,
                        "mismatches": mismatches,
                        "total_rows": len(df),
                        "status": "pass" if mismatches == 0 else "fail",
                    })

    if reconciliation_checks:
        all_pass = all(c["status"] == "pass" for c in reconciliation_checks)
        results["checks"].append({
            "name": "Mathematical Reconciliation",
            "status": "pass" if all_pass else "fail",
            "icon": "✅" if all_pass else "❌",
            "details": reconciliation_checks,
        })
        if not all_pass:
            results["overall_status"] = "fail"
    else:
        results["checks"].append({
            "name": "Mathematical Reconciliation",
            "status": "skip",
            "icon": "⏭️",
            "details": "No reconcilable total columns found",
        })

    # ── Check 3: Statistical Fidelity ──
    if real_tables:
        for table_def in schema.tables:
            if table_def.name in real_tables and table_def.name in synth_tables:
                metrics = compute_fidelity_metrics(
                    real_tables[table_def.name],
                    synth_tables[table_def.name],
                    table_def,
                )
                results["fidelity_metrics"][table_def.name] = metrics

                score = metrics.get("overall", {}).get("fidelity_score", 0)
                results["checks"].append({
                    "name": f"Statistical Fidelity — {table_def.name}",
                    "status": "pass" if score >= 70 else "warn" if score >= 50 else "fail",
                    "icon": "✅" if score >= 70 else "⚠️" if score >= 50 else "❌",
                    "fidelity_score": score,
                    "details": metrics.get("columns", {}),
                })
    else:
        results["checks"].append({
            "name": "Statistical Fidelity",
            "status": "skip",
            "icon": "⏭️",
            "details": "No real data provided for comparison",
        })

    # ── Check 4: Null Rate Compliance ──
    null_issues = []
    for table_def in schema.tables:
        df = synth_tables.get(table_def.name)
        if df is None:
            continue

        for field in table_def.fields:
            if field.name not in df.columns:
                continue

            actual_null_rate = float(df[field.name].isna().mean())

            if field.is_primary_key and actual_null_rate > 0:
                null_issues.append({
                    "table": table_def.name,
                    "column": field.name,
                    "issue": "Primary key contains nulls",
                    "null_rate": actual_null_rate,
                })

            if not field.constraint.nullable and actual_null_rate > 0:
                null_issues.append({
                    "table": table_def.name,
                    "column": field.name,
                    "issue": "Non-nullable column contains nulls",
                    "null_rate": actual_null_rate,
                })

    results["checks"].append({
        "name": "Null Constraint Compliance",
        "status": "pass" if not null_issues else "warn",
        "icon": "✅" if not null_issues else "⚠️",
        "issues": null_issues,
    })

    # ── Check 5: Unique Constraint Satisfaction ──
    unique_issues = []
    for table_def in schema.tables:
        df = synth_tables.get(table_def.name)
        if df is None:
            continue

        for field in table_def.fields:
            if field.name not in df.columns:
                continue

            if field.constraint.unique or field.is_primary_key:
                duplicates = df[field.name].duplicated().sum()
                if duplicates > 0:
                    unique_issues.append({
                        "table": table_def.name,
                        "column": field.name,
                        "duplicates": int(duplicates),
                    })

    results["checks"].append({
        "name": "Uniqueness Constraints",
        "status": "pass" if not unique_issues else "fail",
        "icon": "✅" if not unique_issues else "❌",
        "issues": unique_issues,
    })

    # ── Check 6: Row Count Verification ──
    row_checks = []
    for table_def in schema.tables:
        df = synth_tables.get(table_def.name)
        if df is not None:
            row_checks.append({
                "table": table_def.name,
                "expected": table_def.row_count,
                "actual": len(df),
                "match": len(df) == table_def.row_count,
            })

    results["checks"].append({
        "name": "Row Count Verification",
        "status": "pass" if all(r["match"] for r in row_checks) else "warn",
        "icon": "✅" if all(r["match"] for r in row_checks) else "⚠️",
        "details": row_checks,
    })

    # ── Summary ──
    pass_count = sum(1 for c in results["checks"] if c["status"] == "pass")
    fail_count = sum(1 for c in results["checks"] if c["status"] == "fail")
    warn_count = sum(1 for c in results["checks"] if c["status"] == "warn")
    skip_count = sum(1 for c in results["checks"] if c["status"] == "skip")

    results["summary"] = {
        "total_checks": len(results["checks"]),
        "passed": pass_count,
        "failed": fail_count,
        "warnings": warn_count,
        "skipped": skip_count,
    }

    if fail_count > 0:
        results["overall_status"] = "fail"
    elif warn_count > 0:
        results["overall_status"] = "warn"

    return results


def validate_document_reconciliation(recon_data: list[dict]) -> dict[str, Any]:
    """Validate document generation reconciliation."""
    results = {
        "valid": True,
        "checks": [],
    }

    for doc in recon_data:
        if "grand_total" in doc:
            # Invoice reconciliation
            line_sum = sum(item["total"] for item in doc.get("line_items", []))
            subtotal_match = abs(line_sum - doc.get("subtotal", 0)) < 0.01
            tax_check = abs(
                doc.get("subtotal", 0) * doc.get("tax_rate", 0) - doc.get("tax_amount", 0)
            ) < 0.01
            total_check = abs(
                doc.get("subtotal", 0) + doc.get("tax_amount", 0) - doc.get("grand_total", 0)
            ) < 0.01

            check = {
                "document": doc.get("invoice_number", "unknown"),
                "type": "invoice",
                "subtotal_match": subtotal_match,
                "tax_calculation_correct": tax_check,
                "total_correct": total_check,
                "status": "pass" if all([subtotal_match, tax_check, total_check]) else "fail",
            }
            results["checks"].append(check)
            if check["status"] == "fail":
                results["valid"] = False

        elif "closing_balance" in doc:
            # Bank statement reconciliation
            balance_check = doc.get("balance_check", False)
            math_check = abs(
                doc.get("opening_balance", 0) -
                doc.get("total_debits", 0) +
                doc.get("total_credits", 0) -
                doc.get("closing_balance", 0)
            ) < 0.01

            check = {
                "document": f"Statement - {doc.get('account_holder', 'unknown')}",
                "type": "bank_statement",
                "balance_reconciled": balance_check,
                "math_verified": math_check,
                "status": "pass" if balance_check and math_check else "fail",
            }
            results["checks"].append(check)
            if check["status"] == "fail":
                results["valid"] = False

    return results
