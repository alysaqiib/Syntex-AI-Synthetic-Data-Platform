# SYNTEX — AI Synthetic Data Platform (HackDataV2)

> **Built for HackDataV2 AI Hackathon** by Fatima & Ali.  
> Designed for **TSTR (Train on Synthetic, Test on Real)** evaluation with correlation checks, referential-integrity validation, and verifiable arithmetic reconciliation. 100% free-tier stack.

---

## 🌟 Core Architectural Highlights

| Dimension | Implementation Details |
| :--- | :--- |
| **Statistical Fidelity (TSTR)** | Multi-variate **Gaussian Copula** modeling preserving feature cross-correlations, skewness, and kurtosis. Tested via Wasserstein distance and Spearman rank matrices. |
| **Relational Integrity** | Strict topological generation ensuring **zero orphan foreign keys**, cascading parent-child key mapping, and cross-table financial consistency (e.g. `order_total == sum(items)`). |
| **Document Synthesis** | Pixel-perfect PDF generation (Commercial Invoices & Bank Statements) with **100% balanced arithmetic audit ledgers** (`Opening + Credits - Debits == Closing`). |
| **Privacy Controls** | In-memory processing, column-level masking, salted SHA-256 hashing, redaction, and configurable Laplace-style noise. These transforms are safeguards, not a formal differential-privacy or compliance certification. |
| **Zero-Cost Tech Stack** | FastAPI + Vite React + Google Gemini 1.5 Flash (Free Tier) + Groq (LLaMA-3.3-70B Free Tier) + ReportLab + Scipy. |

---

## 🚀 Quick Start

### 1. Backend Setup
```bash
# In project root
pip install -r backend/requirements.txt

# Run FastAPI backend
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. Frontend Setup
```bash
# In frontend directory
cd frontend
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 📐 Platform Capabilities

### 1. Tabular Synthetic Generator
- **Multi-modal Ingestion**: Drag & drop CSV samples, paste SQL `CREATE TABLE` DDL, or write raw JSON Schema.
- **Parametric Distributions**: Normal, Uniform, Lognormal, Bimodal, and Categorical frequency matching.
- **Privacy Transforms**: PII pseudonymization, Laplace-style noise, format masking, and redaction.
- **Real-time Live Preview**: 20-row instant debounced preview or batch synthesis up to 100,000 rows.

### 2. Relational Schema & ER Topology
- **Interactive Visual ER Diagram**: Dynamic SVG graph rendering Primary Keys (PK) and Foreign Keys (FK) with 1:1 and 1:N cardinality indicators.
- **Preset Topologies**:
  - **E-Commerce**: `customers` $\rightarrow$ `orders` $\rightarrow$ `order_items`
  - **HR Management**: `departments` $\rightarrow$ `employees`
- **Referential Integrity Auditor**: Reports orphan foreign keys and reconciliation results for each generated run.

### 3. Document Synthesis & Arithmetic Reconciliation
- **Natural Language Parsing**: Ask the AI in plain English: *"Generate 5 Q3 corporate invoices for Texas with 8.25% sales tax and net-30 terms"* or *"Create a 60-day bank statement with $25k opening balance and 2 large refunds"*.
- **Tax Jurisdictions**: US Sales Tax, EU/UK VAT (20%), Canadian GST/PST (13%), Pakistan GST (18%), or Zero-Rated.
- **Embedded PDF Viewer**: High-resolution in-browser preview + 1-click batch ZIP export.
- **Mathematical Audit Ledger**: Verifies line-item arithmetic and reports the discrepancy between statement balances and transaction ledgers.

### 4. TSTR Quality & Export Suite
- **TSTR Readiness Gauge**: Real-time score based on distribution and correlation checks when a real sample is available.
- **Multi-Format Export**: 1-click export to **CSV**, **JSON**, **Production SQL DDL + Inserts**, and **ZIP Bundles**.
- **AI Adversarial Edge-Cases**: Leverages Gemini / Groq to simulate leap-year timestamps, Unicode names, negative balances, and extreme financial bursts.

---

## 🔒 Privacy & Compliance
- **Ephemeral Session Workspace**: All data generation and schema transformations are executed in-memory. Zero persistent disk storage of uploaded user data.
- **Privacy limitation**: The platform does not persist uploaded samples, but it does not provide a formal zero-memorization proof or GDPR, HIPAA, or CCPA certification. Run your own legal, privacy, and disclosure review before production use.
