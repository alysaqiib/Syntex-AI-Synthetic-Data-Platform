import React from 'react';
import { 
  Database, 
  Share2, 
  FileText, 
  RefreshCw,
  Sliders,
  Layers
} from 'lucide-react';

export default function Header({ 
  activeTab, 
  setActiveTab, 
  sessionId, 
  onLoadPreset, 
  currentPreset,
  onRunDemo,
  onExport,
  isGenerating,
  seed,
  setSeed,
  locale,
  setLocale
}) {
  return (
    <header className="navbar">
      {/* Brand */}
      <div className="brand-section">
        <div className="brand-logo">
          <Database size={20} color="#fff" />
        </div>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <h1 className="brand-title">SYNTEX</h1>
            <span className="brand-badge">HackDataV2</span>
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
            Privacy-Preserving Synthetic Engine
          </div>
        </div>
      </div>

      {/* Main Mode Navigation */}
      <nav className="nav-tabs">
        <button 
          className={`nav-tab-btn ${activeTab === 'tabular' ? 'active' : ''}`}
          onClick={() => setActiveTab('tabular')}
        >
          <Database size={16} />
          <span>Tabular Data</span>
        </button>

        <button 
          className={`nav-tab-btn ${activeTab === 'relational' ? 'active' : ''}`}
          onClick={() => setActiveTab('relational')}
        >
          <Share2 size={16} />
          <span>Relational Schema</span>
        </button>

        <button 
          className={`nav-tab-btn ${activeTab === 'documents' ? 'active' : ''}`}
          onClick={() => setActiveTab('documents')}
        >
          <FileText size={16} />
          <span>Document Engine</span>
        </button>

      </nav>

      {/* Actions & Session */}
      <div className="header-actions">
        {/* Preset Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Layers size={14} color="var(--text-muted)" />
          <select 
            className="form-select" 
            style={{ width: '135px', padding: '0.35rem 0.6rem', fontSize: '0.8rem' }}
            value={currentPreset}
            onChange={(e) => onLoadPreset(e.target.value)}
          >
            <option value="ecommerce">E-Commerce</option>
            <option value="hr">HR System</option>
            <option value="custom">Custom Schema</option>
          </select>
        </div>

        <select
          className="form-select"
          style={{ width: '125px', padding: '0.35rem 0.6rem', fontSize: '0.8rem' }}
          value={locale}
          onChange={(event) => setLocale(event.target.value)}
          title="Synthetic data locale"
        >
          <option value="en_PK">Pakistan</option>
          <option value="en_US">United States</option>
          <option value="en_GB">United Kingdom</option>
        </select>

        {/* Global Seed Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', background: 'var(--bg-secondary)', padding: '0.2rem 0.5rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)' }}>
          <Sliders size={13} color="var(--text-muted)" />
          <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Seed:</span>
          <input 
            type="number" 
            value={seed} 
            onChange={(e) => setSeed(parseInt(e.target.value) || 42)}
            style={{ width: '48px', background: 'transparent', border: 'none', color: '#a5b4fc', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}
          />
        </div>

        <button
          className="btn btn-emerald btn-sm"
          onClick={onRunDemo}
          disabled={isGenerating}
          title="Load and generate the judge demonstration scenario"
        >
          <RefreshCw size={14} />
          <span>Run Demo</span>
        </button>

        {/* Session Status Pill */}
        <div className="session-pill" title={`Active Ephemeral Session: ${sessionId}`}>
          <div className="pulse-dot"></div>
          <span>{sessionId ? `${sessionId.slice(0, 8)}...` : 'Connecting...'}</span>
        </div>
      </div>
    </header>
  );
}
