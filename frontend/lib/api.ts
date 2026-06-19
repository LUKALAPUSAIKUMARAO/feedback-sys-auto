import axios from "axios";
import Cookies from "js-cookie";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL: `${BASE_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = Cookies.get("access_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      Cookies.remove("access_token");
      if (typeof window !== "undefined") window.location.href = "/admin/login";
    }
    return Promise.reject(error);
  }
);

// ── Auth ─────────────────────────────────────────────────────────────────────

export const authApi = {
  login: (email: string, password: string) =>
    api.post("/auth/login", { email, password }).then((r) => r.data),
  me: () => api.get("/auth/me").then((r) => r.data),
};

// ── Admin ─────────────────────────────────────────────────────────────────────

export const trainersApi = {
  list: (params?: object) => api.get("/admin/trainers", { params }).then((r) => r.data),
  get: (id: string) => api.get(`/admin/trainers/${id}`).then((r) => r.data),
  create: (data: object) => api.post("/admin/trainers", data).then((r) => r.data),
  update: (id: string, data: object) => api.patch(`/admin/trainers/${id}`, data).then((r) => r.data),
};

export const programsApi = {
  list: (params?: object) => api.get("/admin/programs", { params }).then((r) => r.data),
  create: (data: object) => api.post("/admin/programs", data).then((r) => r.data),
};

export const batchesApi = {
  list: (params?: object) => api.get("/admin/batches", { params }).then((r) => r.data),
  get: (id: string) => api.get(`/admin/batches/${id}`).then((r) => r.data),
  create: (data: object) => api.post("/admin/batches", data).then((r) => r.data),
  getParticipants: (id: string, params?: object) =>
    api.get(`/admin/batches/${id}/participants`, { params }).then((r) => r.data),
  getRoster: (id: string) =>
    api.get(`/admin/batches/${id}/roster`).then((r) => r.data),
  uploadParticipants: (id: string, data: object) =>
    api.post(`/admin/batches/${id}/participants`, data).then((r) => r.data),
  uploadCSV: (id: string, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return api.post(`/admin/batches/${id}/participants/csv`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    }).then((r) => r.data);
  },
  sendFeedbackLinks: (id: string) =>
    api.post(`/admin/batches/${id}/send-feedback-links`).then((r) => r.data),
  registerGoogleForm: (id: string, data: { form_url: string; sheet_url?: string }) =>
    api.post(`/admin/batches/${id}/google-form`, data).then((r) => r.data),
  getGoogleForm: (id: string) =>
    api.get(`/admin/batches/${id}/google-form`).then((r) => r.data),
};

export const webhookApi = {
  status: (batchId: string) =>
    api.get(`/webhook/status/${batchId}`).then((r) => r.data),
};

export const participantsApi = {
  list: (params?: object) => api.get("/admin/participants", { params }).then((r) => r.data),
};

// ── Feedback ──────────────────────────────────────────────────────────────────

export const feedbackApi = {
  validate: (token: string) =>
    api.get(`/feedback/validate/${token}`).then((r) => r.data),
  submit: (data: object) => api.post("/feedback/submit", data).then((r) => r.data),
};

// ── Analytics ─────────────────────────────────────────────────────────────────

export const analyticsApi = {
  dashboard: () => api.get("/analytics/dashboard").then((r) => r.data),
  trainer: (id: string) => api.get(`/analytics/trainer/${id}`).then((r) => r.data),
  trainerHistory: (id: string) => api.get(`/analytics/trainer/${id}/history`).then((r) => r.data),
  program: (id: string) => api.get(`/analytics/program/${id}`).then((r) => r.data),
  chat: (data: object) => api.post("/analytics/chat", data).then((r) => r.data),
  triggerPipeline: (data: object) => api.post("/analytics/pipeline/trigger", data).then((r) => r.data),
  pipelineRuns: (batchId: string) => api.get(`/analytics/pipeline/runs/${batchId}`).then((r) => r.data),
  campaigns: () => api.get("/analytics/campaigns").then((r) => r.data),
  healthStatus: () => api.get("/analytics/health/status").then((r) => r.data),
};
