"""
Document Generation Engine — pixel-perfect PDF invoices and bank statements
using ReportLab with dynamic calculation, tax rules, and running balances.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime, timedelta
from typing import Any, Optional

import numpy as np
from faker import Faker
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
)
from reportlab.pdfgen import canvas as pdf_canvas

from backend.core.schema import (
    InvoiceConfig, BankStatementConfig, TaxRegion, InvoiceLineItem
)

logger = logging.getLogger(__name__)

# ──────────────────────────── Tax Rates ────────────────────────────

TAX_RATES = {
    TaxRegion.US: {"name": "Sales Tax", "rate": 0.0825},
    TaxRegion.UK_EU: {"name": "VAT", "rate": 0.20},
    TaxRegion.EU: {"name": "VAT", "rate": 0.20},
    TaxRegion.UK: {"name": "VAT", "rate": 0.20},
    TaxRegion.CA: {"name": "GST/PST", "rate": 0.13},
    TaxRegion.PK: {"name": "GST", "rate": 0.18},
    TaxRegion.NONE: {"name": "Tax", "rate": 0.0},
}


# ──────────────────────────── Color Palette ────────────────────────────

BRAND_DARK = colors.HexColor("#16233b")
BRAND_TEAL = colors.HexColor("#177a6b")
BRAND_LIGHT = colors.HexColor("#f0f4f8")
TEXT_DARK = colors.HexColor("#1a1a2e")
TEXT_GRAY = colors.HexColor("#6b7280")
BORDER_GRAY = colors.HexColor("#e5e7eb")


# ──────────────────────────── Styles ────────────────────────────

def _get_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="InvoiceTitle",
        fontSize=28,
        leading=34,
        textColor=BRAND_DARK,
        fontName="Helvetica-Bold",
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="InvoiceNumber",
        fontSize=11,
        textColor=BRAND_TEAL,
        fontName="Helvetica-Bold",
    ))
    styles.add(ParagraphStyle(
        name="LabelText",
        fontSize=8,
        textColor=TEXT_GRAY,
        fontName="Helvetica",
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="ValueText",
        fontSize=10,
        textColor=TEXT_DARK,
        fontName="Helvetica",
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="ValueTextBold",
        fontSize=10,
        textColor=TEXT_DARK,
        fontName="Helvetica-Bold",
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="TableHeader",
        fontSize=9,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name="TableHeaderRight",
        fontSize=9,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="TableCell",
        fontSize=9,
        textColor=TEXT_DARK,
        fontName="Helvetica",
    ))
    styles.add(ParagraphStyle(
        name="TableCellRight",
        fontSize=9,
        textColor=TEXT_DARK,
        fontName="Helvetica",
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="TotalLabel",
        fontSize=10,
        textColor=TEXT_DARK,
        fontName="Helvetica-Bold",
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="GrandTotal",
        fontSize=14,
        textColor=BRAND_TEAL,
        fontName="Helvetica-Bold",
        alignment=TA_RIGHT,
    ))
    styles.add(ParagraphStyle(
        name="StatementTitle",
        fontSize=24,
        leading=30,
        textColor=BRAND_DARK,
        fontName="Helvetica-Bold",
        spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="FooterText",
        fontSize=7,
        textColor=TEXT_GRAY,
        fontName="Helvetica",
        alignment=TA_CENTER,
    ))
    return styles


# ──────────────────────────── Product Catalog ────────────────────────────

PRODUCTS = [
    ("Cloud Compute Instance (m5.large)", 49.99, 299.99),
    ("API Gateway - 1M Requests", 3.50, 35.00),
    ("Managed PostgreSQL (db.r5)", 89.99, 449.99),
    ("SSL/TLS Certificate (Wildcard)", 29.99, 149.99),
    ("CDN Bandwidth - 1TB", 8.99, 89.99),
    ("Object Storage - 100GB", 2.30, 23.00),
    ("Container Orchestration Node", 59.99, 299.99),
    ("Serverless Function - 1M Executions", 0.20, 20.00),
    ("Load Balancer (Application)", 22.50, 225.00),
    ("Monitoring & Alerting Suite", 15.00, 150.00),
    ("DNS Zone Management", 0.50, 5.00),
    ("DDoS Protection (Advanced)", 99.99, 499.99),
    ("Data Pipeline Processing - 1M Events", 5.00, 50.00),
    ("AI/ML Training GPU Hour", 2.50, 25.00),
    ("Compliance Audit License", 199.99, 999.99),
    ("Enterprise Support Tier", 149.99, 749.99),
    ("Log Aggregation - 10GB/day", 25.00, 250.00),
    ("VPN Gateway", 14.99, 149.99),
    ("Email Delivery - 10K Messages", 1.99, 19.99),
    ("Backup & Disaster Recovery", 39.99, 199.99),
]

PAKISTAN_PRODUCTS = [
    ("Managed Hosting - Business Plan", 3500.00, 18000.00),
    ("E-commerce Website Maintenance", 15000.00, 75000.00),
    ("Digital Marketing Campaign", 25000.00, 150000.00),
    ("Cloud Backup - 1TB", 4500.00, 22000.00),
    ("Point of Sale Software License", 8000.00, 40000.00),
    ("IT Support Retainer", 20000.00, 100000.00),
]

PAKISTAN_NAMES = [
    "Ayesha Khan", "Ali Raza", "Fatima Ahmed", "Hassan Malik",
    "Maham Iqbal", "Usman Tariq", "Sana Siddiqui", "Bilal Shah",
]
PAKISTAN_CITIES = [
    ("Lahore", "Punjab"), ("Karachi", "Sindh"), ("Islamabad", "ICT"),
    ("Rawalpindi", "Punjab"), ("Peshawar", "Khyber Pakhtunkhwa"),
]
PAKISTAN_COMPANIES = [
    "Lahore Digital Works (Pvt.) Ltd.", "Karachi Trade House (Pvt.) Ltd.",
    "Islamabad Technology Services", "Punjab Enterprise Solutions",
]


def _format_address(fake: Faker, locale: str) -> str:
    """Use US state formatting only for locales that provide state_abbr."""
    if _is_pakistan_locale(locale):
        city, province = fake.random_element(PAKISTAN_CITIES)
        return f"House {fake.random_int(1, 250)}, {city}, {province}"
    if locale.lower() in {"en_us", "en_us_posix"}:
        region = f"{fake.state_abbr()} {fake.zipcode()}"
    else:
        region = fake.postcode()
    return f"{fake.street_address()}\n{fake.city()}, {region}"


def _create_faker(locale: str) -> Faker:
    try:
        return Faker(locale)
    except AttributeError:
        return Faker("en_US")


def _is_pakistan_locale(locale: str) -> bool:
    return locale.lower() in {"pk", "en_pk", "ur_pk", "pa_pk"}

MERCHANTS = [
    "Amazon.com", "Starbucks", "Uber Technologies", "Netflix Inc",
    "Whole Foods Market", "Shell Gas Station", "Target Stores",
    "Apple iTunes", "Spotify Premium", "Costco Wholesale",
    "McDonald's", "Walmart Supercenter", "Home Depot",
    "CVS Pharmacy", "Trader Joe's", "Lyft Ride",
    "DoorDash Delivery", "Adobe Systems", "Google Cloud",
    "Microsoft Azure", "Dropbox Business", "Zoom Pro",
    "Electric Utility Co", "Water & Sewer Dept", "AT&T Wireless",
    "Verizon Wireless", "Comcast Internet", "State Farm Insurance",
    "Blue Cross Medical", "Planet Fitness", "REI Co-op",
]

PAKISTAN_MERCHANTS = [
    "Daraz.pk", "Foodpanda Pakistan", "Careem Pakistan", "JazzCash",
    "Easypaisa", "K-Electric", "PTCL Broadband", "HBL Konnect",
    "Metro Cash & Carry", "Imtiaz Super Market", "Sui Gas Utility",
    "Pakistan State Oil", "Telenor Pakistan", "Packages Mall",
]


# ──────────────────────────── Invoice Generator ────────────────────────────

def generate_invoice_pdf(config: InvoiceConfig, index: int = 0) -> tuple[bytes, dict]:
    """
    Generate a single invoice PDF.
    Returns (pdf_bytes, reconciliation_data).
    """
    rng = np.random.default_rng(config.seed + index)
    fake = _create_faker(config.locale)
    Faker.seed(config.seed + index)
    styles = _get_styles()

    # Generate invoice metadata
    inv_number = f"INV-{10000 + index:05d}"
    inv_date = fake.date_between(start_date="-90d", end_date="today")
    due_date = inv_date + timedelta(days=30)
    company_name = fake.random_element(PAKISTAN_COMPANIES) if _is_pakistan_locale(config.locale) else fake.company()
    company_address = _format_address(fake, config.locale)
    client_name = fake.random_element(PAKISTAN_NAMES) if _is_pakistan_locale(config.locale) else fake.name()
    client_company = fake.random_element(PAKISTAN_COMPANIES) if _is_pakistan_locale(config.locale) else fake.company()
    client_address = _format_address(fake, config.locale)

    # Generate line items
    n_items = rng.integers(config.min_line_items, config.max_line_items + 1)
    line_items = []
    for _ in range(n_items):
        products = PAKISTAN_PRODUCTS if _is_pakistan_locale(config.locale) else PRODUCTS
        product, min_p, max_p = products[rng.integers(0, len(products))]
        qty = int(rng.integers(1, 15))
        unit_price = round(float(rng.uniform(min_p, max_p)), 2)
        line_items.append(InvoiceLineItem(
            product_name=product,
            quantity=qty,
            unit_price=unit_price,
        ))

    # Calculate totals
    subtotal = sum(item.total for item in line_items)
    tax_info = TAX_RATES.get(config.tax_region, TAX_RATES[TaxRegion.NONE])
    tax_rate = config.tax_rate if config.tax_rate is not None else tax_info["rate"]
    tax_amount = round(subtotal * tax_rate, 2)
    grand_total = round(subtotal + tax_amount, 2)

    sym = config.currency_symbol

    # Build PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )

    elements = []

    # Header
    elements.append(Paragraph("INVOICE", styles["InvoiceTitle"]))
    elements.append(Paragraph(inv_number, styles["InvoiceNumber"]))
    elements.append(Spacer(1, 16))

    # Company and client info side by side
    info_data = [
        [
            Paragraph("FROM", styles["LabelText"]),
            Paragraph("BILL TO", styles["LabelText"]),
            Paragraph("INVOICE DATE", styles["LabelText"]),
        ],
        [
            Paragraph(f"<b>{company_name}</b><br/>{company_address}", styles["ValueText"]),
            Paragraph(f"<b>{client_name}</b><br/>{client_company}<br/>{client_address}", styles["ValueText"]),
            Paragraph(f"<b>{inv_date.strftime('%B %d, %Y')}</b><br/>Due: {due_date.strftime('%B %d, %Y')}", styles["ValueText"]),
        ],
    ]
    info_table = Table(info_data, colWidths=[2.3 * inch, 2.3 * inch, 2.3 * inch])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))

    # Divider
    elements.append(HRFlowable(width="100%", thickness=1, color=BRAND_TEAL, spaceAfter=12))

    # Line items table
    header_row = [
        Paragraph("ITEM", styles["TableHeader"]),
        Paragraph("QTY", styles["TableHeaderRight"]),
        Paragraph("UNIT PRICE", styles["TableHeaderRight"]),
        Paragraph("TOTAL", styles["TableHeaderRight"]),
    ]
    table_data = [header_row]

    for item in line_items:
        table_data.append([
            Paragraph(item.product_name, styles["TableCell"]),
            Paragraph(str(item.quantity), styles["TableCellRight"]),
            Paragraph(f"{sym}{item.unit_price:,.2f}", styles["TableCellRight"]),
            Paragraph(f"{sym}{item.total:,.2f}", styles["TableCellRight"]),
        ])

    items_table = Table(
        table_data,
        colWidths=[3.2 * inch, 0.8 * inch, 1.4 * inch, 1.4 * inch],
        repeatRows=1,
    )
    items_table.setStyle(TableStyle([
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("LEFTPADDING", (0, 0), (-1, 0), 10),
        ("RIGHTPADDING", (0, 0), (-1, 0), 10),
        # Data rows
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("LEFTPADDING", (0, 1), (-1, -1), 10),
        ("RIGHTPADDING", (0, 1), (-1, -1), 10),
        # Alternating row colors
        *[
            ("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT if i % 2 == 0 else colors.white)
            for i in range(1, len(table_data))
        ],
        # Borders
        ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_TEAL),
        ("LINEBELOW", (0, -1), (-1, -1), 1, BORDER_GRAY),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 16))

    # Totals
    totals_data = [
        ["", "", Paragraph("Subtotal", styles["TotalLabel"]),
         Paragraph(f"{sym}{subtotal:,.2f}", styles["TableCellRight"])],
        ["", "", Paragraph(f"{tax_info['name']} ({tax_rate*100:.1f}%)", styles["TotalLabel"]),
         Paragraph(f"{sym}{tax_amount:,.2f}", styles["TableCellRight"])],
        ["", "", Paragraph("TOTAL DUE", styles["TotalLabel"]),
         Paragraph(f"{sym}{grand_total:,.2f}", styles["GrandTotal"])],
    ]
    totals_table = Table(
        totals_data,
        colWidths=[3.2 * inch, 0.8 * inch, 1.4 * inch, 1.4 * inch],
    )
    totals_table.setStyle(TableStyle([
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEABOVE", (2, 2), (-1, 2), 2, BRAND_TEAL),
        ("TOPPADDING", (2, 2), (-1, 2), 8),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 30))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceAfter=8))
    elements.append(Paragraph(
        "This is a synthetically generated invoice for demonstration purposes only. "
        "Generated by Synthetic Data Platform — HackDataV2.",
        styles["FooterText"]
    ))

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()

    # Reconciliation data
    recon = {
        "invoice_number": inv_number,
        "date": inv_date.isoformat(),
        "due_date": due_date.isoformat(),
        "client": client_name,
        "client_company": client_company,
        "num_items": len(line_items),
        "subtotal": subtotal,
        "tax_name": tax_info["name"],
        "tax_rate": tax_rate,
        "tax_amount": tax_amount,
        "grand_total": grand_total,
        "line_items": [
            {
                "product": item.product_name,
                "qty": item.quantity,
                "unit_price": item.unit_price,
                "total": item.total,
            }
            for item in line_items
        ],
    }

    return pdf_bytes, recon


# ──────────────────────────── Bank Statement Generator ────────────────────────────

def generate_statement_pdf(config: BankStatementConfig, index: int = 0) -> tuple[bytes, dict]:
    """
    Generate a single bank statement PDF with running balances.
    Returns (pdf_bytes, reconciliation_data).
    """
    rng = np.random.default_rng(config.seed + index)
    fake = _create_faker(config.locale)
    Faker.seed(config.seed + index)
    styles = _get_styles()

    sym = config.currency_symbol
    account_name = fake.name()
    account_number = f"****{rng.integers(1000, 9999)}"
    bank_name = f"{fake.last_name()} National Bank"

    # Generate statement period
    end_date = datetime.now().date() - timedelta(days=int(rng.integers(1, 10)))
    start_date = end_date - timedelta(days=int(config.days_span))

    # Generate transactions
    transactions = []
    current_balance = config.opening_balance
    dates = sorted([
        start_date + timedelta(days=int(d))
        for d in rng.choice(range(config.days_span), config.num_transactions, replace=True)
    ])

    refund_indices = set()
    if config.include_large_refunds > 0:
        refund_indices = set(
            rng.choice(range(config.num_transactions), config.include_large_refunds, replace=False)
        )

    for i, date in enumerate(dates):
        if i in refund_indices:
            # Large refund (credit)
            amount = round(float(rng.uniform(500, 2500)), 2)
            merchants = PAKISTAN_MERCHANTS if _is_pakistan_locale(config.locale) else MERCHANTS
            merchant = rng.choice(["REFUND - " + m for m in merchants[:10]])
            is_credit = True
        else:
            # Normal transaction
            is_credit = rng.random() < 0.25  # 25% credits
            if is_credit:
                amount = round(float(rng.uniform(50, 1500)), 2)
                merchant = rng.choice(["Direct Deposit", "Transfer In", "Interest Payment",
                                       "Venmo Credit", "PayPal Transfer", "Refund"])
            else:
                amount = round(float(rng.uniform(2.50, 350)), 2)
                merchants = PAKISTAN_MERCHANTS if _is_pakistan_locale(config.locale) else MERCHANTS
                merchant = rng.choice(merchants)

        if is_credit:
            current_balance = round(current_balance + amount, 2)
            debit = None
            credit = amount
        else:
            current_balance = round(current_balance - amount, 2)
            debit = amount
            credit = None

        transactions.append({
            "date": date.strftime("%m/%d/%Y"),
            "description": str(merchant),
            "debit": debit,
            "credit": credit,
            "balance": current_balance,
        })

    closing_balance = current_balance

    # Build PDF
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
    )

    elements = []

    # Header
    elements.append(Paragraph(bank_name.upper(), styles["StatementTitle"]))
    elements.append(Paragraph("ACCOUNT STATEMENT", styles["InvoiceNumber"]))
    elements.append(Spacer(1, 12))

    # Account info
    acct_data = [
        [
            Paragraph("ACCOUNT HOLDER", styles["LabelText"]),
            Paragraph("ACCOUNT NUMBER", styles["LabelText"]),
            Paragraph("STATEMENT PERIOD", styles["LabelText"]),
        ],
        [
            Paragraph(f"<b>{account_name}</b>", styles["ValueText"]),
            Paragraph(f"<b>{account_number}</b>", styles["ValueText"]),
            Paragraph(
                f"<b>{start_date.strftime('%b %d, %Y')} — {end_date.strftime('%b %d, %Y')}</b>",
                styles["ValueText"]
            ),
        ],
    ]
    acct_table = Table(acct_data, colWidths=[2.3 * inch, 2.3 * inch, 2.3 * inch])
    acct_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(acct_table)
    elements.append(Spacer(1, 8))

    # Summary box
    total_debits = sum(t["debit"] or 0 for t in transactions)
    total_credits = sum(t["credit"] or 0 for t in transactions)

    summary_data = [
        [
            Paragraph("Opening Balance", styles["LabelText"]),
            Paragraph("Total Debits", styles["LabelText"]),
            Paragraph("Total Credits", styles["LabelText"]),
            Paragraph("Closing Balance", styles["LabelText"]),
        ],
        [
            Paragraph(f"<b>{sym}{config.opening_balance:,.2f}</b>", styles["ValueTextBold"]),
            Paragraph(f"<b>{sym}{total_debits:,.2f}</b>",
                      ParagraphStyle("debit", parent=styles["ValueTextBold"],
                                     textColor=colors.HexColor("#dc2626"))),
            Paragraph(f"<b>{sym}{total_credits:,.2f}</b>",
                      ParagraphStyle("credit", parent=styles["ValueTextBold"],
                                     textColor=colors.HexColor("#059669"))),
            Paragraph(f"<b>{sym}{closing_balance:,.2f}</b>", styles["ValueTextBold"]),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[1.72 * inch] * 4)
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ("BOX", (0, 0), (-1, -1), 0.5, BORDER_GRAY),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 16))

    # Transaction table
    header = [
        Paragraph("DATE", styles["TableHeader"]),
        Paragraph("DESCRIPTION", styles["TableHeader"]),
        Paragraph("DEBIT", styles["TableHeaderRight"]),
        Paragraph("CREDIT", styles["TableHeaderRight"]),
        Paragraph("BALANCE", styles["TableHeaderRight"]),
    ]
    txn_data = [header]

    for txn in transactions:
        debit_str = f"{sym}{txn['debit']:,.2f}" if txn["debit"] else ""
        credit_str = f"{sym}{txn['credit']:,.2f}" if txn["credit"] else ""

        # Color-code balance
        bal_color = colors.HexColor("#059669") if txn["balance"] >= 0 else colors.HexColor("#dc2626")
        bal_style = ParagraphStyle("bal", parent=styles["TableCellRight"], textColor=bal_color)

        txn_data.append([
            Paragraph(txn["date"], styles["TableCell"]),
            Paragraph(txn["description"], styles["TableCell"]),
            Paragraph(debit_str, ParagraphStyle("debitCell", parent=styles["TableCellRight"],
                                                 textColor=colors.HexColor("#dc2626")) if debit_str else styles["TableCellRight"]),
            Paragraph(credit_str, ParagraphStyle("creditCell", parent=styles["TableCellRight"],
                                                  textColor=colors.HexColor("#059669")) if credit_str else styles["TableCellRight"]),
            Paragraph(f"{sym}{txn['balance']:,.2f}", bal_style),
        ])

    txn_table = Table(
        txn_data,
        colWidths=[1.0 * inch, 2.5 * inch, 1.1 * inch, 1.1 * inch, 1.2 * inch],
        repeatRows=1,
    )
    txn_table.setStyle(TableStyle([
        # Header
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
        ("LEFTPADDING", (0, 0), (-1, 0), 8),
        ("RIGHTPADDING", (0, 0), (-1, 0), 8),
        # Data
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
        ("LEFTPADDING", (0, 1), (-1, -1), 8),
        ("RIGHTPADDING", (0, 1), (-1, -1), 8),
        # Alternating colors
        *[
            ("BACKGROUND", (0, i), (-1, i), BRAND_LIGHT if i % 2 == 0 else colors.white)
            for i in range(1, len(txn_data))
        ],
        ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_TEAL),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, BORDER_GRAY),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    elements.append(txn_table)
    elements.append(Spacer(1, 20))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=0.5, color=BORDER_GRAY, spaceAfter=8))
    elements.append(Paragraph(
        "This is a synthetically generated bank statement for demonstration purposes only. "
        "Generated by Synthetic Data Platform — HackDataV2.",
        styles["FooterText"]
    ))

    doc.build(elements)
    pdf_bytes = buf.getvalue()
    buf.close()

    # Reconciliation data
    recon = {
        "account_holder": account_name,
        "account_number": account_number,
        "bank_name": bank_name,
        "period_start": start_date.isoformat(),
        "period_end": end_date.isoformat(),
        "opening_balance": config.opening_balance,
        "closing_balance": closing_balance,
        "total_debits": round(total_debits, 2),
        "total_credits": round(total_credits, 2),
        "num_transactions": len(transactions),
        "balance_check": round(config.opening_balance - total_debits + total_credits, 2) == closing_balance,
        "transactions": transactions,
    }

    return pdf_bytes, recon


# ──────────────────────────── Bulk Generator ────────────────────────────

def generate_bulk_documents(
    doc_type: str,
    config: InvoiceConfig | BankStatementConfig,
) -> tuple[list[bytes], list[dict]]:
    """Generate multiple documents and return (pdf_list, recon_list)."""
    count = config.count
    all_pdfs = []
    all_recons = []

    for i in range(count):
        if doc_type == "invoice":
            pdf, recon = generate_invoice_pdf(config, index=i)
        else:
            pdf, recon = generate_statement_pdf(config, index=i)

        all_pdfs.append(pdf)
        all_recons.append(recon)

    return all_pdfs, all_recons
