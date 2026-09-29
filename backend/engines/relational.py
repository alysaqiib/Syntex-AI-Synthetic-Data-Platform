"""
Relational Generation Engine — generates multi-table synthetic data 
with strict referential integrity, topological dependency resolution,
and cross-table mathematical consistency.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Optional

import numpy as np
import pandas as pd

from backend.core.schema import (
    SchemaDefinition, TableDefinition, ForeignKeyRelation, Cardinality,
    DataType, EdgeCase
)
from backend.engines.tabular import generate_tabular

logger = logging.getLogger(__name__)


# ──────────────────────────── Topological Sort ────────────────────────────

def topological_sort(tables: list[TableDefinition], relations: list[ForeignKeyRelation]) -> list[str]:
    """
    Topologically sort tables so parents are generated before children.
    Returns table names in generation order.
    """
    # Build adjacency: child -> parents
    graph: dict[str, set[str]] = {t.name: set() for t in tables}
    for rel in relations:
        # from_table depends on to_table (child depends on parent)
        if rel.from_table in graph:
            graph[rel.from_table].add(rel.to_table)
        # Ensure parent exists in graph
        if rel.to_table not in graph:
            graph[rel.to_table] = set()

    # Kahn's algorithm
    in_degree = {node: len(deps) for node, deps in graph.items()}
    queue = [node for node, deg in in_degree.items() if deg == 0]
    order = []

    while queue:
        node = queue.pop(0)
        order.append(node)
        for other, deps in graph.items():
            if node in deps:
                deps.remove(node)
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)

    if len(order) != len(graph):
        # Cycle detected — return original order with warning
        logger.warning("Circular dependency detected in schema relations — using declaration order")
        return [t.name for t in tables]

    return order


# ──────────────────────────── Cardinality-Aware FK Generation ────────────────────────────

def generate_fk_values(
    parent_keys: list[Any],
    child_count: int,
    relation: ForeignKeyRelation,
    rng: np.random.Generator,
) -> list[Any]:
    """
    Generate foreign key values respecting cardinality constraints.

    For 1:N, each parent gets between min_children and max_children references.
    For 1:1, each parent gets exactly one reference.
    """
    if not parent_keys:
        return list(range(1, child_count + 1))

    if relation.cardinality == Cardinality.ONE_TO_ONE:
        # Each parent maps to exactly one child
        n = min(child_count, len(parent_keys))
        selected = rng.choice(parent_keys, n, replace=False).tolist()
        # Pad if needed
        while len(selected) < child_count:
            selected.append(rng.choice(parent_keys))
        return selected[:child_count]

    if relation.cardinality == Cardinality.ONE_TO_MANY:
        min_c = max(1, relation.min_children)
        max_c = max(min_c, relation.max_children)

        # Reserve the minimum assignment first so trimming cannot orphan a parent.
        mandatory = [pk for pk in parent_keys for _ in range(min_c)]
        if len(mandatory) > child_count:
            mandatory = [pk for pk in parent_keys[:child_count]]
        fk_values = list(mandatory)
        remaining = child_count - len(fk_values)
        if remaining > 0:
            child_capacity = {
                pk: min_c for pk in parent_keys
            }
            extras = []
            for _ in range(remaining):
                eligible = [pk for pk in parent_keys if child_capacity[pk] < max_c]
                if not eligible:
                    break
                selected = eligible[int(rng.integers(0, len(eligible)))]
                child_capacity[selected] += 1
                extras.append(selected)
            fk_values.extend(extras)
        if len(fk_values) < child_count:
            fk_values.extend(rng.choice(parent_keys, child_count - len(fk_values)).tolist())

        rng.shuffle(fk_values)
        return fk_values

    # MANY_TO_MANY: generate via junction (handled separately)
    return rng.choice(parent_keys, child_count).tolist()


# ──────────────────────────── Cross-Table Reconciliation ────────────────────────────

def reconcile_order_totals(
    orders_df: pd.DataFrame,
    items_df: pd.DataFrame,
    order_id_col: str = "order_id",
    total_col: str = "total_amount",
    qty_col: str = "quantity",
    price_col: str = "unit_price",
) -> pd.DataFrame:
    """
    Ensure order totals exactly equal the sum of (qty * unit_price) for their line items.
    Modifies and returns the orders dataframe.
    """
    if total_col not in orders_df.columns:
        return orders_df
    if qty_col not in items_df.columns or price_col not in items_df.columns:
        return orders_df

    # Compute line item totals
    items_df["_line_total"] = (
        pd.to_numeric(items_df[qty_col], errors="coerce").fillna(0) *
        pd.to_numeric(items_df[price_col], errors="coerce").fillna(0)
    )

    # Sum by order
    order_sums = items_df.groupby(order_id_col)["_line_total"].sum().reset_index()
    order_sums.columns = [order_id_col, "_computed_total"]

    # Update orders
    orders_df = orders_df.merge(order_sums, on=order_id_col, how="left")
    orders_df[total_col] = orders_df["_computed_total"].fillna(0).round(2)
    orders_df.drop(columns=["_computed_total"], inplace=True)

    # Clean up items temp column
    items_df.drop(columns=["_line_total"], inplace=True, errors="ignore")

    return orders_df


# ──────────────────────────── ER Diagram Data ────────────────────────────

def build_er_diagram_data(schema: SchemaDefinition) -> dict:
    """Build ER diagram metadata for frontend visualization."""
    tables_data = []
    for table in schema.tables:
        fields_data = []
        for field in table.fields:
            fields_data.append({
                "name": field.name,
                "type": field.data_type.value,
                "is_pk": field.is_primary_key,
                "is_fk": field.is_foreign_key,
                "nullable": field.constraint.nullable,
            })
        tables_data.append({
            "name": table.name,
            "fields": fields_data,
            "row_count": table.row_count,
        })

    relations_data = []
    for rel in schema.relations:
        relations_data.append({
            "from_table": rel.from_table,
            "from_column": rel.from_column,
            "to_table": rel.to_table,
            "to_column": rel.to_column,
            "cardinality": rel.cardinality.value,
        })

    return {"tables": tables_data, "relations": relations_data}


# ──────────────────────────── N:N Junction Table Generator ────────────────────────────

def generate_junction_table(
    table_a_keys: list[Any],
    table_b_keys: list[Any],
    relation: ForeignKeyRelation,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Generate a junction table for N:N relationships."""
    pairs = set()
    for a_key in table_a_keys:
        n_links = rng.integers(relation.min_children, relation.max_children + 1)
        linked_bs = rng.choice(table_b_keys, min(n_links, len(table_b_keys)), replace=False)
        for b_key in linked_bs:
            pairs.add((a_key, b_key))

    junction_name = f"{relation.from_table}_{relation.to_table}"
    return pd.DataFrame(list(pairs), columns=[relation.from_column, relation.to_column])


# ──────────────────────────── Main Relational Generation ────────────────────────────

def generate_relational(
    schema: SchemaDefinition,
    sample_data: Optional[dict[str, pd.DataFrame]] = None,
    edge_cases: Optional[list[EdgeCase]] = None,
) -> dict[str, pd.DataFrame]:
    """
    Generate a complete set of relationally-consistent tables.

    Returns a dict mapping table names to DataFrames.
    All foreign keys reference valid parent records.
    Cross-table totals are mathematically reconciled.
    """
    rng = np.random.default_rng(schema.seed)

    # Determine generation order via topological sort
    gen_order = topological_sort(schema.tables, schema.relations)
    logger.info(f"Generation order: {gen_order}")

    # Build relation lookup: child_table -> list of relations
    child_relations: dict[str, list[ForeignKeyRelation]] = defaultdict(list)
    for rel in schema.relations:
        child_relations[rel.from_table].append(rel)

    generated: dict[str, pd.DataFrame] = {}
    pk_values: dict[str, dict[str, list[Any]]] = {}  # table -> {col: [values]}

    for table_name in gen_order:
        table_def = schema.get_table(table_name)
        if table_def is None:
            logger.warning(f"Table '{table_name}' not found in schema — skipping")
            continue

        # Prepare FK values from already-generated parent tables
        fk_vals: dict[str, list[Any]] = {}
        for rel in child_relations.get(table_name, []):
            parent_table = rel.to_table
            parent_col = rel.to_column

            if parent_table in pk_values and parent_col in pk_values[parent_table]:
                parent_keys = pk_values[parent_table][parent_col]
                fk_vals[rel.from_column] = generate_fk_values(
                    parent_keys, table_def.row_count, rel, rng
                )

        # Get sample data for this table
        sample_df = None
        if sample_data and table_name in sample_data:
            sample_df = sample_data[table_name]

        # Filter edge cases for this table
        table_edges = None
        if edge_cases:
            table_edges = [
                ec for ec in edge_cases
                if ec.field_target and any(
                    f.name == ec.field_target for f in table_def.fields
                )
            ]

        # Generate the table
        df = generate_tabular(
            table_def=table_def,
            schema=schema,
            sample_df=sample_df,
            edge_cases=table_edges,
            fk_values=fk_vals if fk_vals else None,
        )

        # Store generated PK values for child tables
        pk_values[table_name] = {}
        for field in table_def.fields:
            if field.is_primary_key:
                pk_values[table_name][field.name] = df[field.name].tolist()

        generated[table_name] = df
        logger.info(f"Generated {len(df)} rows for '{table_name}'")

    # ── Cross-Table Reconciliation ──
    # Look for order/items pattern and reconcile totals
    for table_name, df in generated.items():
        table_def = schema.get_table(table_name)
        if table_def is None:
            continue

        # Find if this table has a "total" column and child line items
        total_field = None
        for field in table_def.fields:
            if field.data_type == DataType.CURRENCY and "total" in field.name.lower():
                total_field = field
                break

        if total_field is None:
            continue

        # Find child table with qty and unit_price
        for rel in schema.relations:
            if rel.to_table == table_name:
                child_name = rel.from_table
                if child_name in generated:
                    child_df = generated[child_name]
                    child_def = schema.get_table(child_name)
                    if child_def is None:
                        continue

                    qty_col = None
                    price_col = None
                    for cf in child_def.fields:
                        if "qty" in cf.name.lower() or "quantity" in cf.name.lower():
                            qty_col = cf.name
                        if "price" in cf.name.lower() or "unit_price" in cf.name.lower():
                            price_col = cf.name

                    if qty_col and price_col:
                        generated[table_name] = reconcile_order_totals(
                            df, child_df,
                            order_id_col=rel.to_column,
                            total_col=total_field.name,
                            qty_col=qty_col,
                            price_col=price_col,
                        )
                        logger.info(f"Reconciled totals: {table_name}.{total_field.name}")

    # Handle N:N junction tables
    for rel in schema.relations:
        if rel.cardinality == Cardinality.MANY_TO_MANY:
            if rel.from_table in pk_values and rel.to_table in pk_values:
                a_keys = list(pk_values[rel.from_table].values())[0] if pk_values[rel.from_table] else []
                b_keys = list(pk_values[rel.to_table].values())[0] if pk_values[rel.to_table] else []
                if a_keys and b_keys:
                    junction = generate_junction_table(a_keys, b_keys, rel, rng)
                    junction_name = f"{rel.from_table}_{rel.to_table}"
                    generated[junction_name] = junction
                    logger.info(f"Generated junction table '{junction_name}' with {len(junction)} rows")

    return generated


# ──────────────────────────── Integrity Validation ────────────────────────────

def validate_referential_integrity(
    tables: dict[str, pd.DataFrame],
    schema: SchemaDefinition,
) -> dict[str, Any]:
    """
    Validate that all foreign key references are satisfied.
    Returns a dict with validation results.
    """
    results = {
        "valid": True,
        "orphan_count": 0,
        "details": [],
    }

    for rel in schema.relations:
        if rel.from_table not in tables or rel.to_table not in tables:
            results["details"].append({
                "relation": f"{rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}",
                "status": "skip",
                "message": "Table not found in generated data",
            })
            continue

        child_df = tables[rel.from_table]
        parent_df = tables[rel.to_table]

        if rel.from_column not in child_df.columns or rel.to_column not in parent_df.columns:
            results["details"].append({
                "relation": f"{rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}",
                "status": "skip",
                "message": "Column not found",
            })
            continue

        parent_keys = set(parent_df[rel.to_column].dropna().tolist())
        child_fks = child_df[rel.from_column].dropna().tolist()
        orphans = [fk for fk in child_fks if fk not in parent_keys]

        status = "pass" if len(orphans) == 0 else "fail"
        results["details"].append({
            "relation": f"{rel.from_table}.{rel.from_column} -> {rel.to_table}.{rel.to_column}",
            "status": status,
            "orphan_count": len(orphans),
            "total_fk_values": len(child_fks),
            "message": f"{len(orphans)} orphan records" if orphans else "All references valid",
        })

        if orphans:
            results["valid"] = False
            results["orphan_count"] += len(orphans)

    return results
