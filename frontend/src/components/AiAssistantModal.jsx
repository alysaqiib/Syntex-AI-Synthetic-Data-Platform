import React, { useState } from 'react';
import { 
  Sparkles, 
  AlertTriangle, 
  Check, 
  X, 
  Layers, 
  Cpu, 
  ArrowRight,
  Database
} from 'lucide-react';

export default function AiAssistantModal({
  isOpen,
  onClose,
  schema,
  onApplyEdgeCases,
  onInferSchema,
  isAiLoading,
}) {
  const [activeTab, setActiveTab] = useState('edge_cases'); // 'edge_cases' | 'schema_infer'
  const [provider, setProvider] = useState('gemini'); // 'gemini' | 'groq'
  
  // Edge cases state
  const [suggestedEdgeCases, setSuggestedEdgeCases] = useState([]);
  const [selectedEdgeCaseIndices, setSelectedEdgeCaseIndices] = useState(new Set());
  
  // Schema inference state
  const [sampleText, setSampleText] = useState('');

  if (!isOpen) return null;

  const handleFetchEdgeCases = async () => {
    const fields = schema?.tables?.flatMap((t) =>
      t.fields.map((f) => ({ name: f.name, data_type: f.data_type }))
    ) || [];

    const cases = await onApplyEdgeCases(fields, provider);
    if (cases && Array.isArray(cases)) {
      setSuggestedEdgeCases(cases);
      setSelectedEdgeCaseIndices(new Set(cases.map((_, i) => i)));
    }
  };

  const toggleEdgeCase = (idx) => {
    const next = new Set(selectedEdgeCaseIndices);
    if (next.has(idx)) next.delete(idx);
    else next.add(idx);
    setSelectedEdgeCaseIndices(next);
  };

  const handleInferSchema = async () => {
    if (!sampleText.trim()) return;
    await onInferSchema(sampleText, provider);
    onClose();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: '640px' }}>
        {/* Modal Header */}
        <div className="card-header" style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div style={{ width: '32px', height: '32px', borderRadius: '8px', background: 'linear-gradient(135deg, #818cf8, #c084fc)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Sparkles size={18} color="#fff" />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#fff' }}>
                AI Synthesizer Assistant
              </h3>
              <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                Powered by Free-Tier Gemini 1.5 Flash & Groq LLaMA-3.3-70B
              </p>
            </div>
          </div>

          <button className="btn btn-outline btn-sm" onClick={onClose}>
            <X size={15} />
          </button>
        </div>

        {/* AI Provider Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--bg-secondary)', padding: '0.5rem 0.85rem', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-subtle)', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
            <Cpu size={15} color="#818cf8" />
            <span>LLM Engine Provider:</span>
          </div>

          <div style={{ display: 'flex', gap: '0.4rem' }}>
            <button 
              className={`btn btn-sm ${provider === 'gemini' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setProvider('gemini')}
              style={{ padding: '0.2rem 0.6rem', fontSize: '0.78rem' }}
            >
              Google Gemini
            </button>
            <button 
              className={`btn btn-sm ${provider === 'groq' ? 'btn-primary' : 'btn-outline'}`}
              onClick={() => setProvider('groq')}
              style={{ padding: '0.2rem 0.6rem', fontSize: '0.78rem' }}
            >
              Groq (Fast LLaMA)
            </button>
          </div>
        </div>

        {/* Tabs: Edge cases vs Schema Infer */}
        <div className="nav-tabs" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', marginBottom: '1.25rem' }}>
          <button 
            className={`nav-tab-btn ${activeTab === 'edge_cases' ? 'active' : ''}`}
            onClick={() => setActiveTab('edge_cases')}
            style={{ justifyContent: 'center' }}
          >
            <AlertTriangle size={15} />
            <span>Adversarial Edge-Cases</span>
          </button>
          <button 
            className={`nav-tab-btn ${activeTab === 'schema_infer' ? 'active' : ''}`}
            onClick={() => setActiveTab('schema_infer')}
            style={{ justifyContent: 'center' }}
          >
            <Database size={15} />
            <span>NL Schema Ingestion</span>
          </button>
        </div>

        {/* Tab 1: Edge Cases */}
        {activeTab === 'edge_cases' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              Evaluate system resilience by asking the AI to inspect your schema and synthesize adversarial edge-cases (e.g. leap years, Unicode names, negative balances, burst volumes).
            </p>

            <button 
              className="btn btn-primary"
              onClick={handleFetchEdgeCases}
              disabled={isAiLoading}
            >
              <Sparkles size={15} />
              <span>{isAiLoading ? 'Analyzing Schema Fields...' : 'Generate Adversarial Edge Cases'}</span>
            </button>

            {suggestedEdgeCases.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '240px', overflowY: 'auto' }}>
                <span style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                  Select edge cases to inject into next generation:
                </span>
                {suggestedEdgeCases.map((ec, idx) => {
                  const isChecked = selectedEdgeCaseIndices.has(idx);
                  return (
                    <div 
                      key={idx}
                      onClick={() => toggleEdgeCase(idx)}
                      style={{ 
                        display: 'flex', 
                        alignItems: 'center', 
                        justifyContent: 'space-between',
                        padding: '0.6rem 0.85rem',
                        background: isChecked ? 'rgba(99, 102, 241, 0.12)' : 'var(--bg-secondary)',
                        border: `1px solid ${isChecked ? 'var(--accent-primary)' : 'var(--border-subtle)'}`,
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        fontSize: '0.82rem'
                      }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                        <span style={{ fontWeight: 600, color: '#fff' }}>{ec.field || ec.name || 'Edge Case'}</span>
                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.76rem' }}>{ec.description || ec.value}</span>
                      </div>
                      <div style={{ width: '18px', height: '18px', borderRadius: '4px', border: '1px solid var(--accent-primary)', display: 'flex', alignItems: 'center', justifyContent: 'center', background: isChecked ? 'var(--accent-primary)' : 'transparent' }}>
                        {isChecked && <Check size={13} color="#fff" />}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Natural Language Schema Ingestion */}
        {activeTab === 'schema_infer' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>
              Describe your desired dataset or paste sample raw text / CSV snippet, and the AI will infer column types, distributions, and relations.
            </p>

            <textarea 
              className="form-textarea form-input-mono"
              rows={6}
              placeholder="e.g. I need a healthcare database with patients (name, birth_date, blood_type, insurance_id) and appointments (date, diagnosis, copay_amount, doctor_name)"
              value={sampleText}
              onChange={(e) => setSampleText(e.target.value)}
            />

            <button 
              className="btn btn-emerald"
              onClick={handleInferSchema}
              disabled={isAiLoading || !sampleText.trim()}
            >
              <Sparkles size={15} />
              <span>{isAiLoading ? 'Inferring Schema...' : 'Synthesize Schema Definition'}</span>
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
