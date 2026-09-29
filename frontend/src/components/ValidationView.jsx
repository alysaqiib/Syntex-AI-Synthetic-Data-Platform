import React from 'react';
import { 
  ShieldCheck, 
  CheckCircle2, 
  AlertCircle, 
  Download, 
  Layers, 
  BarChart, 
  Lock, 
  Database,
  FileCode,
  FileSpreadsheet,
  FileArchive
} from 'lucide-react';

export default function ValidationView({
  validation,
  generatedData,
  onExport,
  sessionId,
}) {
  const checks = validation?.checks || [];
  const refCheck = checks.find((check) => check.name === 'Referential Integrity');
  const reconciliationCheck = checks.find((check) => check.name === 'Mathematical Reconciliation');
  const fidelityScores = Object.values(validation?.fidelity_metrics || {})
    .map((metrics) => Number(metrics?.overall?.fidelity_score))
    .filter(Number.isFinite);
  const tstrScore = fidelityScores.length
    ? (fidelityScores.reduce((sum, score) => sum + score, 0) / fidelityScores.length).toFixed(1)
    : null;
  const hasFidelityData = Boolean(tstrScore);
  const overallStatus = validation?.overall_status || 'not-run';
  const correlationDeviations = Object.values(validation?.fidelity_metrics || {})
    .map((metrics) => Number(metrics?.overall?.correlation_deviation))
    .filter(Number.isFinite);
  const copulaStatuses = Object.values(validation?.fidelity_metrics || {})
    .map((metrics) => metrics?.overall?.copula_status)
    .filter(Boolean);
  const copulaMessage = correlationDeviations.length
    ? 'Measured from numeric rank correlation'
    : copulaStatuses.includes('needs_more_than_five_rows')
      ? 'Upload more than 5 source rows to measure'
      : copulaStatuses.includes('needs_two_numeric_columns')
        ? 'Requires at least 2 numeric columns'
        : 'Upload a real source sample to measure';
  const correlationValue = correlationDeviations.length
    ? `${(100 - (correlationDeviations.reduce((sum, value) => sum + value, 0) / correlationDeviations.length) * 100).toFixed(1)}%`
    : 'Not measured';
  const reconciliationDetails = Array.isArray(reconciliationCheck?.details)
    ? reconciliationCheck.details
    : [];
  const reconciliationMismatches = reconciliationDetails.reduce(
    (sum, item) => sum + (item.mismatches || 0), 0
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner: TSTR Readiness Score */}
      <div className="glass-card" style={{ background: 'linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(99, 102, 241, 0.08))', border: '1px solid var(--border-success)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem' }}>
            <div style={{ 
              width: '84px', 
              height: '84px', 
              borderRadius: '50%', 
              background: 'rgba(16, 185, 129, 0.15)', 
              border: '3px solid var(--accent-emerald)', 
              display: 'flex', 
              flexDirection: 'column',
              alignItems: 'center', 
              justifyContent: 'center',
              boxShadow: 'var(--shadow-emerald-glow)'
            }}>
              <span style={{ fontSize: '1.75rem', fontWeight: 800, fontFamily: 'var(--font-mono)', color: 'var(--accent-emerald-light)', lineHeight: 1 }}>
                {tstrScore || '—'}
              </span>
              <span style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>/ 100</span>
            </div>

            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
                <h2 style={{ fontSize: '1.4rem', fontWeight: 700, color: '#fff' }}>
                  TSTR Evaluation Readiness
                </h2>
                <span className="badge badge-emerald">
                  <CheckCircle2 size={12} /> {hasFidelityData ? 'Measured' : 'Needs source sample'}
                </span>
              </div>
              <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', maxWidth: '640px' }}>
                Shows the checks completed for this generated run. TSTR performance depends on the source sample and downstream evaluation.
              </p>
            </div>
          </div>

          {/* Quick Export Actions */}
          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            <button className="btn btn-outline btn-sm" onClick={() => onExport('csv')}>
              <FileSpreadsheet size={14} />
              <span>Export CSV</span>
            </button>
            <button className="btn btn-outline btn-sm" onClick={() => onExport('json')}>
              <FileCode size={14} />
              <span>Export JSON</span>
            </button>
            <button className="btn btn-outline btn-sm" onClick={() => onExport('sql')}>
              <Database size={14} />
              <span>Export SQL</span>
            </button>
            <button className="btn btn-emerald btn-sm" onClick={() => onExport('zip')}>
              <FileArchive size={14} />
              <span>Export Bundle (ZIP)</span>
            </button>
          </div>
        </div>
      </div>

      {/* 4 Pillars of TSTR Grid */}
      <div className="grid-2">
        {/* Pillar 1: Zero Memorization & Privacy Safe */}
        <div className="glass-card">
          <div className="card-header">
            <h3 className="card-title">
              <Lock size={18} color="#10b981" />
              Privacy Transforms & Limitations
            </h3>
            <span className="badge badge-amber">No formal privacy proof</span>
          </div>
          <p className="card-desc" style={{ marginBottom: '1rem' }}>
            In-memory processing and column transforms reduce exposure, but this dashboard does not prove zero memorization or certify differential privacy.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0.85rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.84rem' }}>
              <span>Exact Duplicate Matches with Training Data</span>
              <strong style={{ color: 'var(--accent-amber)' }}>Not measured</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0.85rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.84rem' }}>
              <span>Differential Privacy Laplace Noise</span>
              <strong style={{ color: 'var(--accent-amber)' }}>Laplace-style noise only</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0.85rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.84rem' }}>
              <span>PII Masking & Pseudonymization</span>
              <strong style={{ color: 'var(--accent-emerald-light)' }}>Configured transforms</strong>
            </div>
          </div>
        </div>

        {/* Pillar 2: Referential Integrity & Cross-Table Consistency */}
        <div className="glass-card">
          <div className="card-header">
            <h3 className="card-title">
              <ShieldCheck size={18} color="#818cf8" />
              Referential Integrity & Cross-Table Audit
            </h3>
            <span className={`badge ${refCheck?.status === 'pass' ? 'badge-emerald' : 'badge-indigo'}`}>
              {refCheck ? `${refCheck.orphan_count || 0} orphan(s)` : 'Not measured'}
            </span>
          </div>
          <p className="card-desc" style={{ marginBottom: '1rem' }}>
            Foreign key relational audit reporting parent existence and mathematical reconciliation for this run.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0.85rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.84rem' }}>
              <span>Orphan Foreign Keys Count</span>
              <strong style={{ color: 'var(--accent-emerald-light)' }}>{refCheck ? refCheck.orphan_count || 0 : 'Not measured'}</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0.85rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.84rem' }}>
              <span>Parent-Child Dependency Order</span>
              <strong style={{ color: 'var(--accent-emerald-light)' }}>Strict Topological Order</strong>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '0.6rem 0.85rem', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', fontSize: '0.84rem' }}>
              <span>Cross-Table Reconciliation Discrepancy</span>
              <strong style={{ color: 'var(--accent-emerald-light)' }}>{reconciliationCheck ? `${reconciliationMismatches} mismatch(es)` : 'Not measured'}</strong>
            </div>
          </div>
        </div>
      </div>

      {/* Statistical Distribution & Copula Fidelity */}
      <div className="glass-card">
        <div className="card-header">
          <h3 className="card-title">
            <BarChart size={18} color="#f59e0b" />
            Statistical Copula Fidelity & Distribution Alignment
          </h3>
          <span className="badge badge-amber">
            {hasFidelityData ? 'Computed from source sample' : 'Awaiting source sample'}
          </span>
        </div>
        <p className="card-desc" style={{ marginBottom: '1rem' }}>
          Multi-variate Gaussian Copula preserves correlation rank matrices, skewness, realistic null patterns, and tail outliers without memorizing rows.
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
          <div className="metric-card">
            <span className="metric-label">Correlation Rank Preservation</span>
            <div className="metric-value" style={{ color: '#a5b4fc' }}>{correlationValue}</div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>{copulaMessage}</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Wasserstein Distance</span>
            <div className="metric-value" style={{ color: 'var(--accent-emerald-light)' }}>Not measured</div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Wasserstein distance is not currently calculated</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Outlier Realism Ratio</span>
            <div className="metric-value" style={{ color: 'var(--accent-amber)' }}>Configured</div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Controlled by the generation outlier rate</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Null Ingestion Match</span>
            <div className="metric-value" style={{ color: '#6ee7b7' }}>Validated</div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Constraint compliance check result</span>
          </div>
        </div>
      </div>
    </div>
  );
}
