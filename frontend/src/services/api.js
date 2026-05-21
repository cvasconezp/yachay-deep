/**
 * Cliente API — Yachay Deep
 *
 * [SEC-02] Fase 2: HttpOnly cookies. Usa credentials:"include" en vez de
 *          localStorage token. El backend setea/borra la cookie.
 * [SEC-07/BUG-03] Sanitización de mensajes de error.
 */

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

  // PIN de desbloqueo
  setPin(pin, password) { return this.request("/auth/set-pin", { method: "POST", body: JSON.stringify({ pin, password }) }); }
  verifyPin(pin) { return this.request("/auth/verify-pin", { method: "POST", body: JSON.stringify({ pin }) }); }
  removePin() { return this.request("/auth/pin", { method: "DELETE" }); }
  createUser(data) { return this.post("/auth/users", data); }
  listUsers() { return this.get("/auth/users"); }
  updateUser(id, data) { return this.patch(`/auth/users/${id}`, data); }

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
  bulkCreateInterventions(data) { return this.post("/interventions/bulk", data); }
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
  getEstudiantesListado(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/resumen/estudiantes-listado${qs ? "?" + qs : ""}`);
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
  getAsignaturas(carrera) {
    const params = carrera ? `?carrera=${encodeURIComponent(carrera)}` : "";
    return this.get(`/dashboard/asignaturas${params}`);
  }
  getStudentInactivity(studentId, periodo) {
    const params = periodo ? `?periodo=${encodeURIComponent(periodo)}` : "";
    return this.get(`/dashboard/risk/${studentId}/inactividad${params}`);
  }

  // ── Admin ──
  triggerETL() { return this.post("/admin/etl/run", {}); }
    triggerScraping(mode = "full") { return this.post(`/admin/etl/trigger-scraping?mode=${encodeURIComponent(mode)}`, {}); }
    getScrapingProgress() { return this.get("/admin/etl/scraping-progress"); }
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

  // ── AVAC Cookie ──
  getAvacCookie() { return this.get("/admin/system/avac-cookie"); }
  updateAvacCookie(cookie) { return this.put("/admin/system/avac-cookie", { cookie }); }

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
  getDocenteTracking(carrera) { const qs = carrera ? `?carrera=${encodeURIComponent(carrera)}` : ""; return this.get(`/analytics/docente-tracking${qs}`); }
  getDocenteTrackingDetalle(docente, carrera) { const qs = carrera ? `?carrera=${encodeURIComponent(carrera)}` : ""; return this.get(`/analytics/docente-tracking/${encodeURIComponent(docente)}${qs}`); }
  getDocenteTrackingResumen(carrera) { const qs = carrera ? `?carrera=${encodeURIComponent(carrera)}` : ""; return this.get(`/analytics/docente-tracking/resumen${qs}`); }

  // ── Entregas ──
  getEntregasPendientes(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/entregas-pendientes${qs ? "?" + qs : ""}`);
  }
  getEntregasResumen(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/entregas-resumen${qs ? "?" + qs : ""}`);
  }

  // ── Prácticas ──
  getPracticasResumen(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/practicas-resumen${qs ? "?" + qs : ""}`);
  }

  // ── Alerts ──
  getAlertCount(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/alerts/count${qs ? "?" + qs : ""}`);
  }
  getAlertsPending(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/alerts/pending${qs ? "?" + qs : ""}`);
  }
  markAlertRead(id) { return this.patch(`/alerts/${id}/read`, {}); }
  generateAlerts() { return this.post("/alerts/generate", {}); }
  debugAlertConditions() { return this.get("/alerts/debug/conditions"); }
  getStudentTasksDetail(studentId) { return this.get(`/alerts/student-tasks-detail/${studentId}`); }

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

  // ── Bandeja de Trabajo [Épica 2.3] ──
  getWorkqueue(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/workqueue${qs ? "?" + qs : ""}`);
  }

  // ── Daily Digest [Épica 2.1] ──
  sendDigest(email = null) {
    const qs = email ? `?email=${encodeURIComponent(email)}` : "";
    return this.post(`/alerts/digest/send${qs}`);
  }
  previewDigest() { return this.get("/alerts/digest/preview"); }

  // Score de Recuperabilidad (Épica 1.4)
  getRecoveryScore(studentId) { return this.get(`/students/${studentId}/recovery-score`); }
  batchRecoveryScores() { return this.post("/students/recovery-scores/batch"); }

  // Workflow de Intervenciones (Fase 3)
  getWorkflowStates() { return this.get("/workflow/states"); }
  transitionIntervention(id, body) { return this.patch(`/workflow/interventions/${id}/transition`, body); }
  assignIntervention(id, body) { return this.post(`/workflow/interventions/${id}/assign`, body); }
  autoAssign(intervention_ids) { return this.post("/workflow/auto-assign", { intervention_ids }); }
  getCargaMonitores() { return this.get("/workflow/carga"); }
  checkSLA() { return this.post("/workflow/check-sla"); }
  getInterventionLogs(id) { return this.get(`/workflow/interventions/${id}/logs`); }
  getOverdueInterventions() { return this.get("/workflow/overdue"); }
  // Analytics Ejecutivo (Fase 4)
  getExecutiveDashboard(periodo) { const qs = periodo ? `?periodo=${periodo}` : ""; return this.get(`/analytics/executive${qs}`); }
  getEffectiveness(periodo) { const qs = periodo ? `?periodo=${periodo}` : ""; return this.get(`/analytics/effectiveness${qs}`); }
  getHistoricalAsignaturas(carrera) { const qs = carrera ? `?carrera=${encodeURIComponent(carrera)}` : ""; return this.get(`/analytics/historical/asignaturas${qs}`); }
  getAbandonoAsignaturas(periodo) { const qs = periodo ? `?periodo=${periodo}` : ""; return this.get(`/analytics/historical/abandono-asignaturas${qs}`); }
  getDocenteEffectiveness(periodo, carrera) { const params = []; if(periodo) params.push(`periodo=${periodo}`); if(carrera) params.push(`carrera=${encodeURIComponent(carrera)}`); const qs = params.length ? `?${params.join("&")}` : ""; return this.get(`/analytics/docente-effectiveness${qs}`); }
  getMonthlyReport(periodo) { const qs = periodo ? `?periodo=${periodo}` : ""; return this.get(`/analytics/monthly-report${qs}`); }

  // ML Avanzado (Fase 5)
  trainAdaptiveModel() { return this.post("/ml/adaptive/train"); }
  getAdaptiveStatus() { return this.get("/ml/adaptive/status"); }
  getAdaptivePrediction(studentId) { return this.get(`/ml/adaptive/predict/${studentId}`); }
  getShapExplanation(studentId) { return this.get(`/ml/explain/${studentId}`); }
  runClustering(nClusters, periodo) { const params = []; if(nClusters) params.push(`n_clusters=${nClusters}`); if(periodo) params.push(`periodo=${periodo}`); const qs = params.length ? `?${params.join("&")}` : ""; return this.post(`/ml/clustering/run${qs}`); }
  getClusteringStatus() { return this.get("/ml/clustering/status"); }

  // Instituciones (Fase 5)
  getInstitutions() { return this.get("/institutions"); }
  createInstitution(body) { return this.post("/institutions", body); }
  updateInstitution(id, body) { return this.patch(`/institutions/${id}`, body); }
  getInstitution(id) { return this.get(`/institutions/${id}`); }
}

export const api = new ApiClient();
