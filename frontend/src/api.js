import axios from 'axios';

const API_BASE = '/api';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const api = {
  // Session
  createSession: async () => {
    const res = await apiClient.post('/session');
    return res.data;
  },

  // Schema Ingestion
  uploadCsv: async (file, sessionId, tableName = 'uploaded_table') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', sessionId);
    formData.append('table_name', tableName);
    const res = await apiClient.post('/schema/upload-csv', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return res.data;
  },

  schemaFromJson: async (schema, sessionId) => {
    const res = await apiClient.post('/schema/from-json', { schema, session_id: sessionId });
    return res.data;
  },

  schemaFromSql: async (ddl, sessionId) => {
    const res = await apiClient.post('/schema/from-sql', { ddl, session_id: sessionId });
    return res.data;
  },

  loadPreset: async (preset, sessionId) => {
    const res = await apiClient.post('/schema/preset', { preset, session_id: sessionId });
    return res.data;
  },

  setCustomSchema: async (schema, sessionId) => {
    const res = await apiClient.post('/schema/custom', { schema, session_id: sessionId });
    return res.data;
  },

  listPresets: async () => {
    const res = await apiClient.get('/presets');
    return res.data;
  },

  // AI Features
  aiInferSchema: async (sampleRows, provider = 'gemini') => {
    const res = await apiClient.post('/ai/infer-schema', { sample_rows: sampleRows, provider });
    return res.data;
  },

  aiSuggestEdgeCases: async (fields, sessionId, provider = 'gemini') => {
    const res = await apiClient.post('/ai/suggest-edge-cases', { fields, session_id: sessionId, provider });
    return res.data;
  },

  aiParseDocQuery: async (query, provider = 'gemini') => {
    const res = await apiClient.post('/ai/parse-document-query', { query, provider });
    return res.data;
  },

  // Generation
  generateData: async (config) => {
    const res = await apiClient.post('/generate', config);
    return res.data;
  },

  generatePreview: async (config) => {
    const res = await apiClient.post('/generate/preview', config);
    return res.data;
  },

  // Documents
  generateDocuments: async (params) => {
    const res = await apiClient.post('/documents/generate', params, {
      responseType: 'blob',
    });
    return res;
  },

  previewDocument: async (params) => {
    const res = await apiClient.post('/documents/preview', params);
    return res.data;
  },

  // Export
  exportData: async (sessionId, format = 'csv') => {
    const res = await apiClient.post('/export', { session_id: sessionId, format }, {
      responseType: 'blob',
    });
    return res;
  },

  // Validation
  validateData: async (sessionId) => {
    const res = await apiClient.post('/validate', { session_id: sessionId });
    return res.data;
  },

  // ER Diagram
  getErDiagram: async (sessionId) => {
    const res = await apiClient.post('/er-diagram', { session_id: sessionId });
    return res.data;
  },
};
