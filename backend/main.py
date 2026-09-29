"""
Synthetic Data Platform — FastAPI Backend
Main application with all API routes, CORS, rate limiting, and session management.
"""

import io
import os
import csv
import json
import uuid
import logging
from typing import Any, Optional

from dotenv import load_dotenv
import numpy as np
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.core.schema import (
    SchemaDefinition, TableDefinition, FieldDefinition, ForeignKeyRelation,
    DataType, Cardinality, PrivacyTransform, FieldConstraint,
    InvoiceConfig, BankStatementConfig, TaxRegion, DocumentRequest,
    EdgeCase, GenerationConfig,
    ingest_csv, ingest_json_schema, ingest_sql_ddl,
    get_ecommerce_preset, get_hr_preset,
)
from backend.core.ai import (
    infer_schema_ai, synthesize_text_ai, suggest_edge_cases_ai,
    parse_nl_document_query,
)
from backend.core.validate import validate_tstr_readiness, validate_document_reconciliation
from backend.core.export import export_csv, export_json, export_sql, export_zip
from backend.engines.tabular import generate_tabular, compute_fidelity_metrics
from backend.engines.relational import (
    generate_relational, validate_referential_integrity, build_er_diagram_data,
)
from backend.engines.documents import (
    generate_invoice_pdf, generate_statement_pdf, generate_bulk_documents,
)

load_dotenv()

# ──────────────────────────── Logging ────────────────────────────

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ──────────────────────────── Rate Limiter ────────────────────────────

limiter = Limiter(key_func=get_remote_address)

# ──────────────────────────── App Setup ────────────────────────────

app = FastAPI(
    title="Synthetic Data Platform",
    description="HackDataV2 — Generate realistic, privacy-safe synthetic data",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ──────────────────────────── In-Memory Session Store ────────────────────────────

# Session-scoped workspace state (ephemeral, no disk persistence)
_sessions: dict[str, dict[str, Any]] = {}

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_RESPONSE_ROWS = 5000
ALLOWED_MIME_TYPES = {"text/csv", "application/json", "text/plain", "application/octet-stream"}


def _get_session(session_id: str) -> dict[str, Any]:
    if session_id not in _sessions:
        _sessions[session_id] = {
            "schema": None,
            "generated_tables": {},
            "sample_data": {},
            "edge_cases": [],
            "validation": None,
        }
    return _sessions[session_id]


# ──────────────────────────── Request / Response Models ────────────────────────────

class SessionResponse(BaseModel):
    session_id: str


class SchemaResponse(BaseModel):
    schema_def: dict
    er_diagram: Optional[dict] = None


class GenerateRequest(BaseModel):
    mode: str = "tabular"  # "tabular", "relational"
    session_id: Optional[str] = ""
    schema_def: Optional[dict] = None
    preset: Optional[str] = None
    row_count: int = Field(default=100, ge=1, le=100000)
    seed: int = 42
    null_rate: float = Field(default=0.02, ge=0.0, le=0.5)
    outlier_rate: float = Field(default=0.01, ge=0.0, le=0.2)
    locale: str = "en_US"
    use_ai: bool = False
    ai_provider: str = "gemini"
    edge_cases: list[dict] = Field(default_factory=list)


class DocumentGenerateRequest(BaseModel):
    doc_type: str = "invoice"
    count: int = Field(default=1, ge=1, le=200)
    tax_region: str = "us_sales_tax"
    tax_rate: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    opening_balance: float = 1000.0
    num_transactions: int = Field(default=30, ge=5, le=200)
    days_span: int = Field(default=30, ge=7, le=365)
    include_large_refunds: int = Field(default=0, ge=0, le=10)
    currency_symbol: str = "$"
    locale: str = "en_US"
    seed: int = 42
    natural_language_query: Optional[str] = None


class PreviewResponse(BaseModel):
    tables: dict[str, list[dict]]
    row_counts: dict[str, int]
    validation: Optional[dict] = None


# ──────────────────────────── Health Check ────────────────────────────

@app.get("/")
async def health():
    return {"status": "healthy", "platform": "Synthetic Data Platform", "version": "1.0.0"}


# ──────────────────────────── Session ────────────────────────────

@app.post("/api/session", response_model=SessionResponse)
async def create_session():
    """Create a new ephemeral workspace session."""
    session_id = str(uuid.uuid4())
    _get_session(session_id)
    return SessionResponse(session_id=session_id)


# ──────────────────────────── Schema Ingestion ────────────────────────────

@app.post("/api/schema/upload-csv")
@limiter.limit("30/minute")
async def upload_csv(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = Form(...),
    table_name: str = Form(default="uploaded_table"),
):
    """Upload a CSV sample for schema inference. File is processed in-memory only."""
    # Validate file
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Invalid file type: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)}MB")

    # Sanitize and parse
    try:
        table_def = ingest_csv(content, table_name)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse CSV: {str(e)}")

    session = _get_session(session_id)

    # Store sample data in memory for statistical fitting
    try:
        df = pd.read_csv(io.BytesIO(content))
        session["sample_data"][table_name] = df
    except Exception:
        pass

    # Build schema with single table
    schema = SchemaDefinition(tables=[table_def])
    session["schema"] = schema

    # Garbage collect the raw content
    del content

    return {
        "table": table_def.model_dump(),
        "message": f"Parsed {len(table_def.fields)} columns from '{table_name}'",
    }


@app.post("/api/schema/from-json")
@limiter.limit("30/minute")
async def schema_from_json(request: Request, body: dict = Body(...)):
    """Create schema from JSON definition."""
    session_id = body.get("session_id", str(uuid.uuid4()))
    json_str = json.dumps(body.get("schema", body))

    try:
        table_def = ingest_json_schema(json_str)
    except Exception as e:
        raise HTTPException(400, f"Invalid JSON schema: {str(e)}")

    session = _get_session(session_id)
    schema = SchemaDefinition(tables=[table_def])
    session["schema"] = schema

    return {"table": table_def.model_dump(), "session_id": session_id}


@app.post("/api/schema/from-sql")
@limiter.limit("30/minute")
async def schema_from_sql(request: Request, body: dict = Body(...)):
    """Parse SQL DDL into schema definition."""
    session_id = body.get("session_id", str(uuid.uuid4()))
    ddl = body.get("ddl", "")

    try:
        tables = ingest_sql_ddl(ddl)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse DDL: {str(e)}")

    if not tables:
        raise HTTPException(400, "No CREATE TABLE statements found")

    session = _get_session(session_id)
    schema = SchemaDefinition(tables=tables)
    session["schema"] = schema

    return {
        "tables": [t.model_dump() for t in tables],
        "session_id": session_id,
    }


@app.post("/api/schema/preset")
async def load_preset(body: dict = Body(...)):
    """Load a preset schema (e-commerce or HR)."""
    session_id = body.get("session_id", str(uuid.uuid4()))
    preset_name = body.get("preset", "ecommerce")

    if preset_name == "ecommerce":
        schema = get_ecommerce_preset()
    elif preset_name == "hr":
        schema = get_hr_preset()
    else:
        raise HTTPException(400, f"Unknown preset: {preset_name}")

    session = _get_session(session_id)
    session["schema"] = schema

    er_data = build_er_diagram_data(schema)

    return {
        "schema": schema.model_dump(),
        "er_diagram": er_data,
        "session_id": session_id,
    }


@app.post("/api/schema/custom")
async def set_custom_schema(body: dict = Body(...)):
    """Set a fully custom schema definition."""
    session_id = body.get("session_id", str(uuid.uuid4()))

    try:
        schema = SchemaDefinition(**body.get("schema", {}))
    except Exception as e:
        raise HTTPException(400, f"Invalid schema: {str(e)}")

    session = _get_session(session_id)
    session["schema"] = schema

    er_data = build_er_diagram_data(schema)

    return {
        "schema": schema.model_dump(),
        "er_diagram": er_data,
        "session_id": session_id,
    }


# ──────────────────────────── AI Features ────────────────────────────

@app.post("/api/ai/infer-schema")
@limiter.limit("10/minute")
async def ai_infer_schema(request: Request, body: dict = Body(...)):
    """Use AI to infer schema from sample data rows."""
    session_id = body.get("session_id", str(uuid.uuid4()))
    sample_rows = body.get("sample_rows", [])
    provider = body.get("provider", "gemini")

    if not sample_rows:
        raise HTTPException(400, "No sample rows provided")

    result = await infer_schema_ai(sample_rows, provider)

    return {"schema": result, "session_id": session_id}


@app.post("/api/ai/suggest-edge-cases")
@limiter.limit("10/minute")
async def ai_edge_cases(request: Request, body: dict = Body(...)):
    """Use AI to suggest edge cases for the current schema."""
    session_id = body.get("session_id", "")
    provider = body.get("provider", "gemini")
    schema_fields = body.get("fields", [])

    if not schema_fields:
        session = _get_session(session_id)
        if session["schema"]:
            schema_fields = [
                {"name": f.name, "data_type": f.data_type.value}
                for t in session["schema"].tables
                for f in t.fields
            ]

    if not schema_fields:
        raise HTTPException(400, "No schema fields available")

    cases = await suggest_edge_cases_ai(schema_fields, provider)

    session = _get_session(session_id)
    session["edge_cases"] = [EdgeCase(**c) for c in cases]

    return {"edge_cases": cases}


@app.post("/api/ai/parse-document-query")
@limiter.limit("15/minute")
async def ai_parse_doc_query(request: Request, body: dict = Body(...)):
    """Parse a natural language query into document generation parameters."""
    query = body.get("query", "")
    provider = body.get("provider", "gemini")

    if not query:
        raise HTTPException(400, "No query provided")

    result = await parse_nl_document_query(query, provider)
    return {"config": result}


# ──────────────────────────── Data Generation ────────────────────────────

@app.post("/api/generate")
@limiter.limit("20/minute")
async def generate_data(request: Request, body: GenerateRequest):
    """Generate synthetic data (tabular or relational mode)."""
    session_id = body.session_id or (body.schema_def.get("_session_id", "") if body.schema_def else "")

    # Build schema
    schema = None
    if body.preset:
        if body.preset == "ecommerce":
            schema = get_ecommerce_preset()
        elif body.preset == "hr":
            schema = get_hr_preset()
        else:
            raise HTTPException(400, f"Unknown preset: {body.preset}")
    elif body.schema_def:
        try:
            schema_data = {k: v for k, v in body.schema_def.items() if k != "_session_id"}
            schema = SchemaDefinition(**schema_data)
        except Exception as e:
            raise HTTPException(400, f"Invalid schema: {str(e)}")
    elif session_id:
        session = _get_session(session_id)
        schema = session.get("schema")

    if schema is None:
        raise HTTPException(400, "No schema or preset provided")

    # Override global settings
    schema.seed = body.seed
    schema.null_rate = body.null_rate
    schema.outlier_rate = body.outlier_rate
    schema.locale = body.locale

    # Update row counts
    for table in schema.tables:
        if body.mode == "tabular" and len(schema.tables) == 1:
            table.row_count = body.row_count

    # Parse edge cases
    edge_cases = [EdgeCase(**ec) for ec in body.edge_cases] if body.edge_cases else []

    # Get sample data from session
    sample_data = None
    if session_id:
        session = _get_session(session_id)
        sample_data = session.get("sample_data")

    # Generate
    if body.mode == "relational" or len(schema.tables) > 1:
        tables = generate_relational(schema, sample_data, edge_cases)
    else:
        table_def = schema.tables[0]
        df = generate_tabular(
            table_def, schema,
            sample_df=sample_data.get(table_def.name) if sample_data else None,
            edge_cases=edge_cases,
        )
        tables = {table_def.name: df}

    # Validate
    validation = validate_tstr_readiness(tables, schema,
                                          real_tables=sample_data if sample_data else None)

    # Store in session
    if session_id:
        session = _get_session(session_id)
        session["generated_tables"] = tables
        session["schema"] = schema
        session["validation"] = validation

    # Build response
    preview = {}
    row_counts = {}
    for name, df in tables.items():
        preview[name] = df.head(MAX_RESPONSE_ROWS).to_dict(orient="records")
        row_counts[name] = len(df)

    er_data = build_er_diagram_data(schema) if len(schema.tables) > 1 else None

    return {
        "preview": preview,
        "row_counts": row_counts,
        "validation": validation,
        "er_diagram": er_data,
        "schema": schema.model_dump(),
    }


@app.post("/api/generate/preview")
@limiter.limit("60/minute")
async def generate_preview(request: Request, body: GenerateRequest):
    """Generate a quick preview (max 20 rows) for live debounced updates."""
    # Same as generate but capped at 20 rows for speed
    schema = None
    if body.preset:
        if body.preset == "ecommerce":
            schema = get_ecommerce_preset()
        elif body.preset == "hr":
            schema = get_hr_preset()
    elif body.schema_def:
        try:
            schema_data = {k: v for k, v in body.schema_def.items() if k != "_session_id"}
            schema = SchemaDefinition(**schema_data)
        except Exception as e:
            raise HTTPException(400, f"Invalid schema: {str(e)}")

    if schema is None:
        raise HTTPException(400, "No schema or preset provided")

    schema.seed = body.seed
    schema.null_rate = body.null_rate
    schema.outlier_rate = body.outlier_rate

    # Cap row count for preview
    for table in schema.tables:
        table.row_count = min(table.row_count, 20)

    if body.mode == "relational" or len(schema.tables) > 1:
        tables = generate_relational(schema)
    else:
        table_def = schema.tables[0]
        df = generate_tabular(table_def, schema)
        tables = {table_def.name: df}

    preview = {}
    for name, df in tables.items():
        preview[name] = df.to_dict(orient="records")

    return {"preview": preview}


# ──────────────────────────── Documents ────────────────────────────

@app.post("/api/documents/generate")
@limiter.limit("10/minute")
async def generate_documents(request: Request, body: DocumentGenerateRequest):
    """Generate PDF documents (invoices or bank statements)."""
    # Parse NL query if provided
    if body.natural_language_query:
        parsed = await parse_nl_document_query(body.natural_language_query)
        if "doc_type" in parsed:
            body.doc_type = parsed["doc_type"]
        if "opening_balance" in parsed:
            body.opening_balance = parsed["opening_balance"]
        if "num_transactions" in parsed:
            body.num_transactions = parsed["num_transactions"]
        if "days_span" in parsed:
            body.days_span = parsed["days_span"]
        if "include_large_refunds" in parsed:
            body.include_large_refunds = parsed["include_large_refunds"]
        if "count" in parsed:
            body.count = min(parsed["count"], 200)
        if "tax_region" in parsed:
            body.tax_region = parsed["tax_region"]
        if "tax_rate" in parsed:
            body.tax_rate = parsed["tax_rate"]

    if body.doc_type == "invoice":
        config = InvoiceConfig(
            count=body.count,
            tax_region=TaxRegion(body.tax_region),
            tax_rate=body.tax_rate,
            currency_symbol=body.currency_symbol,
            locale=body.locale,
            seed=body.seed,
        )
        pdfs, recons = generate_bulk_documents("invoice", config)
    else:
        config = BankStatementConfig(
            count=body.count,
            opening_balance=body.opening_balance,
            num_transactions=body.num_transactions,
            days_span=body.days_span,
            include_large_refunds=body.include_large_refunds,
            currency_symbol=body.currency_symbol,
            locale=body.locale,
            seed=body.seed,
        )
        pdfs, recons = generate_bulk_documents("bank_statement", config)

    # Validate reconciliation
    doc_validation = validate_document_reconciliation(recons)

    if body.count == 1:
        # Return single PDF
        return StreamingResponse(
            io.BytesIO(pdfs[0]),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{body.doc_type}_001.pdf"',
                "X-Reconciliation": json.dumps(recons[0], default=str),
                "X-Validation": json.dumps(doc_validation, default=str),
            },
        )
    else:
        # Return ZIP
        zip_bytes = export_zip(
            {}, SchemaDefinition(tables=[]),
            pdfs=pdfs, pdf_prefix=body.doc_type,
            recon_data=recons,
        )
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={
                "Content-Disposition": f'attachment; filename="{body.doc_type}s_bulk.zip"',
                "X-Validation": json.dumps(doc_validation, default=str),
            },
        )


@app.post("/api/documents/preview")
@limiter.limit("30/minute")
async def preview_document(request: Request, body: DocumentGenerateRequest):
    """Generate a single document preview and return reconciliation data."""
    if body.doc_type == "invoice":
        config = InvoiceConfig(
            count=1,
            tax_region=TaxRegion(body.tax_region),
            tax_rate=body.tax_rate,
            currency_symbol=body.currency_symbol,
            locale=body.locale,
            seed=body.seed,
        )
        pdf_bytes, recon = generate_invoice_pdf(config)
    else:
        config = BankStatementConfig(
            count=1,
            opening_balance=body.opening_balance,
            num_transactions=body.num_transactions,
            days_span=body.days_span,
            include_large_refunds=body.include_large_refunds,
            currency_symbol=body.currency_symbol,
            locale=body.locale,
            seed=body.seed,
        )
        pdf_bytes, recon = generate_statement_pdf(config)

    import base64
    pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")

    validation = validate_document_reconciliation([recon])

    return {
        "pdf_base64": pdf_b64,
        "reconciliation": recon,
        "validation": validation,
    }


# ──────────────────────────── Export ────────────────────────────

@app.post("/api/export")
@limiter.limit("15/minute")
async def export_data(request: Request, body: dict = Body(...)):
    """Export generated data in specified format."""
    session_id = body.get("session_id", "")
    fmt = body.get("format", "csv")

    session = _get_session(session_id)
    tables = session.get("generated_tables", {})
    schema = session.get("schema")

    if not tables:
        raise HTTPException(400, "No generated data to export. Generate data first.")

    if fmt == "csv":
        if len(tables) == 1:
            name, df = next(iter(tables.items()))
            csv_bytes = export_csv(df, name)
            return StreamingResponse(
                io.BytesIO(csv_bytes),
                media_type="text/csv",
                headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
            )
        else:
            # ZIP of CSVs
            zip_bytes = export_zip(tables, schema)
            return StreamingResponse(
                io.BytesIO(zip_bytes),
                media_type="application/zip",
                headers={"Content-Disposition": 'attachment; filename="synthetic_data.zip"'},
            )

    elif fmt == "json":
        json_bytes = export_json(tables)
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="synthetic_data.json"'},
        )

    elif fmt == "sql":
        if schema is None:
            raise HTTPException(400, "Schema not available for SQL export")
        sql_bytes = export_sql(tables, schema)
        return StreamingResponse(
            io.BytesIO(sql_bytes),
            media_type="application/sql",
            headers={"Content-Disposition": 'attachment; filename="schema_and_data.sql"'},
        )

    elif fmt == "zip":
        if schema is None:
            raise HTTPException(400, "Schema not available for ZIP export")
        zip_bytes = export_zip(tables, schema)
        return StreamingResponse(
            io.BytesIO(zip_bytes),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="synthetic_data.zip"'},
        )

    else:
        raise HTTPException(400, f"Unknown format: {fmt}")


# ──────────────────────────── Validation ────────────────────────────

@app.post("/api/validate")
async def validate_data(body: dict = Body(...)):
    """Run full validation on generated data."""
    session_id = body.get("session_id", "")
    session = _get_session(session_id)

    tables = session.get("generated_tables", {})
    schema = session.get("schema")
    sample_data = session.get("sample_data")

    if not tables or schema is None:
        raise HTTPException(400, "No generated data to validate")

    validation = validate_tstr_readiness(tables, schema, sample_data)
    session["validation"] = validation

    return validation


# ──────────────────────────── ER Diagram ────────────────────────────

@app.post("/api/er-diagram")
async def get_er_diagram(body: dict = Body(...)):
    """Get ER diagram data for the current schema."""
    session_id = body.get("session_id", "")
    session = _get_session(session_id)
    schema = session.get("schema")

    if schema is None:
        raise HTTPException(400, "No schema defined")

    return build_er_diagram_data(schema)


# ──────────────────────────── Presets List ────────────────────────────

@app.get("/api/presets")
async def list_presets():
    """List available schema presets."""
    return {
        "presets": [
            {
                "id": "ecommerce",
                "name": "E-Commerce",
                "description": "Customers → Orders → Order Items with transactional consistency",
                "tables": ["customers", "orders", "order_items"],
            },
            {
                "id": "hr",
                "name": "HR Department",
                "description": "Departments → Employees with salary distributions",
                "tables": ["departments", "employees"],
            },
        ]
    }


# ──────────────────────────── Startup ────────────────────────────

@app.on_event("startup")
async def startup():
    logger.info("🚀 Synthetic Data Platform starting up...")
    logger.info(f"  GEMINI_API_KEY: {'set' if os.environ.get('GEMINI_API_KEY') else 'not set'}")
    logger.info(f"  GROQ_API_KEY: {'set' if os.environ.get('GROQ_API_KEY') else 'not set'}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
