/**
 * Cliente API — Yachay Deep
 *
 * [SEC-02] Fase 2: HttpOnly cookies. Usa credentials:"include" en vez de
 *          localStorage token. El backend setea/borra la cookie.
 * [SEC-07/BUG-03] Sanitización de mensajes de error.
 */h

const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function sanitizeErrorMessage(raw) {
  if (typeof raw !== "string") return "Error desconocido";
  return raw.replace(/<[^>]*>/g, "").replace(/[<>'"]/g, "").slice(0, 500);
}

class ApiClient {
  constructor() {
    this.baseUrl = BASE_URL;
  }

  async request(path, options = {}) {
    const isFormData = options.body instanceof FormData;
    const headers = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    };

    // [SEC-02] credentials: "include" envía la HttpOnly cookie automáticamente
    // [PERF-03] Timeout de 30s para evitar requests colgados
    const controller = options.signal ? null : new AbortController();
    const timeoutId = controller ? setTimeout(() => controller.abort(), 30000) : null;

    let response;
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...options,
        headers,
        credentials: "include",
        signal: options.signal || controller?.signal,
      });
    } catch (e) {
      if (timeoutId) clearTimeout(timeoutId);
      if (e.name === "AbortError" && !options.signal) {
        throw new Error("La solicitud tardó demasiado. Intenta de nuevo.");
      }
      throw e;
    } finally {
      if (timeoutId) clearTimeout(timeoutId);
    }

    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("yd:unauthorized"));
      throw new Error("No autenticado");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Error desconocido" }));
      const detail = error.detail;
      const message = Array.isArray(detail)
        ? detail.map(e => e.msg || e.message || JSON.stringify(e)).join("; ")
        : (typeof detail === "string" ? detail : `HTTP ${response.status}`);
      throw new Error(sanitizeErrorMessage(message));
    }

    if (response.headers.get("content-type")?.includes("application/pdf")) {
      return response.blob();
    }

    return response.json();
  }

  get(path, options = {}) { return this.request(path, options); }
  post(path, body) { return this.request(path, { method: "POST", body: JSON.stringify(body) }); }
  put(path, body) { return this.request(path, { method: "PUT", body: JSON.stringify(body) }); }
  patch(path, body) { return this.request(path, { method: "PATCH", body: JSON.stringify(body) }); }
  delete(path) { return this.request(path, { method: "DELETE" }); }

  async getBlob(path) {
    const response = await fetch(`${this.baseUrl}${path}`, {
      credentials: "include",
    });
    if (response.status === 401) {
      window.dispatchEvent(new CustomEvent("yd:unauthorized"));
      throw new Error("No autenticado");
    }
    if (!response.ok) {
      const err = await response.json().catch(() => ({ detail: "Error al descargar" }));
      throw new Error(sanitizeErrorMessage(err.detail || `HTTP ${response.status}`));
    }
    return response.blob();
  }

  // ── Auth ──
  login(email, password) {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    return this.request("/auth/login", { method: "POST", body: form, headers: {} });
  }
  logout() { return this.request("/auth/logout", { method: "POST" }); }
  me() { return this.get("/auth/me"); }
  createUser(data) { return this.post("/auth/users", data); }
  listUsers() { return this.get("/auth/users"); }

  // ── Students (PERF-01: paginado) ──
  searchStudents(q, carrera = "", options = {}) {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (carrera) params.set("carrera", carrera);
    if (options.page) params.set("page", options.page);
    if (options.limit) params.set("limit", options.limit);
    if (options.nivel_riesgo) params.set("nivel_riesgo", options.nivel_riesgo);
    return this.get(`/students/search?${params.toString()}`);
  }
  getFicha(studentId, periodo) {
    const qs = periodo ? `?periodo=${encodeURIComponent(periodo)}` : "";
    return this.get(`/students/${studentId}/ficha${qs}`);
  }
  getStudentComparativa(studentId) { return this.get(`/students/${studentId}/comparativa`); }

  // ── Interventions ──
  createIntervention(data) { return this.post("/interventions/", data); }
  listInterventions(studentId) { return this.get(`/interventions/?student_id=${studentId}`); }
  interventionStats() { return this.get("/interventions/stats"); }
  updateIntervention(id, data) { return this.patch(`/interventions/${id}`, data); }
  deleteIntervention(id) { return this.delete(`/interventions/${id}`); }
  getInterventionsDashboard(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/interventions/dashboard${qs ? "?" + qs : ""}`);
  }

  // ── Analytics ──
  getPeriodosDisponibles() { return this.get("/analytics/periodos"); }
  getAsignaturasAnalytics(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/asignaturas${qs ? "?" + qs : ""}`);
  }
  getAsignaturaDetalle(asignatura, docente, periodo) {
    const params = new URLSearchParams();
    if (docente) params.set("docente", docente);
    if (periodo) params.set("periodo", periodo);
    const qs = params.toString();
    return this.get(`/analytics/asignaturas/${encodeURIComponent(asignatura)}/detalle${qs ? "?" + qs : ""}`);
  }
  getDocentesAnalytics(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/docentes${qs ? "?" + qs : ""}`);
  }
  getDocenteDetalle(docenteNombre, periodo) {
    const params = new URLSearchParams();
    if (periodo) params.set("periodo", periodo);
    const qs = params.toString();
    return this.get(`/analytics/docentes/${encodeURIComponent(docenteNombre)}/detalle${qs ? "?" + qs : ""}`);
  }
  getTutoriasPorAsignatura(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/tutorias/por-asignatura${qs ? "?" + qs : ""}`);
  }
  getResumenDatos(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/resumen${qs ? "?" + qs : ""}`);
  }
  getComparativa(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/comparativa${qs ? "?" + qs : ""}`);
  }

  // ── Dashboard ──
  getRiskDashboard(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/dashboard/risk${qs ? "?" + qs : ""}`);
  }
  getStats(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/dashboard/stats${qs ? "?" + qs : ""}`);
  }
  getCarreras() { return this.get("/dashboard/carreras"); }

  // ── Admin ──
  triggerETL() { return this.post("/admin/etl/run", {}); }
    triggerScraping(mode = "full") { return this.post(`/admin/etl/trigger-scraping?mode=${encodeURIComponent(mode)}`, {}); }
  getETLRuns(page = 1, pageSize = 10) { return this.get(`/admin/etl/runs?page=${page}&page_size=${pageSize}`); }
  getSystemStatus() { return this.get("/admin/system/status"); }
  uploadAndRunETL(file) {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${this.baseUrl}/admin/etl/upload-and-run`, {
      method: "POST",
      credentials: "include",
      body: form,
    }).then(async (r) => {
      if (!r.ok) throw new Error(sanitizeErrorMessage((await r.json().catch(() => ({}))).detail || r.statusText));
      return r.json();
    });
  }

  uploadHistorico(file, periodo = "P67") {
    const form = new FormData();
    form.append("file", file);
    return fetch(`${this.baseUrl}/admin/etl/upload-historico?periodo=${encodeURIComponent(periodo)}`, {
      method: "POST",
      credentials: "include",
      body: form,
    }).then(async (r) => {
      if (!r.ok) throw new Error(sanitizeErrorMessage((await r.json().catch(() => ({}))).detail || r.statusText));
      return r.json();
    });
  }

  uploadPracticasFiles(files) {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return fetch(`${this.baseUrl}/admin/etl/upload-practicas`, {
      method: "POST",
      credentials: "include",
      body: form,
    }).then(async (r) => {
      if (!r.ok) throw new Error(sanitizeErrorMessage((await r.json().catch(() => ({}))).detail || r.statusText));
      return r.json();
    });
  }

  // ── Export ──
  exportFichaPDF(studentId) { return this.getBlob(`/export/ficha/${studentId}/pdf`); }
  getExportColumnas() { return this.get("/export/columnas-disponibles"); }
  exportEstudiantesExcel(params) {
    const qs = new URLSearchParams(params).toString();
    return this.getBlob(`/export/estudiantes/excel${qs ? "?" + qs : ""}`);
  }
  getIntervencionesColumnas() { return this.get("/export/intervenciones/columnas-disponibles"); }
  exportIntervencionesExcel(params) {
    const qs = new URLSearchParams(params).toString();
    return this.getBlob(`/export/intervenciones/excel${qs ? "?" + qs : ""}`);
  }

  // ── Docente Tracking ──
  getDocenteTracking() { return this.get("/analytics/docente-tracking"); }
  getDocenteTrackingDetalle(docente) { return this.get(`/analytics/docente-tracking/${encodeURIComponent(docente)}`); }
  getDocenteTrackingResumen() { return this.get("/analytics/docente-tracking/resumen"); }

  // ── Alerts ──
  getAlertCount() { return this.get("/alerts/count"); }
  getAlertsPending() { return this.get("/alerts/pending"); }
  markAlertRead(id) { return this.patch(`/alerts/${id}/read`, {}); }
  generateAlerts() { return this.post("/alerts/generate", {}); }

  // ── Predictions / ML ──
  trainModel() { return this.post("/predictions/train", {}); }
  runPredictions() { return this.post("/predictions/run", {}); }
  getTaskStatus() { return this.get("/predictions/task-status"); }
  getPredictionStatus() { return this.get("/predictions/status"); }
  getPredictionStudent(studentId) { return this.get(`/predictions/student/${studentId}`); }
  getPrediction(studentId) { return this.getPredictionStudent(studentId); } // alias
  getRecommendations(studentId) { return this.get(`/predictions/student/${studentId}/recommendations`); }
  getCounterfactual(studentId, target = "ambos") {
    return this.get(`/predictions/student/${studentId}/counterfactual?target=${target}`);
  }
  whatIf(studentId, changes) {
    return this.request(`/predictions/student/${studentId}/what-if`, {
      method: "POST", body: JSON.stringify(changes)
    });
  }

  // ── Intervention Impact ──
  getInterventionImpact(interventionId) {
    return this.get(`/interventions/${interventionId}/impact`);
  }

  // ── Notify Tutoria ──
  notifyTutoria(data) {
    return this.post("/predictions/notify-tutoria", data);
  }
}

export const api = new ApiClient();
