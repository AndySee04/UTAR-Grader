import axios from "axios";

const API_URL = "/api";

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

function hasAuthorizationHeader(config) {
  const h = config.headers;
  if (!h) return false;
  if (h.Authorization) return true;
  if (typeof h.get === "function" && h.get("Authorization")) return true;
  return false;
}

// Add auth token to requests (do not overwrite an explicit Authorization — used when
// token is snapshotted before a long-running call so logout mid-flight cannot strip auth.)
api.interceptors.request.use((config) => {
  if (hasAuthorizationHeader(config)) {
    return config;
  }
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  },
);

// Auth
export const authAPI = {
  register: (data) => api.post("/auth/register", data),
  verifyEmail: (token) =>
    api.get("/auth/verify-email", { params: { token } }),
  forgotPassword: (data) => api.post("/auth/forgot-password", data),
  resetPassword: (data) => api.post("/auth/reset-password", data),
  login: (data) => api.post("/auth/login", data),
  getMe: () => api.get("/auth/me"),
};

// Exams
export const examsAPI = {
  create: (data) => api.post("/exams", data),
  list: () => api.get("/exams"),
  get: (id) => api.get(`/exams/${id}`),
  update: (id, data) => api.put(`/exams/${id}`, data),
  delete: (id) => api.delete(`/exams/${id}`),
};

// Documents
export const documentsAPI = {
  upload: (examId, file, docType, fileName) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);
    if (fileName) formData.append("file_name", fileName);
    return api.post(`/exams/${examId}/upload`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  uploadMultiple: (examId, files, docType) => {
    const formData = new FormData();
    files.forEach((file) => formData.append("files", file));
    formData.append("doc_type", docType);
    return api.post(`/exams/${examId}/upload-multiple`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  list: (examId, docType) =>
    api.get(`/exams/${examId}/documents`, { params: { doc_type: docType } }),
  getPages: (docId) => api.get(`/documents/${docId}/pages`),
  getPageImage: (docId, pageNumber) =>
    api.get(`/documents/${docId}/pages/${pageNumber}/image`, { responseType: 'blob' }),
  getRegions: (docId) => api.get(`/${docId}/regions`),
  saveCrop: (docId, payload) => api.post(`/${docId}/crop`, payload),
  saveRegionsOrder: (docId, regionIds) =>
    api.put(`/${docId}/regions/order`, { region_ids: regionIds }),
  rename: (docId, fileName) =>
    api.patch(`/${docId}`, { file_name: fileName }),
  delete: (id) => api.delete(`/${id}`),
};

// Phone Capture Sessions
export const captureAPI = {
  createSession: (examId, docType, frontendBaseUrl) =>
    api.post(`/exams/${examId}/capture-sessions`, {
      doc_type: docType,
      frontend_base_url: frontendBaseUrl,
    }),
  getSessionOwner: (examId, sessionId) =>
    api.get(`/exams/${examId}/capture-sessions/${sessionId}`),
  getSessionPublic: (sessionId, token) =>
    api.get(`/capture-sessions/${sessionId}`, { params: { token } }),
  listPages: (sessionId, token) =>
    api.get(`/capture-sessions/${sessionId}/pages`, { params: { token } }),
  uploadPage: (sessionId, token, file) => {
    const formData = new FormData();
    formData.append("token", token);
    formData.append("file", file);
    return api.post(`/capture-sessions/${sessionId}/pages`, formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  deletePage: (sessionId, pageId, token) =>
    api.delete(`/capture-sessions/${sessionId}/pages/${pageId}`, { params: { token } }),
  finalizeSession: (sessionId, token, pageIds = [], fileName = null) =>
    api.post(`/capture-sessions/${sessionId}/finalize`, {
      token,
      page_ids: pageIds,
      ...(fileName != null && String(fileName).trim() !== ""
        ? { file_name: String(fileName).trim() }
        : {}),
    }),
  continueSession: (sessionId, token) =>
    api.post(`/capture-sessions/${sessionId}/continue`, {
      token,
    }),
};

// Processing
export const processingAPI = {
  runOCR: (regionId) => api.post(`/regions/${regionId}/ocr`),
  deleteRegion: (regionId) => api.delete(`/regions/${regionId}`),
  updateRegionText: (regionId, data) =>
    api.patch(`/regions/${regionId}`, data),
  cleanupText: (regionId) => api.post(`/regions/${regionId}/cleanup`),
};

// Marking Guide
export const markingGuideAPI = {
  generate: (examId, useLLM = true) =>
    api.post(`/exams/${examId}/generate-guide`, { use_llm: useLLM }),
  get: (examId) => api.get(`/exams/${examId}/marking-guide`),
  addQuestion: (examId, data) =>
    api.post(`/exams/${examId}/marking-guide`, data),
  updateQuestion: (guideId, data) => api.put(`/marking-guide/${guideId}`, data),
  deleteQuestion: (guideId) => api.delete(`/marking-guide/${guideId}`),
};

// Grading
export const gradingAPI = {
  /** Snapshots token at call time so grading can start even if user logs out before the request finishes. */
  start: (examId, payload = {}) => {
    const token =
      typeof window !== "undefined" ? localStorage.getItem("token") : null;
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    return api.post(
      `/exams/${examId}/grade`,
      { process_all: true, ...payload },
      { headers },
    );
  },
  getGrades: (examId) => api.get(`/exams/${examId}/grades`),
  overrideGrade: (gradeId, data) => api.put(`/grades/${gradeId}`, data),
};

// Reports
export const reportsAPI = {
  downloadExcel: (examId) =>
    api.get(`/exams/${examId}/report/excel`, { responseType: "blob" }),
  downloadStudentPDF: (examId, docId) =>
    api.get(`/exams/${examId}/report/pdf/${docId}`, { responseType: "blob" }),
  downloadAllPDFs: (examId) =>
    api.get(`/exams/${examId}/report/all-pdfs`, { responseType: "blob" }),
};

// Account
export const accountAPI = {
  get: () => api.get("/account"),
  update: (data) => api.put("/account", data),
  uploadProfilePicture: (file) => {
    const formData = new FormData();
    formData.append("file", file);
    return api.post("/account/profile-picture", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  removeProfilePicture: () => api.delete("/account/profile-picture"),
  changePassword: (data) => api.put("/account/password", data),
  delete: () => api.delete("/account"),
};

export default api;
