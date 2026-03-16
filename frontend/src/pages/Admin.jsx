import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";

const TABS = ["Sistema", "Cursos", "Semestre", "Usuarios"];

// ─────────────────────────────────────────────────────────────────────────────
// TAB: SISTEMA (ETL)
// ─────────────────────────────────────────────────────────────────────────────
function TabSistema() {
  const [status, setStatus] = useState(null);
  const [runs, setRuns] = useState([]);
  const [etlLoading, setEtlLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [etlMsg, setEtlMsg] = useState("");
  const [mlStatus, setMlStatus] = useState(null);
  const [mlLoading, setMlLoading] = useState(false);
  const [mlMsg, setMlMsg] = useState("");

  const loadMlStatus = () => api.getPredictionStatus().then(setMlStatus).catch(() => {});

  useEffect(() => {
    api.getSystemStatus().then(setStatus).catch(() => setMsg("Error: No se pudo cargar el estado del sistema"));
    api.getETLRuns().then(setRuns).catch(() => setMsg("Error: No se pudo cargar el historial ETL"));
    loadMlStatus();
  }, []);

  const handleRunETL = async () => {
    setEtlLoading(true);
    setEtlMsg("");
    try {
      const result = await api.triggerETL();
      setEtlMsg(result.message || "ETL ejecutado correctamente");
      setTimeout(() => api.getETLRuns().then(setRuns), 2000);
    } catch (e) {
      setEtlMsg("Error: " + e.message);
    } finally {
      setEtlLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {msg && (
        <div className={`text-sm px-4 py-2 rounded-lg ${msg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {msg}
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-800 mb-4">Estado del Sistema</h2>
        {status ? (
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-gray-500 text-xs">Total estudiantes</div>
              <div className="text-2xl font-bold text-gray-900">{status.total_estudiantes}</div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-gray-500 text-xs">Última actualización</div>
              <div className="font-semibold text-gray-900">
                {status.ultima_actualizacion
                  ? new Date(status.ultima_actualizacion).toLocaleString("es-EC")
                  : "Nunca"}
              </div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-gray-500 text-xs">Estado pipeline</div>
              <div className={`font-semibold capitalize ${status.estado_pipeline === "success" ? "text-green-600" : "text-yellow-600"}`}>
                {status.estado_pipeline}
              </div>
            </div>
          </div>
        ) : <p className="text-gray-400 text-sm">Cargando...</p>}

        <div className="mt-4 pt-4 border-t border-gray-100">
          <button
            onClick={handleRunETL}
            disabled={etlLoading}
            className="bg-brand text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-brand-light transition-colors disabled:opacity-60"
          >
            {etlLoading ? "Ejecutando ETL..." : "Ejecutar ETL Manual"}
          </button>
          <p className="text-xs text-gray-400 mt-2">
            Procesa todos los CSVs de IngresosAVAC y Tareas y actualiza la base de datos.
          </p>
          {etlMsg && (
            <div className={`text-sm mt-3 px-4 py-2 rounded-lg ${etlMsg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
              {etlMsg}
            </div>
          )}
        </div>
      </div>

      {/* Historial ETL */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <h2 className="px-5 py-4 font-semibold text-gray-800 border-b border-gray-100">
          Historial de Ejecuciones ETL
        </h2>
        {runs.length === 0 ? (
          <p className="text-center py-8 text-gray-400 text-sm">Sin ejecuciones registradas</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Inicio</th>
                <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Tipo</th>
                <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Estado</th>
                <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Registros</th>
                <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Disparado por</th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr key={run.id} className="border-t border-gray-100">
                  <td className="px-5 py-3 text-gray-600">
                    {run.started_at ? new Date(run.started_at).toLocaleString("es-EC") : "—"}
                  </td>
                  <td className="px-5 py-3 capitalize text-gray-700">{run.tipo}</td>
                  <td className="px-5 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                      ${run.status === "success" ? "bg-green-100 text-green-700"
                        : run.status === "error" ? "bg-red-100 text-red-700"
                        : "bg-yellow-100 text-yellow-700"}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-center font-mono">{run.registros_insertados ?? "—"}</td>
                  <td className="px-5 py-3 text-gray-500 text-xs">{run.triggered_by}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modelo Predictivo ML */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h2 className="font-semibold text-gray-800 mb-4">Modelo Predictivo (Fase 2)</h2>

        {mlStatus && (
          <div className="grid grid-cols-3 gap-4 text-sm mb-4">
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-gray-500 text-xs">Estado del modelo</div>
              <div className={`font-semibold ${mlStatus.loaded ? "text-green-600" : "text-yellow-600"}`}>
                {mlStatus.loaded ? "Cargado" : "Sin entrenar"}
              </div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-gray-500 text-xs">Modelo desercion</div>
              <div className="font-semibold text-gray-900">
                {mlStatus.has_desercion ? "Disponible" : "—"}
                {mlStatus.metadata?.results?.desercion?.best_auc && (
                  <span className="text-xs text-gray-500 ml-1">
                    (AUC: {mlStatus.metadata.results.desercion.best_auc})
                  </span>
                )}
              </div>
            </div>
            <div className="bg-gray-50 rounded-lg p-3">
              <div className="text-gray-500 text-xs">Entrenado</div>
              <div className="font-semibold text-gray-900">
                {mlStatus.metadata?.trained_at
                  ? new Date(mlStatus.metadata.trained_at).toLocaleString("es-EC")
                  : "Nunca"}
              </div>
            </div>
          </div>
        )}

        <div className="flex gap-3">
          <button
            onClick={async () => {
              setMlLoading(true);
              setMlMsg("");
              try {
                const r = await api.trainModel();
                setMlMsg(r.status === "ok"
                  ? `Modelo entrenado (${r.estudiantes} estudiantes, ${r.periodos?.length} periodos)`
                  : `Aviso: ${r.message || "sin resultado"}`);
                loadMlStatus();
              } catch (e) { setMlMsg("Error: " + e.message); }
              finally { setMlLoading(false); }
            }}
            disabled={mlLoading}
            className="bg-brand text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-brand-light transition-colors disabled:opacity-60"
          >
            {mlLoading ? "Entrenando..." : "Reentrenar Modelo"}
          </button>
          <button
            onClick={async () => {
              setMlLoading(true);
              setMlMsg("");
              try {
                const r = await api.runPredictions();
                setMlMsg(r.status === "ok"
                  ? `Predicciones actualizadas para ${r.updated} estudiantes`
                  : `Aviso: ${r.message || "sin resultado"}`);
              } catch (e) { setMlMsg("Error: " + e.message); }
              finally { setMlLoading(false); }
            }}
            disabled={mlLoading || !mlStatus?.loaded}
            className="bg-brand-gold text-brand-dark px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-brand-gold-light transition-colors disabled:opacity-60"
          >
            {mlLoading ? "Ejecutando..." : "Ejecutar Predicciones"}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Entrena modelos de desercion y reprobacion con datos historicos (P60-P67). Las predicciones se ejecutan automaticamente al final del ETL si hay un modelo entrenado.
        </p>
        {mlMsg && (
          <div className={`text-sm mt-3 px-4 py-2 rounded-lg ${mlMsg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
            {mlMsg}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: CURSOS
// ─────────────────────────────────────────────────────────────────────────────
function TabCursos() {
  const [courses, setCourses] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editCourse, setEditCourse] = useState(null);
  const [form, setForm] = useState({
    codigo_avac: "", nombre: "", asignatura: "", carrera: "",
    docente: "", semestre: "", bloque: "1", grupo: "", activo: true, notas: "",
  });
  const [msg, setMsg] = useState("");

  const loadCourses = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.get("/courses/");
      setCourses(data);
    } catch { setCourses([]); }
    setLoading(false);
  }, []);

  useEffect(() => { loadCourses(); }, [loadCourses]);

  const resetForm = () => {
    setForm({ codigo_avac: "", nombre: "", asignatura: "", carrera: "", docente: "",
      semestre: "", bloque: "1", grupo: "", activo: true, notas: "" });
    setEditCourse(null);
    setShowForm(false);
    setMsg("");
  };

  const handleEdit = (c) => {
    setForm({ codigo_avac: c.codigo_avac, nombre: c.nombre || "", asignatura: c.asignatura || "",
      carrera: c.carrera || "", docente: c.docente || "", semestre: c.semestre || "",
      bloque: c.bloque || "1", grupo: c.grupo || "", activo: c.activo, notas: c.notas || "" });
    setEditCourse(c);
    setShowForm(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      if (editCourse) {
        await api.patch(`/courses/${editCourse.id}`, form);
        setMsg("Curso actualizado correctamente");
      } else {
        await api.post("/courses/", form);
        setMsg("Curso creado correctamente");
      }
      loadCourses();
      resetForm();
    } catch (err) {
      setMsg("Error: " + err.message);
    }
  };

  const handleToggle = async (c) => {
    try {
      await api.patch(`/courses/${c.id}`, { activo: !c.activo });
      loadCourses();
    } catch (err) {
      setMsg("Error: " + err.message);
    }
  };

  const handleDelete = async (id) => {
    if (!confirm("¿Eliminar este curso?")) return;
    try {
      await api.delete(`/courses/${id}`);
      loadCourses();
    } catch (err) {
      setMsg("Error: " + err.message);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="font-semibold text-gray-800">Gestión de Cursos AVAC</h2>
        <button
          onClick={() => { resetForm(); setShowForm(true); }}
          className="bg-brand text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-brand-light"
        >
          + Agregar Curso
        </button>
      </div>

      {msg && (
        <div className={`text-sm px-4 py-2 rounded-lg ${msg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {msg}
        </div>
      )}

      {/* Formulario */}
      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-medium text-gray-800 mb-4">{editCourse ? "Editar Curso" : "Nuevo Curso"}</h3>
          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Código AVAC *</label>
                <input value={form.codigo_avac} onChange={e => setForm(f => ({ ...f, codigo_avac: e.target.value }))}
                  required placeholder="ej: 395484"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Nombre del curso</label>
                <input value={form.nombre} onChange={e => setForm(f => ({ ...f, nombre: e.target.value }))}
                  placeholder="Nombre en AVAC"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Asignatura</label>
                <input value={form.asignatura} onChange={e => setForm(f => ({ ...f, asignatura: e.target.value }))}
                  placeholder="Nombre normalizado"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Carrera</label>
                <input value={form.carrera} onChange={e => setForm(f => ({ ...f, carrera: e.target.value }))}
                  placeholder="Carrera"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Docente</label>
                <input value={form.docente} onChange={e => setForm(f => ({ ...f, docente: e.target.value }))}
                  placeholder="Nombre del docente"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Semestre</label>
                <input value={form.semestre} onChange={e => setForm(f => ({ ...f, semestre: e.target.value }))}
                  placeholder="ej: 2026-1"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Bloque</label>
                <select value={form.bloque} onChange={e => setForm(f => ({ ...f, bloque: e.target.value }))}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
                  <option value="1">Bloque 1</option>
                  <option value="2">Bloque 2</option>
                  <option value="ambos">Ambos bloques</option>
                </select>
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Grupo</label>
                <input value={form.grupo} onChange={e => setForm(f => ({ ...f, grupo: e.target.value }))}
                  placeholder="ej: G1"
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div className="flex items-end">
                <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
                  <input type="checkbox" checked={form.activo} onChange={e => setForm(f => ({ ...f, activo: e.target.checked }))}
                    className="w-4 h-4 rounded border-gray-300 text-blue-600" />
                  Curso activo
                </label>
              </div>
            </div>
            <div className="mb-4">
              <label className="block text-xs text-gray-500 mb-1">Notas</label>
              <input value={form.notas} onChange={e => setForm(f => ({ ...f, notas: e.target.value }))}
                placeholder="Observaciones opcionales"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div className="flex gap-3">
              <button type="submit"
                className="bg-brand text-white px-5 py-2 rounded-lg text-sm font-semibold hover:bg-brand-light">
                {editCourse ? "Guardar cambios" : "Crear curso"}
              </button>
              <button type="button" onClick={resetForm}
                className="px-5 py-2 rounded-lg text-sm font-semibold text-gray-600 border border-gray-300 hover:bg-gray-50">
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Tabla de cursos */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {loading ? (
          <p className="text-center py-8 text-gray-400 text-sm">Cargando cursos...</p>
        ) : courses.length === 0 ? (
          <p className="text-center py-8 text-gray-400 text-sm">No hay cursos configurados</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-4 py-2.5 text-gray-600 font-medium">Código</th>
                <th className="text-left px-4 py-2.5 text-gray-600 font-medium">Asignatura</th>
                <th className="text-left px-4 py-2.5 text-gray-600 font-medium">Carrera</th>
                <th className="text-center px-4 py-2.5 text-gray-600 font-medium">Semestre</th>
                <th className="text-center px-4 py-2.5 text-gray-600 font-medium">Bloque</th>
                <th className="text-center px-4 py-2.5 text-gray-600 font-medium">Estado</th>
                <th className="text-center px-4 py-2.5 text-gray-600 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {courses.map(c => (
                <tr key={c.id} className="border-t border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-2.5 font-mono text-gray-800">{c.codigo_avac}</td>
                  <td className="px-4 py-2.5 text-gray-700">{c.asignatura || c.nombre || "—"}</td>
                  <td className="px-4 py-2.5 text-gray-500 text-xs">{c.carrera || "—"}</td>
                  <td className="px-4 py-2.5 text-center text-gray-600">{c.semestre || "—"}</td>
                  <td className="px-4 py-2.5 text-center">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                      {c.bloque === "ambos" ? "1+2" : `B${c.bloque}`}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <button onClick={() => handleToggle(c)}
                      className={`px-2 py-0.5 rounded-full text-xs font-medium ${c.activo ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {c.activo ? "Activo" : "Inactivo"}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <button onClick={() => handleEdit(c)}
                        className="text-blue-600 hover:text-blue-800 text-xs font-medium">
                        Editar
                      </button>
                      <button onClick={() => handleDelete(c.id)}
                        className="text-red-500 hover:text-red-700 text-xs font-medium">
                        Eliminar
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: SEMESTRE
// ─────────────────────────────────────────────────────────────────────────────
function TabSemestre() {
  const [semesters, setSemesters] = useState([]);
  const [newSem, setNewSem] = useState({ semestre: "", bloque_actual: "1" });
  const [msg, setMsg] = useState("");

  const loadSemesters = async () => {
    try {
      const data = await api.get("/courses/semester/all");
      setSemesters(data);
    } catch { setSemesters([]); }
  };

  useEffect(() => { loadSemesters(); }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    try {
      await api.post("/courses/semester/", newSem);
      setMsg("Semestre creado");
      setNewSem({ semestre: "", bloque_actual: "1" });
      loadSemesters();
    } catch (err) {
      setMsg("Error: " + err.message);
    }
  };

  const handleActivate = async (semestre) => {
    try {
      await api.post(`/courses/semester/${semestre}/activate`);
      setMsg(`Semestre ${semestre} activado`);
      loadSemesters();
    } catch (err) {
      setMsg("Error: " + err.message);
    }
  };

  const handleSetBloque = async (semestre, bloque) => {
    try {
      await api.post(`/courses/semester/${semestre}/bloque`, { bloque });
      setMsg(`Bloque ${bloque} activado para ${semestre}`);
      loadSemesters();
    } catch (err) {
      setMsg("Error: " + err.message);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-gray-800">Gestión de Semestres</h2>

      {msg && (
        <div className={`text-sm px-4 py-2 rounded-lg ${msg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {msg}
        </div>
      )}

      {/* Crear semestre */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-medium text-gray-700 mb-3 text-sm">Nuevo Semestre</h3>
        <form onSubmit={handleCreate} className="flex gap-3 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Semestre (ej: 2026-1)</label>
            <input value={newSem.semestre} onChange={e => setNewSem(s => ({ ...s, semestre: e.target.value }))}
              required placeholder="2026-1"
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Bloque inicial</label>
            <select value={newSem.bloque_actual} onChange={e => setNewSem(s => ({ ...s, bloque_actual: e.target.value }))}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="1">Bloque 1</option>
              <option value="2">Bloque 2</option>
            </select>
          </div>
          <button type="submit"
            className="bg-brand text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-brand-light">
            Crear
          </button>
        </form>
      </div>

      {/* Lista de semestres */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {semesters.length === 0 ? (
          <p className="text-center py-8 text-gray-400 text-sm">No hay semestres configurados</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Semestre</th>
                <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Estado</th>
                <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Bloque actual</th>
                <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {semesters.map(s => (
                <tr key={s.id} className="border-t border-gray-100">
                  <td className="px-5 py-3 font-semibold text-gray-800">{s.semestre}</td>
                  <td className="px-5 py-3 text-center">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${s.activo ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {s.activo ? "Activo" : "Inactivo"}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-center text-gray-700">
                    Bloque {s.bloque_actual}
                  </td>
                  <td className="px-5 py-3 text-center">
                    <div className="flex items-center justify-center gap-2 flex-wrap">
                      {!s.activo && (
                        <button onClick={() => handleActivate(s.semestre)}
                          className="text-xs px-2 py-1 rounded bg-brand text-white hover:bg-brand-light">
                          Activar
                        </button>
                      )}
                      <button onClick={() => handleSetBloque(s.semestre, "1")}
                        className={`text-xs px-2 py-1 rounded border ${s.bloque_actual === "1" ? "border-blue-500 text-blue-700 bg-blue-50" : "border-gray-300 text-gray-600 hover:bg-gray-50"}`}>
                        Bloque 1
                      </button>
                      <button onClick={() => handleSetBloque(s.semestre, "2")}
                        className={`text-xs px-2 py-1 rounded border ${s.bloque_actual === "2" ? "border-blue-500 text-blue-700 bg-blue-50" : "border-gray-300 text-gray-600 hover:bg-gray-50"}`}>
                        Bloque 2
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
        <strong>Al inicio de cada semestre:</strong> Crea el nuevo semestre, actívalo y agrega los cursos
        en la pestaña "Cursos" usando el botón "Agregar Curso" o importación masiva.
        Cambia el bloque activo a mitad del semestre para filtrar automáticamente las asignaturas del bloque 1 al 2.
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: USUARIOS
// ─────────────────────────────────────────────────────────────────────────────
function TabUsuarios() {
  const [users, setUsers] = useState([]);
  const [newUser, setNewUser] = useState({ email: "", nombre: "", password: "", role: "monitor" });
  const [userMsg, setUserMsg] = useState("");

  useEffect(() => {
    api.listUsers().then(setUsers).catch(() => setUserMsg("Error: No se pudieron cargar los usuarios"));
  }, []);

  const handleCreateUser = async (e) => {
    e.preventDefault();
    try {
      await api.createUser(newUser);
      setUserMsg("Usuario creado correctamente");
      setNewUser({ email: "", nombre: "", password: "", role: "monitor" });
      api.listUsers().then(setUsers);
    } catch (err) {
      setUserMsg("Error: " + err.message);
    }
  };

  const toggleUser = async (user) => {
    try {
      await api.patch(`/auth/users/${user.id}`, { is_active: !user.is_active });
      api.listUsers().then(setUsers);
    } catch (err) {
      setUserMsg("Error: " + err.message);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-gray-800">Gestión de Usuarios</h2>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-medium text-gray-700 mb-3 text-sm">Crear nuevo usuario</h3>
        <form onSubmit={handleCreateUser} className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <input value={newUser.email} onChange={e => setNewUser(u => ({ ...u, email: e.target.value }))}
            type="email" placeholder="Email" required
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <input value={newUser.nombre} onChange={e => setNewUser(u => ({ ...u, nombre: e.target.value }))}
            placeholder="Nombre completo" required
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <input value={newUser.password} onChange={e => setNewUser(u => ({ ...u, password: e.target.value }))}
            type="password" placeholder="Contraseña" required
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <select value={newUser.role} onChange={e => setNewUser(u => ({ ...u, role: e.target.value }))}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
            <option value="monitor">Monitor</option>
            <option value="admin">Admin</option>
          </select>
          <button type="submit"
            className="bg-brand text-white rounded-lg py-2 text-sm font-semibold hover:bg-brand-light">
            Crear usuario
          </button>
        </form>
        {userMsg && <p className="text-sm mt-3">{userMsg}</p>}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Nombre</th>
              <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Email</th>
              <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Rol</th>
              <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Estado</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t border-gray-100">
                <td className="px-5 py-2.5 font-medium text-gray-800">{u.nombre}</td>
                <td className="px-5 py-2.5 text-gray-500">{u.email}</td>
                <td className="px-5 py-2.5 text-center capitalize text-xs font-medium text-blue-600">{u.role}</td>
                <td className="px-5 py-2.5 text-center">
                  <button onClick={() => toggleUser(u)}
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${u.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                    {u.is_active ? "Activo" : "Inactivo"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PÁGINA PRINCIPAL ADMIN
// ─────────────────────────────────────────────────────────────────────────────
export default function Admin() {
  const [activeTab, setActiveTab] = useState("Sistema");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Administración</h1>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-200">
        {TABS.map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-5 py-2.5 text-sm font-medium transition-colors -mb-px
              ${activeTab === tab
                ? "border-b-2 border-brand text-brand"
                : "text-gray-500 hover:text-gray-700"}`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === "Sistema" && <TabSistema />}
      {activeTab === "Cursos" && <TabCursos />}
      {activeTab === "Semestre" && <TabSemestre />}
      {activeTab === "Usuarios" && <TabUsuarios />}
    </div>
  );
}
