import React, { useState, useRef } from 'react';
import { 
  Upload, 
  Plus, 
  Trash2, 
  Play, 
  Download, 
  Search, 
  BarChart2, 
  Sliders, 
  FileCode, 
  FileSpreadsheet, 
  CheckCircle, 
  AlertCircle,
  HelpCircle,
  Lock
} from 'lucide-react';

const DATA_TYPES = [
  'integer', 'float', 'string', 'category', 'datetime', 'boolean',
  'email', 'phone', 'name', 'address', 'uuid', 'ssn', 'credit_card'
];

const DISTRIBUTIONS = ['uniform', 'normal', 'lognormal', 'bimodal', 'categorical'];
const PRIVACY_TRANSFORMS = ['none', 'mask', 'hash_sha256', 'laplace_noise', 'redact'];

export default function TabularView({
  schema,
  setSchema,
  generatedData,
  generatedRowCounts,
  onGenerate,
  onUploadCsv,
  onSchemaFromSql,
  isGenerating,
  seed,
  rowCount,
  setRowCount,
  nullRate,
  setNullRate,
  outlierRate,
  setOutlierRate,
  onExportSingleCsv,
}) {
  const [selectedTableIdx, setSelectedTableIdx] = useState(0);
  const [searchTerm, setSearchTerm] = useState('');
  const [showSqlModal, setShowSqlModal] = useState(false);
  const [sqlInput, setSqlInput] = useState('');
  const [selectedColumnStats, setSelectedColumnStats] = useState(null);
  const fileInputRef = useRef(null);

  const currentTable = schema?.tables?.[selectedTableIdx] || schema?.tables?.[0];
  const tableData = generatedData?.[currentTable?.name] || [];

  // Update a field definition
  const updateField = (fieldIdx, key, value) => {
    if (!schema || !currentTable) return;
    const newSchema = { ...schema };
    const table = newSchema.tables[selectedTableIdx];
    table.fields[fieldIdx] = { ...table.fields[fieldIdx], [key]: value };
    setSchema(newSchema);
  };

  // Add new field
  const addField = () => {
    if (!schema || !currentTable) return;
    const newSchema = { ...schema };
    const table = newSchema.tables[selectedTableIdx];
    table.fields.push({
      name: `new_col_${table.fields.length + 1}`,
      data_type: 'string',
      distribution: 'uniform',
      is_primary_key: false,
      is_nullable: true,
      privacy: 'none',
    });
    setSchema(newSchema);
  };

  // Delete field
  const deleteField = (fieldIdx) => {
    if (!schema || !currentTable) return;
    const newSchema = { ...schema };
    newSchema.tables[selectedTableIdx].fields.splice(fieldIdx, 1);
    setSchema(newSchema);
  };

  // Handle CSV file upload
  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      onUploadCsv(file);
    }
  };

  // Filtered rows for data table
  const filteredRows = tableData.filter((row) => {
    if (!searchTerm) return true;
    return Object.values(row).some((val) =>
      String(val).toLowerCase().includes(searchTerm.toLowerCase())
    );
  });

  // Calculate quick column stats
  const getColStats = (colName) => {
    if (!tableData.length) return null;
    const values = tableData.map((r) => r[colName]);
    const nulls = values.filter((v) => v === null || v === undefined || v === '').length;
    const distinct = new Set(values).size;
    const numericVals = values.filter((v) => typeof v === 'number' && !isNaN(v));
    const mean = numericVals.length ? (numericVals.reduce((a, b) => a + b, 0) / numericVals.length).toFixed(2) : null;
    const min = numericVals.length ? Math.min(...numericVals) : null;
    const max = numericVals.length ? Math.max(...numericVals) : null;

    return { nulls, distinct, mean, min, max, total: values.length };
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Config & Generation Bar */}
      <div className="glass-card">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 className="card-title">
              <FileSpreadsheet size={20} color="#818cf8" />
              Tabular Synthetic Generator
            </h2>
            <p className="card-desc">
              Ingest schema via CSV/DDL, configure realistic copula correlations, and synthesize privacy-safe rows.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <input 
              type="file" 
              ref={fileInputRef} 
              style={{ display: 'none' }} 
              accept=".csv"
              onChange={handleFileUpload}
            />
            <button 
              className="btn btn-outline btn-sm" 
              onClick={() => fileInputRef.current?.click()}
            >
              <Upload size={14} />
              <span>Upload CSV Sample</span>
            </button>

            <button 
              className="btn btn-outline btn-sm" 
              onClick={() => setShowSqlModal(true)}
            >
              <FileCode size={14} />
              <span>Import SQL DDL</span>
            </button>

            <button 
              className="btn btn-emerald" 
              onClick={onGenerate}
              disabled={isGenerating || !currentTable}
            >
              <Play size={15} />
              <span>{isGenerating ? 'Synthesizing...' : `Generate ${rowCount} Rows`}</span>
            </button>
          </div>
        </div>

        {/* Sliders Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginTop: '1.25rem', paddingTop: '1.25rem', borderTop: '1px solid var(--border-subtle)' }}>
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <span className="form-label" style={{ margin: 0 }}>Target Row Count</span>
              <span className="range-value">{rowCount.toLocaleString()}</span>
            </div>
            <input 
              type="range" 
              className="range-slider" 
              min="10" 
              max="5000" 
              step="50"
              value={rowCount}
              onChange={(e) => setRowCount(parseInt(e.target.value))}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <span className="form-label" style={{ margin: 0 }}>Null Ingestion Rate</span>
              <span className="range-value">{(nullRate * 100).toFixed(1)}%</span>
            </div>
            <input 
              type="range" 
              className="range-slider" 
              min="0" 
              max="0.20" 
              step="0.005"
              value={nullRate}
              onChange={(e) => setNullRate(parseFloat(e.target.value))}
            />
          </div>

          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
              <span className="form-label" style={{ margin: 0 }}>Outlier Injection Rate</span>
              <span className="range-value">{(outlierRate * 100).toFixed(1)}%</span>
            </div>
            <input 
              type="range" 
              className="range-slider" 
              min="0" 
              max="0.10" 
              step="0.005"
              value={outlierRate}
              onChange={(e) => setOutlierRate(parseFloat(e.target.value))}
            />
          </div>
        </div>
      </div>

      {/* Main Workspace Layout */}
      <div className="grid-sidebar-layout">
        {/* Left Column: Schema Fields Editor */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ fontWeight: 600, fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span>Table:</span>
              <span className="badge badge-indigo">{currentTable?.name || 'No Table'}</span>
            </div>
            <button className="btn btn-outline btn-sm" onClick={addField}>
              <Plus size={13} />
              <span>Add Field</span>
            </button>
          </div>

          {/* Fields list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '560px', overflowY: 'auto', paddingRight: '0.25rem' }}>
            {currentTable?.fields?.map((field, idx) => (
              <div 
                key={idx} 
                style={{ 
                  background: 'var(--bg-secondary)', 
                  border: '1px solid var(--border-subtle)', 
                  borderRadius: 'var(--radius-sm)', 
                  padding: '0.75rem',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <input 
                    type="text" 
                    className="form-input form-input-mono"
                    value={field.name}
                    onChange={(e) => updateField(idx, 'name', e.target.value)}
                    style={{ fontWeight: 600, width: '65%', padding: '0.25rem 0.5rem' }}
                  />
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                    {field.is_primary_key && (
                      <span className="badge badge-amber" title="Primary Key">PK</span>
                    )}
                    <button 
                      onClick={() => deleteField(idx)} 
                      style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', padding: '0.2rem' }}
                      title="Remove Field"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                  <div>
                    <label style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Type</label>
                    <select 
                      className="form-select" 
                      value={field.data_type}
                      onChange={(e) => updateField(idx, 'data_type', e.target.value)}
                      style={{ padding: '0.25rem 0.4rem', fontSize: '0.78rem' }}
                    >
                      {DATA_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>

                  <div>
                    <label style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Privacy Transform</label>
                    <select 
                      className="form-select" 
                      value={field.privacy || 'none'}
                      onChange={(e) => updateField(idx, 'privacy', e.target.value)}
                      style={{ padding: '0.25rem 0.4rem', fontSize: '0.78rem' }}
                    >
                      {PRIVACY_TRANSFORMS.map((pt) => <option key={pt} value={pt}>{pt}</option>)}
                    </select>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: Interactive Data Preview */}
        <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '0.75rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div style={{ fontWeight: 600, fontSize: '0.95rem' }}>Synthetic Records Preview</div>
              <span className="badge badge-emerald">
                {generatedRowCounts?.[currentTable?.name] ?? tableData.length} records generated ({tableData.length} shown)
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <div style={{ position: 'relative', width: '220px' }}>
                <Search size={14} style={{ position: 'absolute', left: '8px', top: '10px', color: 'var(--text-muted)' }} />
                <input 
                  type="text" 
                  className="form-input" 
                  placeholder="Filter rows..." 
                  style={{ paddingLeft: '28px', fontSize: '0.8rem', padding: '0.35rem 0.6rem 0.35rem 28px' }}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>

              {tableData.length > 0 && (
                <button 
                  className="btn btn-outline btn-sm" 
                  onClick={onExportSingleCsv}
                  title="Export Current Table CSV"
                >
                  <Download size={14} />
                  <span>CSV</span>
                </button>
              )}
            </div>
          </div>

          {/* Table Container */}
          <div className="table-wrapper" style={{ maxHeight: '520px' }}>
            {tableData.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '40px' }}>#</th>
                    {Object.keys(tableData[0]).map((col) => (
                      <th 
                        key={col} 
                        style={{ cursor: 'pointer' }}
                        onClick={() => setSelectedColumnStats(col)}
                        title="Click to view column statistical breakdown"
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                          <span>{col}</span>
                          <BarChart2 size={12} color="var(--text-dim)" />
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredRows.map((row, rIdx) => (
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
              <div style={{ padding: '3.5rem 1.5rem', textAlign: 'center', color: 'var(--text-secondary)' }}>
                <FileSpreadsheet size={38} color="var(--text-dim)" style={{ marginBottom: '0.75rem' }} />
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.25rem' }}>No Data Generated Yet</div>
                <div style={{ fontSize: '0.82rem', maxWidth: '360px', margin: '0 auto' }}>
                  Click <strong>Generate {rowCount} Rows</strong> above or upload a CSV sample to automatically extract distribution weights.
                </div>
              </div>
            )}
          </div>

          {/* Quick Column Stats Drawer */}
          {selectedColumnStats && (
            <div style={{ background: 'rgba(99, 102, 241, 0.08)', border: '1px solid rgba(99, 102, 241, 0.25)', borderRadius: 'var(--radius-sm)', padding: '0.75rem 1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                <span style={{ fontWeight: 600, color: '#a5b4fc', fontSize: '0.84rem' }}>
                  Stat Summary: <span style={{ fontFamily: 'var(--font-mono)' }}>{selectedColumnStats}</span>
                </span>
                {(() => {
                  const s = getColStats(selectedColumnStats);
                  if (!s) return null;
                  return (
                    <div style={{ display: 'flex', gap: '1rem', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                      <span>Nulls: <strong style={{ color: '#fff' }}>{s.nulls} ({((s.nulls / s.total) * 100).toFixed(1)}%)</strong></span>
                      <span>Distinct: <strong style={{ color: '#fff' }}>{s.distinct}</strong></span>
                      {s.mean && <span>Mean: <strong style={{ color: '#fff' }}>{s.mean}</strong></span>}
                      {s.min !== null && <span>Min: <strong style={{ color: '#fff' }}>{s.min}</strong></span>}
                      {s.max !== null && <span>Max: <strong style={{ color: '#fff' }}>{s.max}</strong></span>}
                    </div>
                  );
                })()}
              </div>
              <button 
                className="btn btn-outline btn-sm" 
                style={{ padding: '0.15rem 0.4rem', fontSize: '0.72rem' }}
                onClick={() => setSelectedColumnStats(null)}
              >
                Close
              </button>
            </div>
          )}
        </div>
      </div>

      {/* SQL Import Modal */}
      {showSqlModal && (
        <div className="modal-overlay" onClick={() => setShowSqlModal(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h3 className="card-title">
                <FileCode size={18} color="#818cf8" />
                Import Schema from SQL DDL
              </h3>
              <button className="btn btn-outline btn-sm" onClick={() => setShowSqlModal(false)}>✕</button>
            </div>
            <p className="card-desc" style={{ marginBottom: '1rem' }}>
              Paste your `CREATE TABLE` definitions. Syntex will extract columns, data types, primary keys, and foreign keys.
            </p>
            <textarea 
              className="form-textarea form-input-mono"
              rows={10}
              placeholder={`CREATE TABLE users (\n  id INT PRIMARY KEY,\n  email VARCHAR(255),\n  created_at TIMESTAMP\n);`}
              value={sqlInput}
              onChange={(e) => setSqlInput(e.target.value)}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button className="btn btn-outline" onClick={() => setShowSqlModal(false)}>Cancel</button>
              <button 
                className="btn btn-primary"
                onClick={() => {
                  onSchemaFromSql(sqlInput);
                  setShowSqlModal(false);
                }}
                disabled={!sqlInput.trim()}
              >
                Parse DDL
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
