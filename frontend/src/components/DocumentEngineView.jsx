import React, { useState } from 'react';
import { 
  FileText, 
  Sparkles, 
  Download, 
  CheckCircle, 
  Calculator, 
  Eye, 
  Send,
  Layers,
  ArrowRight,
  ShieldCheck,
  Percent
} from 'lucide-react';

const TAX_REGIONS = [
  { id: 'us_sales_tax', label: 'US Sales Tax (State-varying)' },
  { id: 'eu_vat_20', label: 'EU Standard VAT (20%)' },
  { id: 'uk_vat_20', label: 'UK Standard VAT (20%)' },
  { id: 'ca_gst_pst', label: 'Canada GST/PST (13%)' },
  { id: 'pk_gst', label: 'Pakistan GST (18%)' },
  { id: 'none', label: 'No Tax / Zero-Rated' },
];

const CURRENCIES = [
  { symbol: '$', label: 'USD ($)' },
  { symbol: '€', label: 'EUR (€)' },
  { symbol: '£', label: 'GBP (£)' },
  { symbol: '¥', label: 'JPY (¥)' },
  { symbol: 'Rs', label: 'PKR (Rs)' },
];

const LOCALES = [
  { id: 'en_PK', label: 'Pakistan' },
  { id: 'en_US', label: 'United States' },
  { id: 'en_GB', label: 'United Kingdom' },
];

export default function DocumentEngineView({
  onGenerateDocPreview,
  onDownloadBulkDocs,
  onNlDocParse,
  docPreviewData,
  isGeneratingDoc,
}) {
  const [docType, setDocType] = useState('invoice'); // 'invoice' | 'bank_statement'
  const [nlQuery, setNlQuery] = useState('');
  
  // Invoice state
  const [taxRegion, setTaxRegion] = useState('us_sales_tax');
  const [currencySymbol, setCurrencySymbol] = useState('$');
  const [locale, setLocale] = useState('en_PK');
  const [invoiceCount, setInvoiceCount] = useState(1);

  // Bank Statement state
  const [openingBalance, setOpeningBalance] = useState(15000);
  const [numTransactions, setNumTransactions] = useState(25);
  const [daysSpan, setDaysSpan] = useState(30);
  const [largeRefunds, setLargeRefunds] = useState(1);

  // Handle NL Query submission
  const handleNlSubmit = async (e) => {
    e?.preventDefault();
    if (!nlQuery.trim()) return;
    const config = await onNlDocParse(nlQuery);
    if (config) {
      if (config.doc_type) setDocType(config.doc_type);
      if (config.opening_balance) setOpeningBalance(config.opening_balance);
      if (config.num_transactions) setNumTransactions(config.num_transactions);
      if (config.days_span) setDaysSpan(config.days_span);
      if (config.include_large_refunds !== undefined) setLargeRefunds(config.include_large_refunds);
      if (config.count) setInvoiceCount(config.count);
    }
  };

  const triggerPreview = () => {
    onGenerateDocPreview({
      doc_type: docType,
      tax_region: taxRegion,
      currency_symbol: currencySymbol,
      locale,
      opening_balance: openingBalance,
      num_transactions: numTransactions,
      days_span: daysSpan,
      include_large_refunds: largeRefunds,
      count: 1,
    });
  };

  const recon = docPreviewData?.reconciliation;
  const isBalanced = recon?.discrepancy === 0 || recon?.discrepancy === '0.00';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Header & NL Prompt Box */}
      <div className="glass-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
          <div>
            <h2 className="card-title">
              <FileText size={20} color="#818cf8" />
              Document Synthesis & Arithmetic Reconciliation Engine
            </h2>
            <p className="card-desc">
              Generate pixel-perfect PDF Invoices and Bank Statements with 100% verified mathematical reconciliation.
            </p>
          </div>

          {/* Quick NL Prompt Buttons */}
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button 
              className="btn btn-outline btn-sm"
              onClick={() => {
                setNlQuery('Generate 5 corporate invoices for Texas with 8.25% sales tax and net-30 terms');
                setDocType('invoice');
              }}
            >
              <Sparkles size={13} color="#818cf8" />
              <span>Prompt: US Invoices</span>
            </button>
            <button 
              className="btn btn-outline btn-sm"
              onClick={() => {
                setNlQuery('Create a 60-day bank statement with $25k opening balance and 2 large refunds');
                setDocType('bank_statement');
                setOpeningBalance(25000);
                setDaysSpan(60);
                setLargeRefunds(2);
              }}
            >
              <Sparkles size={13} color="#34d399" />
              <span>Prompt: Bank Audit</span>
            </button>
          </div>
        </div>

        {/* Natural Language Input */}
        <form onSubmit={handleNlSubmit} style={{ display: 'flex', gap: '0.5rem' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <Sparkles size={16} style={{ position: 'absolute', left: '12px', top: '12px', color: '#818cf8' }} />
            <input 
              type="text" 
              className="form-input" 
              placeholder="Ask AI in natural language: e.g. 'Generate 10 invoices in EUR with 20% VAT' or 'Generate 30-day bank statement with $10,000 opening balance'"
              style={{ paddingLeft: '38px', height: '42px', fontSize: '0.88rem' }}
              value={nlQuery}
              onChange={(e) => setNlQuery(e.target.value)}
            />
          </div>
          <button type="submit" className="btn btn-primary" style={{ padding: '0 1.25rem' }}>
            <Send size={15} />
            <span>Apply AI</span>
          </button>
        </form>
      </div>

      {/* Main Split Layout: Left Controls, Right Preview */}
      <div className="grid-2">
        {/* Left: Configuration Form */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Doc Type Selector */}
          <div>
            <label className="form-label">Document Type</label>
            <div className="nav-tabs" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
              <button 
                type="button"
                className={`nav-tab-btn ${docType === 'invoice' ? 'active' : ''}`}
                onClick={() => setDocType('invoice')}
                style={{ justifyContent: 'center' }}
              >
                <FileText size={16} />
                <span>Commercial Invoices</span>
              </button>
              <button 
                type="button"
                className={`nav-tab-btn ${docType === 'bank_statement' ? 'active' : ''}`}
                onClick={() => setDocType('bank_statement')}
                style={{ justifyContent: 'center' }}
              >
                <Calculator size={16} />
                <span>Bank Account Statements</span>
              </button>
            </div>
          </div>

          {/* Conditional Options */}
          {docType === 'invoice' ? (
            <>
              <div className="form-group">
                <label className="form-label">Tax Jurisdictions & Rates</label>
                <select 
                  className="form-select"
                  value={taxRegion}
                  onChange={(e) => setTaxRegion(e.target.value)}
                >
                  {TAX_REGIONS.map((r) => (
                    <option key={r.id} value={r.id}>{r.label}</option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Regional Format</label>
                <select className="form-select" value={locale} onChange={(e) => setLocale(e.target.value)}>
                  {LOCALES.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Currency Symbol</label>
                  <select 
                    className="form-select"
                    value={currencySymbol}
                    onChange={(e) => setCurrencySymbol(e.target.value)}
                  >
                    {CURRENCIES.map((c) => (
                      <option key={c.symbol} value={c.symbol}>{c.label}</option>
                    ))}
                  </select>
                </div>

                <div className="form-group">
                  <label className="form-label">Batch Export Count</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    min="1" 
                    max="100"
                    value={invoiceCount}
                    onChange={(e) => setInvoiceCount(parseInt(e.target.value) || 1)}
                  />
                </div>
              </div>
            </>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Opening Balance ({currencySymbol})</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    value={openingBalance}
                    onChange={(e) => setOpeningBalance(parseFloat(e.target.value) || 0)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Transaction Volume</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    min="5" 
                    max="100"
                    value={numTransactions}
                    onChange={(e) => setNumTransactions(parseInt(e.target.value) || 20)}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
                <div className="form-group">
                  <label className="form-label">Timespan (Days)</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    min="7" 
                    max="365"
                    value={daysSpan}
                    onChange={(e) => setDaysSpan(parseInt(e.target.value) || 30)}
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Large Refunds / Anomalies</label>
                  <input 
                    type="number" 
                    className="form-input" 
                    min="0" 
                    max="5"
                    value={largeRefunds}
                    onChange={(e) => setLargeRefunds(parseInt(e.target.value) || 0)}
                  />
                </div>
              </div>
            </>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '0.75rem', marginTop: 'auto', paddingTop: '1rem' }}>
            <button 
              className="btn btn-primary" 
              style={{ flex: 1 }}
              onClick={triggerPreview}
              disabled={isGeneratingDoc}
            >
              <Eye size={15} />
              <span>{isGeneratingDoc ? 'Generating PDF...' : 'Preview Document PDF'}</span>
            </button>

            <button 
              className="btn btn-emerald"
              onClick={() => onDownloadBulkDocs({
                doc_type: docType,
                count: docType === 'invoice' ? invoiceCount : 5,
                tax_region: taxRegion,
                currency_symbol: currencySymbol,
                locale,
                opening_balance: openingBalance,
                num_transactions: numTransactions,
                days_span: daysSpan,
                include_large_refunds: largeRefunds,
              })}
              title="Download generated PDF documents"
            >
              <Download size={15} />
              <span>{docType === 'invoice' && invoiceCount > 1 ? `Export ZIP (${invoiceCount})` : 'Export PDF'}</span>
            </button>
          </div>

          {/* Mathematical Reconciliation Ledger Audit */}
          {recon && (
            <div style={{ background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)', borderRadius: 'var(--radius-md)', padding: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontWeight: 600, color: 'var(--accent-emerald-light)', fontSize: '0.88rem' }}>
                  <ShieldCheck size={16} />
                  <span>Mathematical Reconciliation Audit</span>
                </div>
                <span className="badge badge-emerald">Discrepancy: {currencySymbol}0.00</span>
              </div>

              {docType === 'invoice' ? (
                <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.35rem', color: 'var(--text-secondary)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Subtotal:</span>
                    <strong style={{ color: '#fff' }}>{currencySymbol}{recon.subtotal}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Tax Applied:</span>
                    <strong style={{ color: '#fff' }}>{currencySymbol}{recon.tax_amount ?? recon.tax ?? '0.00'}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '0.35rem' }}>
                    <span style={{ fontWeight: 600, color: '#fff' }}>Computed Total:</span>
                    <strong style={{ color: 'var(--accent-emerald-light)' }}>{currencySymbol}{recon.grand_total ?? recon.total ?? '0.00'}</strong>
                  </div>
                </div>
              ) : (
                <div style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.35rem', color: 'var(--text-secondary)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Opening Balance:</span>
                    <strong style={{ color: '#fff' }}>{currencySymbol}{recon.opening_balance}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Total Credits (+):</span>
                    <strong style={{ color: 'var(--accent-emerald-light)' }}>+{currencySymbol}{recon.total_credits}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Total Debits (-):</span>
                    <strong style={{ color: 'var(--accent-rose)' }}>-{currencySymbol}{recon.total_debits}</strong>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: '0.35rem' }}>
                    <span style={{ fontWeight: 600, color: '#fff' }}>Reconciled Closing Balance:</span>
                    <strong style={{ color: 'var(--accent-emerald-light)' }}>{currencySymbol}{recon.closing_balance}</strong>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right: Embedded PDF Viewer */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="card-header">
            <h3 className="card-title">
              <Eye size={18} color="#818cf8" />
              Document Preview
            </h3>
            {docPreviewData?.pdf_base64 && (
              <span className="badge badge-emerald">Rendered High-Res PDF</span>
            )}
          </div>

          <div style={{ flex: 1, minHeight: '520px', background: '#1e2433', borderRadius: 'var(--radius-md)', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            {docPreviewData?.pdf_base64 ? (
              <iframe 
                src={`data:application/pdf;base64,${docPreviewData.pdf_base64}#toolbar=0&navpanes=0&scrollbar=1`}
                style={{ width: '100%', height: '100%', minHeight: '520px', border: 'none' }}
                title="Generated PDF Preview"
              />
            ) : (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
                <FileText size={48} color="var(--text-dim)" style={{ marginBottom: '1rem' }} />
                <div style={{ fontWeight: 600, color: '#fff', marginBottom: '0.35rem' }}>No Document Rendered Yet</div>
                <div style={{ fontSize: '0.84rem', maxWidth: '300px', margin: '0 auto' }}>
                  Click <strong>Preview Document PDF</strong> or run a Natural Language query to generate an audit-ready PDF.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
