const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

class ApiClient {
  constructor() {
    this.baseUrl = BASE_URL;
  }

  getToken() {
    return localStorage.getItem("yd_token");
  }

  async request(path, options = {}) {
    const token = this.getToken();
    const isFormData = options.body instanceof FormData;
    const headers = {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    };

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      const currentToken = this.getToken();
      if (currentToken && currentToken === token) {
        localStorage.removeItem("yd_token");
      }
      window.dispatchEvent(new CustomEvent("yd:unauthorized"));
      throw new Error("No autenticado");
    }

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: "Error desconocido" }));
      const detail = error.detail;
      const message = Array.isArray(detail)
        ? detail.map(e => e.msg || e.message || JSON.stringify(e)).join("; ")
        : (typeof detail === "string" ? detail : `HTTP ${response.status}`);
      throw new Error(message);
    }

    if (response.headers.get("content-type")?.includes("application/pdf")) {
      return response.blob();
    }

    return response.json();
  }

  get(path) { return this.request(path); }
  post(path, body) { return this.request(path, { method: "POST", body: JSON.stringify(body) }); }
  put(path, body) { return this.request(path, { method: "PUT", body: JSON.stringify(body) }); }
  patch(path, body) { return this.request(path, { method: "PATCH", body: JSON.stringify(body) }); }
  delete(path) { return this.request(path, { method: "DELETE" }); }

  // Auth
  login(email, password) {
    const form = new FormData();
    form.append("username", email);
    form.append("password", password);
    return this.request("/auth/login", { method: "POST", body: form, headers: {} });
  }
  me() { return this.get("/auth/me"); }
  createUser(data) { return this.post("/auth/users", data); }
  listUsers() { return this.get("/auth/users"); }

  // Students
  searchStudents(q, carrera = "") {
    const params = new URLSearchParams();
    if (q) params.set("q", q);
    if (carrera) params.set("carrera", carrera);
    return this.get(`/students/search?${params.toString()}`);
  }
  getFicha(studentId) { return this.get(`/students/${studentId}/ficha`); }

  // Interventions
  createIntervention(data) { return this.post("/interventions/", data); }
  listInterventions(studentId) { return this.get(`/interventions/?student_id=${studentId}`); }
  interventionStats() { return this.get("/interventions/stats"); }
  updateIntervention(id, data) { return this.patch(`/interventions/${id}`, data); }

  // Dashboard
  getRiskDashboard(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/dashboard/risk${qs ? "?" + qs : ""}`);
  }
  getStats() { return this.get("/dashboard/stats"); }
  getCarreras() { return this.get("/dashboard/carreras"); }

  // Admin
  triggerETL() { return this.post("/admin/etl/run", {}); }
  getETLRuns() { return this.get("/admin/etl/runs"); }
  getSystemStatus() { return this.get("/admin/system/status"); }

  // Export
  exportFichaPDF(studentId) { return this.get(`/export/ficha/${studentId}/pdf`); }

  // Analytics — Asignaturas (Módulo 8.2)
  getAsignaturasAnalytics(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/asignaturas${qs ? "?" + qs : ""}`);
  }
  getAsignaturaDetalle(asignatura, docente) {
    const params = new URLSearchParams({ asignatura });
    if (docente) params.set("docente", docente);
    return this.get(`/analytics/asignaturas/${encodeURIComponent(asignatura)}/detalle${docente ? "?docente=" + encodeURIComponent(docente) : ""}`);
  }

  // Analytics — Docentes (Módulo 8.3)
  getDocentesAnalytics(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/docentes${qs ? "?" + qs : ""}`);
  }
  getDocenteDetalle(docenteNombre) {
    return this.get(`/analytics/docentes/${encodeURIComponent(docenteNombre)}/detalle`);
  }

  // Analytics — Tutorías por asignatura (Módulo 8.4)
  getTutoriasPorAsignatura(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/tutorias/por-asignatura${qs ? "?" + qs : ""}`);
  }

  // Interventions — Dashboard
  getInterventionsDashboard(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/interventions/dashboard${qs ? "?" + qs : ""}`);
  }

  // Analytics — Resumen de Datos (Módulo 8.5)
  getResumenDatos(params = {}) {
    const qs = new URLSearchParams(params).toString();
    return this.get(`/analytics/resumen${qs ? "?" + qs : ""}`);
  }
  getPeriodosDisponibles() { return this.get("/analytics/periodos"); }

  // Predictions — ML (Fase 2)
  trainModel() { return this.post("/predictions/train", {}); }
  runPredictions() { return this.post("/predictions/run", {}); }
  getPredictionStatus() { return this.get("/predictions/status"); }
  getPredictionStudent(studentId) { return this.get(`/predictions/student/${studentId}`); }
}

export const api = new ApiClient();
