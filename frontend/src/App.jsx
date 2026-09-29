import React, { useState, useEffect, useRef } from 'react';
import Header from './components/Header';
import TabularView from './components/TabularView';
import RelationalView from './components/RelationalView';
import DocumentEngineView from './components/DocumentEngineView';
import ValidationView from './components/ValidationView';
import AiAssistantModal from './components/AiAssistantModal';
import { api } from './api';
import { CheckCircle, AlertCircle, Info } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('tabular');
  const [sessionId, setSessionId] = useState('');
  const [currentPreset, setCurrentPreset] = useState('ecommerce');
  const [schema, setSchema] = useState(null);
  const [generatedData, setGeneratedData] = useState({});
  const [generatedRowCounts, setGeneratedRowCounts] = useState({});
  const [erDiagram, setErDiagram] = useState(null);
  const [validation, setValidation] = useState(null);
  
  // Document state
  const [docPreviewData, setDocPreviewData] = useState(null);
  const [isGeneratingDoc, setIsGeneratingDoc] = useState(false);

  // Settings
  const [seed, setSeed] = useState(42);
  const [locale, setLocale] = useState('en_PK');
  const [rowCount, setRowCount] = useState(150);
  const [nullRate, setNullRate] = useState(0.02);
  const [outlierRate, setOutlierRate] = useState(0.01);
  const [activeEdgeCases, setActiveEdgeCases] = useState([]);

  // Loaders & Modals
  const [isGenerating, setIsGenerating] = useState(false);
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [isAiModalOpen, setIsAiModalOpen] = useState(false);
  const [toasts, setToasts] = useState([]);
  const sessionRequestRef = useRef(null);
  const userStartedFlowRef = useRef(false);
  const toastIdRef = useRef(0);

  const ensureSession = async () => {
    if (sessionId) return sessionId;
    if (!sessionRequestRef.current) {
      sessionRequestRef.current = api.createSession().then((response) => {
        setSessionId(response.session_id);
        return response.session_id;
      });
    }
    return sessionRequestRef.current;
  };

  const addToast = (message, type = 'info') => {
    const id = `${Date.now()}-${toastIdRef.current++}`;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  // Initialize session & default preset
  useEffect(() => {
    const initApp = async () => {
      try {
        const sid = await ensureSession();

        // Load default preset
        const presetRes = await api.loadPreset('ecommerce', sid);
        if (userStartedFlowRef.current) return;
        setSchema(presetRes.schema);
        setErDiagram(presetRes.er_diagram);

        // Generate initial data
        const genRes = await api.generateData({
          mode: 'relational',
          schema_def: presetRes.schema,
          seed: 42,
          null_rate: 0.02,
          outlier_rate: 0.01,
          locale,
          row_count: 100,
        });

        if (userStartedFlowRef.current) return;
        setGeneratedData(genRes.preview);
        setGeneratedRowCounts(genRes.row_counts || {});
        setValidation(genRes.validation);
        addToast('Connected to Syntex Ephemeral Engine. E-Commerce preset loaded.', 'success');
      } catch (err) {
        console.error('Failed to init session:', err);
        addToast('Connected to local dev mode.', 'info');
      }
    };

    initApp();
  }, []);

  // Handle Preset Switching
  const handleLoadPreset = async (presetName) => {
    setCurrentPreset(presetName);
    if (presetName === 'custom') {
      addToast('Switched to Custom Schema mode. Add fields or upload a sample.', 'info');
      return;
    }
    try {
      setIsGenerating(true);
      const res = await api.loadPreset(presetName, sessionId);
      setSchema(res.schema);
      setErDiagram(res.er_diagram);

      const genRes = await api.generateData({
        mode: 'relational',
        schema_def: res.schema,
        seed,
        null_rate: nullRate,
        outlier_rate: outlierRate,
        locale,
        row_count: rowCount,
      });

      setGeneratedData(genRes.preview);
      setGeneratedRowCounts(genRes.row_counts || {});
      setValidation(genRes.validation);
      addToast(`Loaded preset '${presetName}' with ${Object.keys(genRes.preview).length} tables.`, 'success');
    } catch (err) {
      console.error(err);
      addToast(`Error loading preset: ${err.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  const handleRunDemo = async () => {
    setActiveTab('relational');
    await handleLoadPreset('ecommerce');
    addToast('Judge demo ready: relational integrity and order reconciliation are visible.', 'success');
  };

  // Generate Tabular Data
  const handleGenerateTabular = async () => {
    if (!schema) return;
    try {
      setIsGenerating(true);
      const res = await api.generateData({
        mode: 'tabular',
        schema_def: schema,
        session_id: sessionId,
        seed,
        null_rate: nullRate,
        outlier_rate: outlierRate,
        locale,
        row_count: rowCount,
        edge_cases: activeEdgeCases,
      });

      setGeneratedData(res.preview);
      setGeneratedRowCounts(res.row_counts || {});
      setValidation(res.validation);
      addToast(`Successfully synthesized ${rowCount} rows with copula correlations!`, 'success');
    } catch (err) {
      console.error(err);
      addToast(`Generation failed: ${err.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  // Generate Relational Network
  const handleGenerateRelational = async () => {
    if (!schema) return;
    try {
      setIsGenerating(true);
      const res = await api.generateData({
        mode: 'relational',
        schema_def: schema,
        seed,
        null_rate: nullRate,
        outlier_rate: outlierRate,
        row_count: rowCount,
        edge_cases: activeEdgeCases,
      });

      setGeneratedData(res.preview);
      setGeneratedRowCounts(res.row_counts || {});
      setValidation(res.validation);
      addToast('Relational network synthesized and validated for referential integrity.', 'success');
    } catch (err) {
      console.error(err);
      addToast(`Relational generation failed: ${err.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  // Ingest CSV
  const handleUploadCsv = async (file) => {
    try {
      setIsGenerating(true);
      userStartedFlowRef.current = true;
      const activeSessionId = await ensureSession();
      const tableName = file.name.replace(/\.[^/.]+$/, '').replace(/[^a-zA-Z0-9_]/g, '_');
      const res = await api.uploadCsv(file, activeSessionId, tableName);
      
      const newSchema = { tables: [res.table] };
      setSchema(newSchema);
      setCurrentPreset('custom');

      const genRes = await api.generateData({
        mode: 'tabular',
        schema_def: newSchema,
        session_id: activeSessionId,
        seed,
        locale,
        row_count: rowCount,
      });

      setGeneratedData(genRes.preview);
      setGeneratedRowCounts(genRes.row_counts || {});
      setValidation(genRes.validation);
      addToast(`Ingested ${file.name}: Inferred ${res.table.fields.length} columns.`, 'success');
    } catch (err) {
      console.error(err);
      addToast(`CSV Ingestion failed: ${err.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  // Ingest SQL DDL
  const handleSchemaFromSql = async (ddl) => {
    try {
      setIsGenerating(true);
      const res = await api.schemaFromSql(ddl, sessionId);
      const newSchema = { tables: res.tables };
      setSchema(newSchema);
      setCurrentPreset('custom');

      const genRes = await api.generateData({
        mode: 'relational',
        schema_def: newSchema,
        seed,
        locale,
        row_count: rowCount,
      });

      setGeneratedData(genRes.preview);
      setGeneratedRowCounts(genRes.row_counts || {});
      setValidation(genRes.validation);
      addToast(`Parsed SQL DDL: Created ${res.tables.length} tables.`, 'success');
    } catch (err) {
      console.error(err);
      addToast(`SQL Parsing failed: ${err.message}`, 'error');
    } finally {
      setIsGenerating(false);
    }
  };

  // Document PDF Preview
  const handleGenerateDocPreview = async (params) => {
    try {
      setIsGeneratingDoc(true);
      const res = await api.previewDocument(params);
      setDocPreviewData(res);
      addToast('Document rendered with exact mathematical reconciliation!', 'success');
    } catch (err) {
      console.error(err);
      addToast(`Document preview failed: ${err.message}`, 'error');
    } finally {
      setIsGeneratingDoc(false);
    }
  };

  // Bulk Document Download
  const handleDownloadBulkDocs = async (params) => {
    try {
      addToast('Preparing document export bundle...', 'info');
      const res = await api.generateDocuments(params);
      const blob = new Blob([res.data], { type: res.headers['content-type'] });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const isZip = params.count > 1;
      a.download = isZip ? `${params.doc_type}_bulk.zip` : `${params.doc_type}_001.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      addToast('Document download completed.', 'success');
    } catch (err) {
      console.error(err);
      addToast(`Document export failed: ${err.message}`, 'error');
    }
  };

  // Export Data (CSV, JSON, SQL, ZIP)
  const handleExport = async (format) => {
    try {
      addToast(`Exporting data in ${format.toUpperCase()} format...`, 'info');
      const res = await api.exportData(sessionId, format);
      const blob = new Blob([res.data]);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `synthetic_data.${format === 'zip' ? 'zip' : format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      addToast(`Exported ${format.toUpperCase()} successfully.`, 'success');
    } catch (err) {
      console.error(err);
      addToast(`Export failed: ${err.message}`, 'error');
    }
  };

  // AI Edge Cases Fetcher
  const handleApplyEdgeCases = async (fields, provider) => {
    try {
      setIsAiLoading(true);
      const res = await api.aiSuggestEdgeCases(fields, sessionId, provider);
      setActiveEdgeCases(res.edge_cases || []);
      addToast(`Generated ${res.edge_cases?.length || 0} adversarial edge-cases.`, 'success');
      return res.edge_cases;
    } catch (err) {
      console.error(err);
      addToast(`AI Edge cases failed: ${err.message}`, 'error');
      return [];
    } finally {
      setIsAiLoading(false);
    }
  };

  // AI Schema Infer
  const handleInferSchema = async (sampleText, provider) => {
    try {
      setIsAiLoading(true);
      const res = await api.aiInferSchema([{ sample: sampleText }], provider);
      if (res.schema) {
        setSchema(res.schema);
        setCurrentPreset('custom');
        addToast('AI inferred schema synthesized!', 'success');
      }
    } catch (err) {
      console.error(err);
      addToast(`AI Schema inference failed: ${err.message}`, 'error');
    } finally {
      setIsAiLoading(false);
    }
  };

  return (
    <div className="app-container">
      {/* Global Header */}
      <Header 
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        sessionId={sessionId}
        onLoadPreset={handleLoadPreset}
        currentPreset={currentPreset}
        onOpenAiModal={() => setIsAiModalOpen(true)}
        onRunDemo={handleRunDemo}
        onExport={handleExport}
        isGenerating={isGenerating}
        seed={seed}
        setSeed={setSeed}
        locale={locale}
        setLocale={setLocale}
      />

      {/* Main Mode View */}
      <main className="main-content">
        {activeTab === 'tabular' && (
          <TabularView 
            schema={schema}
            setSchema={setSchema}
            generatedData={generatedData}
            generatedRowCounts={generatedRowCounts}
            onGenerate={handleGenerateTabular}
            onUploadCsv={handleUploadCsv}
            onSchemaFromSql={handleSchemaFromSql}
            isGenerating={isGenerating}
            seed={seed}
            rowCount={rowCount}
            setRowCount={setRowCount}
            nullRate={nullRate}
            setNullRate={setNullRate}
            outlierRate={outlierRate}
            setOutlierRate={setOutlierRate}
            onExportSingleCsv={() => handleExport('csv')}
          />
        )}

        {activeTab === 'relational' && (
          <RelationalView 
            schema={schema}
            setSchema={setSchema}
            generatedData={generatedData}
            erDiagram={erDiagram}
            validation={validation}
            onGenerateRelational={handleGenerateRelational}
            isGenerating={isGenerating}
          />
        )}

        {activeTab === 'documents' && (
          <DocumentEngineView 
            onGenerateDocPreview={handleGenerateDocPreview}
            onDownloadBulkDocs={handleDownloadBulkDocs}
            onNlDocParse={async (query) => {
              const res = await api.aiParseDocQuery(query);
              return res.config;
            }}
            docPreviewData={docPreviewData}
            isGeneratingDoc={isGeneratingDoc}
          />
        )}

        {activeTab === 'validation' && (
          <ValidationView 
            validation={validation}
            generatedData={generatedData}
            onExport={handleExport}
            sessionId={sessionId}
          />
        )}
      </main>

      {/* AI Assistant Modal */}
      <AiAssistantModal 
        isOpen={isAiModalOpen}
        onClose={() => setIsAiModalOpen(false)}
        schema={schema}
        onApplyEdgeCases={handleApplyEdgeCases}
        onInferSchema={handleInferSchema}
        isAiLoading={isAiLoading}
      />

      {/* Toast Notification Stack */}
      <div className="toast-container">
        {toasts.map((toast) => (
          <div key={toast.id} className="toast">
            {toast.type === 'success' ? (
              <CheckCircle size={16} color="var(--accent-emerald)" />
            ) : toast.type === 'error' ? (
              <AlertCircle size={16} color="var(--accent-rose)" />
            ) : (
              <Info size={16} color="var(--accent-primary)" />
            )}
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
