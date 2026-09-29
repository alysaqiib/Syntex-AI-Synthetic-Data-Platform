import React, { useState } from 'react';
import { 
  Share2, 
  Play, 
  CheckCircle2, 
  AlertTriangle, 
  Link2, 
  Layers, 
  ArrowRight,
  Database,
  ExternalLink,
  ShieldCheck
} from 'lucide-react';

export default function RelationalView({
  schema,
  setSchema,
  generatedData,
  erDiagram,
  validation,
  onGenerateRelational,
  isGenerating,
}) {
  const [activeTable, setActiveTable] = useState(schema?.tables?.[0]?.name || '');
  const [hoveredNode, setHoveredNode] = useState(null);

  const tables = schema?.tables || [];
  const currentTable = tables.find((t) => t.name === activeTable) || tables[0];
  const tableData = generatedData?.[currentTable?.name] || [];

  const updateTableRowCount = (tableName, value) => {
    const nextCount = Math.max(1, Math.min(100000, parseInt(value, 10) || 1));
    setSchema({
      ...schema,
      tables: schema.tables.map((table) => (
        table.name === tableName ? { ...table, row_count: nextCount } : table
      )),
    });
  };

  // Compute total records generated across all relational tables
  const totalRecords = Object.values(generatedData || {}).reduce((acc, df) => acc + (df?.length || 0), 0);

  // Read integrity and reconciliation from the backend's actual validation checks.
  const refCheck = validation?.checks?.find((check) => check.name === 'Referential Integrity');
  const reconciliationCheck = validation?.checks?.find((check) => check.name === 'Mathematical Reconciliation');
  const refIntegrity = {
    valid: refCheck?.status === 'pass',
    orphans: refCheck?.orphan_count ?? null,
    integrity_score: refCheck?.status === 'pass'
      ? 1
      : refCheck?.status === 'fail'
        ? 0
        : null,
  };

  // Mock node positions for SVG ER Diagram if not pre-calculated
  const nodePositions = {
    customers: { x: 80, y: 70 },
    departments: { x: 80, y: 100 },
    orders: { x: 380, y: 70 },
    employees: { x: 420, y: 100 },
    order_items: { x: 680, y: 70 },
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Relational Control Card */}
      <div className="glass-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 className="card-title">
              <Share2 size={20} color="#818cf8" />
              Relational Integrity & Schema Engine
            </h2>
            <p className="card-desc">
              Generate interconnected databases with strict foreign key constraints, zero orphan keys, and cross-table financial reconciliation.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button 
              className="btn btn-emerald" 
              onClick={onGenerateRelational}
              disabled={isGenerating || !tables.length}
            >
              <Play size={15} />
              <span>{isGenerating ? 'Synthesizing Network...' : 'Generate Relational Database'}</span>
            </button>
          </div>
        </div>

        <div style={{ marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-subtle)' }}>
          <div className="form-label">Rows per table</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem' }}>
            {tables.map((table) => (
              <label key={table.name} style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                {table.name}
                <input
                  type="number"
                  className="form-input"
                  min="1"
                  max="100000"
                  value={table.row_count}
                  onChange={(event) => updateTableRowCount(table.name, event.target.value)}
                />
              </label>
            ))}
          </div>
        </div>

        {/* Referential KPI Row */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-subtle)' }}>
          <div className="metric-card">
            <span className="metric-label">Referential Integrity Score</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="metric-value" style={{ color: refIntegrity.orphans === 0 ? 'var(--accent-emerald)' : 'var(--accent-amber)' }}>
                {refIntegrity.integrity_score === null ? '—' : `${(refIntegrity.integrity_score * 100).toFixed(0)}%`}
              </span>
              <CheckCircle2 size={20} color={refIntegrity.valid ? 'var(--accent-emerald)' : 'var(--accent-amber)'} />
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Orphan foreign keys reported by validation</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Tables in Topology</span>
            <div className="metric-value">{tables.length}</div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Parent-Child Cascade Rules Enforced</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Total Relational Records</span>
            <div className="metric-value">{totalRecords.toLocaleString()}</div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Multi-table synchronized state</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Financial Reconciliation</span>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="metric-value" style={{ color: 'var(--accent-emerald)', fontSize: '1.4rem' }}>
                {reconciliationCheck?.status === 'pass'
                  ? 'MATCH'
                  : reconciliationCheck?.status === 'fail'
                    ? 'REVIEW'
                    : 'Not measured'}
              </span>
              <ShieldCheck size={20} color="var(--accent-emerald)" />
            </div>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Order Total == Sum(Items)</span>
          </div>
        </div>
      </div>

      {/* Interactive ER Diagram Canvas */}
      <div className="glass-card">
        <div className="card-header">
          <h3 className="card-title">
            <Link2 size={18} color="#818cf8" />
            Interactive Entity-Relationship (ER) Topology
          </h3>
          <span className="badge badge-indigo">Multi-Table Foreign Keys</span>
        </div>

        <div style={{ 
          background: 'rgba(10, 13, 20, 0.75)', 
          border: '1px solid var(--border-subtle)', 
          borderRadius: 'var(--radius-md)', 
          padding: '1.5rem', 
          minHeight: '260px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          position: 'relative',
          overflowX: 'auto'
        }}>
          {/* SVG Canvas for Relationship Connectors */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '2rem', flexWrap: 'wrap', justifyContent: 'center' }}>
            {tables.map((t, idx) => {
              const isActive = t.name === currentTable?.name;
              return (
                <div key={t.name} style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
                  {/* Table Box */}
                  <div 
                    onClick={() => setActiveTable(t.name)}
                    style={{
                      background: isActive ? 'rgba(99, 102, 241, 0.15)' : 'var(--bg-secondary)',
                      border: `1px solid ${isActive ? 'var(--accent-primary)' : 'var(--border-medium)'}`,
                      borderRadius: 'var(--radius-md)',
                      width: '240px',
                      boxShadow: isActive ? 'var(--shadow-glow)' : 'var(--shadow-sm)',
                      cursor: 'pointer',
                      transition: 'all 0.2s ease',
                      overflow: 'hidden'
                    }}
                  >
                    {/* Header */}
                    <div style={{ 
                      background: isActive ? 'var(--accent-primary)' : 'rgba(255, 255, 255, 0.05)', 
                      padding: '0.5rem 0.85rem',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      color: '#fff',
                      fontWeight: 600,
                      fontSize: '0.88rem'
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                        <Database size={14} />
                        <span>{t.name}</span>
                      </div>
                      <span style={{ fontSize: '0.72rem', opacity: 0.85 }}>{t.row_count} rows</span>
                    </div>

                    {/* Columns List */}
                    <div style={{ padding: '0.65rem 0.85rem', display: 'flex', flexDirection: 'column', gap: '0.35rem', maxHeight: '180px', overflowY: 'auto' }}>
                      {t.fields.map((f) => (
                        <div key={f.name} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.76rem' }}>
                          <span style={{ fontFamily: 'var(--font-mono)', color: f.is_primary_key ? 'var(--accent-amber)' : 'var(--text-primary)' }}>
                            {f.name}
                          </span>
                          <div style={{ display: 'flex', gap: '0.25rem' }}>
                            {f.is_primary_key && <span className="badge badge-amber" style={{ fontSize: '0.6rem', padding: '0.1rem 0.3rem' }}>PK</span>}
                            {t.foreign_keys?.some((fk) => fk.constrained_columns?.includes(f.name)) && (
                              <span className="badge badge-indigo" style={{ fontSize: '0.6rem', padding: '0.1rem 0.3rem' }}>FK</span>
                            )}
                            <span style={{ color: 'var(--text-dim)', fontSize: '0.7rem' }}>{f.data_type}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Connector Arrow to next table if relations exist */}
                  {idx < tables.length - 1 && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.25rem' }}>
                      <span style={{ fontSize: '0.68rem', fontFamily: 'var(--font-mono)', color: 'var(--accent-emerald)' }}>
                        1 : N
                      </span>
                      <ArrowRight size={22} color="var(--accent-primary)" />
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Relational Table Data Inspector */}
      <div className="glass-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ fontWeight: 600 }}>Active Table Inspector:</span>
            <div className="nav-tabs" style={{ padding: '0.15rem' }}>
              {tables.map((t) => (
                <button
                  key={t.name}
                  className={`nav-tab-btn ${currentTable?.name === t.name ? 'active' : ''}`}
                  onClick={() => setActiveTable(t.name)}
                  style={{ padding: '0.35rem 0.75rem', fontSize: '0.8rem' }}
                >
                  {t.name} ({generatedData?.[t.name]?.length || 0})
                </button>
              ))}
            </div>
          </div>

            <span className={`badge ${refCheck?.status === 'pass' ? 'badge-emerald' : 'badge-amber'}`}>
              {refCheck ? `${refCheck.orphan_count || 0} orphan(s)` : 'Not measured'}
            </span>
        </div>

        {/* Table View */}
        <div className="table-wrapper" style={{ maxHeight: '420px' }}>
          {tableData.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '40px' }}>#</th>
                  {Object.keys(tableData[0]).map((col) => (
                    <th key={col}>{col}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableData.slice(0, 30).map((row, rIdx) => (
                  <tr key={rIdx}>
                    <td style={{ color: 'var(--text-dim)', fontSize: '0.72rem' }}>{rIdx + 1}</td>
                    {Object.entries(row).map(([k, val], cIdx) => (
                      <td key={cIdx}>
                        {val === null || val === undefined ? (
                          <span style={{ color: 'var(--accent-amber)', fontStyle: 'italic', fontSize: '0.72rem' }}>NULL</span>
                        ) : (
                          String(val)
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div style={{ padding: '3rem 1.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
              <Layers size={36} color="var(--text-dim)" style={{ marginBottom: '0.5rem' }} />
              <div>No relational data generated yet. Click <strong>Generate Relational Database</strong> above.</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
