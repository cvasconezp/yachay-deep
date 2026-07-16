/**
 * Cliente API — Yachay Deep
 *
 * [SEC-02] Fase 2: HttpOnly cookies. Usa credentials:"include" en vez de
 *          localStorage token. El backend setea/borra la cookie.
 * [SEC-07/BUG-03] Sanitización de mensajes de error.
 */

import { getTenant } from "../hooks/useTenant";

const BASE_URL = import.meta.env.VITE_API_URL || "/api";

function sanitizeErrorMessage(raw) {
  if (typeof raw !== "string") return "Error desconocido";
  return raw.replace(/<[^>]*>/g, "").replace(/[<>'"]/g, "").slice(0, 500);
}

class ApiClient {
  constructor() {
    this.baseUrl = BASE_URL;
    this._previewReadOnly = false;
  }

  setPreviewReadOnly(v) { this._previewReadOnly = !!v; }

  async _tryRefresh() {
    // [WF4] Renueva el access token usando el refresh cookie. Deduplica llamadas concurrentes.
    if (this._refreshing) return this._refreshing;
    this._refreshing = (async () => {
      try {
        const r = await fetch(`${this.baseUrl}/auth/refresh`, { method: "POST", credentials: "include", cache: "no-store" });
        return r.ok;
      } catch {
        return false;
      }
    })();
    const ok = await this._refreshing;
    this._refreshing = null;
    return ok;
  }

  async request(path, options = {}) {
    // [AUDIT] En vista previa de rol de solo lectura (Docente), bloquear escrituras (excepto /auth/).
    if (this._previewReadOnly && !path.startsWith("/auth/")) {
      const m = (options.method || "GET").toUpperCase();
      if (["POST", "PUT", "PATCH", "DELETE"].includes(m)) {
        throw new Error("Modo vista previa (Docente): solo lectura. Acción de escritura bloqueada.");
      }
    }
    const isFormData = options.body instanceof FormData;
    const tenant = getTenant();
    const headers = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(tenant ? { "X-Tenant": tenant } : {}),
      ...options.headers,
    };

    // [SEC-02] credentials: "include" envía la HttpOnly cookie automáticamente
    // [PERF-03] Timeout de 30s para evitar requests colgados
    const controller = options.signal ? null : new AbortController();
    const timeoutId = controller ? setTimeout(() => controller.abort(), 30000) : null;

    let response;
    try {
      // [CACHE] Cache-busting en GET: garantiza MISS en el CDN (datos por-tenant nunca deben cachearse)
      const _method = (options.method || "GET").toUpperCase();
      let _url = `${this.baseUrl}${path}`;
      if (_method === "GET") {
        _url += (path.includes("?") ? "&" : "?") + "_=" + Date.now();
      }
      response = await fetch(_url, {
        ...options,
        headers,
        credentials: "include",
        cache: "no-store",
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
      // [WF4] Auto-refresh: renueva el access token una sola vez y reintenta.
      const noRetry = path.includes("/auth/refresh") || path.includes("/auth/login");
      if (!options._retried && !noRetry) {
        const ok = await this._tryRefresh();
        if (ok) return this.request(path, { ...options, _retried: true });
      }
      // Leer el detalle para no perder señales como "2FA_REQUIRED" o el motivo
      // específico (código 2FA inválido, credenciales incorrectas).
      const err401 = await response.json().catch(() => ({}));
      const detail401 = typeof err401.detail === "string" ? err401.detail : null;
      if (detail401 && detail401 !== "No autenticado") {
        throw new Error(sanitizeErrorMessage(detail401));
      }
      window.dispatchEvent(new CustomEvent("yd:unauthorized"));
      throw new Error("No autenticado");
    }

    if (response.status === 423) {
      // [SEC-03] Sesión bloqueada por PIN: avisar a la UI para mostrar la pantalla de bloqueo.
      window.dispatchEvent(new CustomEvent("yd:locked"));
      throw new Error("PIN_LOCKED");
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

  async getBlob(path, _retried = false) {
    const _u = `${this.baseUrl}${path}` + (path.includes("?") ? "&" : "?") + "_=" + Date.now();
    const response = await fetch(_u, {
      credentials: "include",
      cache: "no-store",
    });
    if (response.status === 401) {
      if (!_retried) {
        const ok = await this._tryRefresh();
        if (ok) return this.getBlob(path, true);
      }
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
  login(email, password, code = null) {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    if (code) form.append("code", code);
    return this.request("/auth/login", { method: "POST", body: form, headers: {} });
  }
  logout() { return this.request("/auth/logout", { method: "POST" }); }
  me() { return this.get("/auth/me"); }

  // ── 2FA (TOTP) ──
  get2FAStatus() { return this.get("/auth/2fa/status"); }
  setup2FA() { return this.request("/auth/2fa/setup", { method: "POST" }); }
  verifySetup2FA(code) {
    const form = new FormData(); form.append("code", code);
    return this.request("/auth/2fa/verify-setup", { method: "POST", body: form, headers: {} });
  }
  changeEmail(new_email, password, code = null) {
    return this.request("/auth/change-email", { method: "POST", body: JSON.stringify({ new_email, password, code }) });
  }
  disable2FA(password) {
    const form = new FormData(); form.append("password", password);
    return this.request("/auth/2fa/disable", { method: "POST", body: form, headers: {} });
  }

  // PIN de desbloqueo
  setPin(pin, password) { return this.request("/auth/set-pin", { method: "POST", body: JSON.stringify({ pin, password }) }); }
  verifyPin(pin) { return this.request("/auth/verify-pin", { method: "POST", body: JSON.stringify({ pin }) }); }
  lock() { return this.request("/auth/lock", { method: "POST" }); }
  removePin() { return this.request("/auth/pin", { method: "DELETE" }); }
  createUser(data) { return this.post("/auth/users", data); }
  listUsers(scope = null) { return this.get(`/auth/users${scope ? "?scope=" + encodeURIComponent(scope) : ""}`); }
  deleteUser(id, password) { return this.request(`/auth/users/${id}/delete`, { method: "POST", body: JSON.stringify({ password }) }); }
  resetUser2FA(userId) { return this.request(`/auth/users/${userId}/reset-2fa`, { method: "POST" }); }
  resetUserPassword(userId, new_password) { return this.request(`/auth/users/${userId}/reset-password`, { method: "POST", body: JSON.stringify({ new_password }) }); }
  regenerateDemoSynthetic(n = 1000) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(), 180000); // hasta 3 min
    return this.request(`/admin/demo/regenerate-synthetic?n_estudiantes=${n}`, { method: "POST", signal: controller.signal })
      .finally(() => clearTimeout(t));
  }
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
  createIntervention(data) { return this.post("/interventions", data); }
  bulkCreateInterventions(data) { return this.post("/interventions/bulk", data); }
  listInterventions(studentId) { return this.get(`/interventions?student_id=${studentId}`); }
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
    cifradoBackfill(mode = "dry-run") { return this.post(`/admin/cifrado/backfill?mode=${encodeURIComponent(mode)}`, {}); }
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
  getAsignaturasDisponibles(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/export/asignaturas-disponibles${qs ? "?" + qs : ""}`);
  }
  getDocentesDisponibles(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/export/docentes-disponibles${qs ? "?" + qs : ""}`);
  }
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
  recalcularIndicadores() { return this.post("/admin/recalcular-indicadores", {}); }
  getDiagnosticoRiesgo() { return this.get("/admin/diagnostico-riesgo"); }
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
  getEffectivenessDesenlaces(periodo) { return this.get(`/analytics/effectiveness/desenlaces?periodo=${periodo}`); }
  getEffectivenessComparado(periodo, dias = 30) { const qs = periodo ? `?periodo=${periodo}&dias_seguimiento=${dias}` : `?dias_seguimiento=${dias}`; return this.get(`/analytics/effectiveness/comparado${qs}`); }
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
