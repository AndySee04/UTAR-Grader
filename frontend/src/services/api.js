import axios from "axios";

const API_URL = "/api";

const api = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
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
  login: (data) => api.post("/auth/login", data),
  getMe: () => api.get("/auth/me"),
  logout: () => api.post("/auth/logout"),
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
  upload: (examId, file, docType, studentName) => {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);
    if (studentName) formData.append("student_name", studentName);
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
  delete: (id) => api.delete(`/${id}`),
};

// Processing
export const processingAPI = {
  processExam: (examId) => api.post(`/exams/${examId}/process`),
  detectRegions: (docId, pageNumber) =>
    api.post(`/documents/${docId}/detect-regions`, null, {
      params: { page_number: pageNumber },
    }),
  runOCR: (regionId) => api.post(`/regions/${regionId}/ocr`),
  deleteRegion: (regionId) => api.delete(`/regions/${regionId}`),
  updateRegionText: (regionId, data) =>
    api.patch(`/regions/${regionId}`, data),
  cleanupText: (regionId) => api.post(`/regions/${regionId}/cleanup`),
  checkOCRHealth: () => api.get("/health/ocr"),
  checkLLMHealth: () => api.get("/health/llm"),
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
  start: (examId, payload = {}) =>
    api.post(`/exams/${examId}/grade`, { process_all: true, ...payload }),
  getGrades: (examId) => api.get(`/exams/${examId}/grades`),
  getStudentGrades: (examId, docId) =>
    api.get(`/exams/${examId}/grades/${docId}`),
  overrideGrade: (gradeId, data) => api.put(`/grades/${gradeId}`, data),
  getProgress: (examId) => api.get(`/exams/${examId}/progress`),
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
