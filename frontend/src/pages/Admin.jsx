import { useState, useEffect, useCallback } from "react";
import { api } from "../services/api";
import { useAuth } from "../hooks/useAuth";
import { useParams, useNavigate } from "react-router-dom";
import { getTenant, isAdminHost } from "../hooks/useTenant";
import Seguridad2FA from "./Seguridad2FA";

const TABS = ["Sistema", "Cursos", "Semestre", "Usuarios", "Seguridad"];
const TAB_SLUGS = { Sistema: "sistema", Cursos: "cursos", Semestre: "semestre", Usuarios: "usuarios", Seguridad: "seguridad" };
const SLUG_TO_TAB = Object.fromEntries(Object.entries(TAB_SLUGS).map(([k, v]) => [v, k]));

// ─────────────────────────────────────────────────────────────────────────────
// TAB: SISTEMA (ETL)
// ─────────────────────────────────────────────────────────────────────────────
function TabSistema() {
  const [status, setStatus] = useState(null);
  const [runsData, setRunsData] = useState({ items: [], total: 0, page: 1, pages: 1 });
  const [runsPage, setRunsPage] = useState(1);
  const [etlLoading, setEtlLoading] = useState(false);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [etlMsg, setEtlMsg] = useState("");
  const [uploadMsg, setUploadMsg] = useState("");
  const [mlStatus, setMlStatus] = useState(null);
  const [mlLoading, setMlLoading] = useState(false);
  const [mlMsg, setMlMsg] = useState("");
  const [scrapingLoading, setScrapingLoading] = useState(false);
  const [scrapingMsg, setScrapingMsg] = useState("");
  const [scrapingMode, setScrapingMode] = useState("full");
  const [scrapingProgress, setScrapingProgress] = useState(null);

  const loadMlStatus = () => api.getPredictionStatus().then(setMlStatus).catch(() => {});

  const loadRuns = (page = 1) => {
    api.getETLRuns(page).then(data => { setRunsData(data); setRunsPage(data.page); }).catch(() => setMsg("Error: No se pudo cargar el historial ETL"));
  };

  useEffect(() => {
    api.getSystemStatus().then(setStatus).catch(() => setMsg("Error: No se pudo cargar el estado del sistema"));
    loadRuns(1);
    loadMlStatus();
  }, []);

  const handleRunETL = async () => {
    setEtlLoading(true);
    setEtlMsg("");
    try {
      const result = await api.triggerETL();
      setEtlMsg(result.message || "ETL ejecutado correctamente");
      setTimeout(() => loadRuns(1), 2000);
    } catch (e) {
      setEtlMsg("Error: " + e.message);
    } finally {
      setEtlLoading(false);
    }
  };

  const handleTriggerScraping = async () => {
    if (!window.confirm(`¿Iniciar scraping en modo "${scrapingMode}"? Esto ejecutará el workflow de GitHub Actions y puede tardar varios minutos.`)) return;
    setScrapingLoading(true);
    setScrapingMsg("");
    try {
      const result = await api.triggerScraping(scrapingMode);
      setScrapingMsg(result.message || "Scraping disparado correctamente en GitHub Actions");
      setTimeout(() => loadRuns(1), 5000);
    } catch (e) {
      setScrapingMsg("Error: " + e.message);
    } finally {
      setScrapingLoading(false);
    }
  };

  // Polling de progreso del scraping cada 15s
  useEffect(() => {
    let interval;
    const checkProgress = async () => {
      try {
        const prog = await api.getScrapingProgress();
        setScrapingProgress(prog);
        if (!prog.running && interval) {
          clearInterval(interval);
          interval = null;
        }
      } catch { /* ignore */ }
    };
    checkProgress();
    interval = setInterval(checkProgress, 15000);
    return () => { if (interval) clearInterval(interval); };
  }, []);

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

        <div className="mt-4 pt-4 border-t border-gray-100">
          <div className="flex items-center gap-3">
            <button
              onClick={handleTriggerScraping}
              disabled={scrapingLoading}
              className="bg-indigo-600 text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-60"
            >
              {scrapingLoading ? "Disparando scraping..." : "Iniciar Scraping AVAC"}
            </button>
            <select
              value={scrapingMode}
              onChange={(e) => setScrapingMode(e.target.value)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white"
              disabled={scrapingLoading}
            >
              <option value="full">Completo (ingresos + tareas)</option>
              <option value="ingresos">Solo ingresos AVAC</option>
              <option value="tareas">Solo estado de tareas</option>
            </select>
          </div>
          <p className="text-xs text-gray-400 mt-2">
            Ejecuta el scraping de AVAC en GitHub Actions. Descarga datos de la plataforma y luego corre el ETL automáticamente.
            Puede tardar 30–60 minutos dependiendo de la cantidad de cursos.
          </p>
          {scrapingMsg && (
            <div className={`text-sm mt-3 px-4 py-2 rounded-lg ${scrapingMsg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
              {scrapingMsg}
            </div>
          )}

          {/* Barra de progreso del scraping */}
          {scrapingProgress?.running && (() => {
            const tp = scrapingProgress.time_progress;
            const elapsed = tp?.elapsed_min ?? (scrapingProgress.started_at
              ? Math.floor((Date.now() - new Date(scrapingProgress.started_at).getTime()) / 60000) : 0);
            const elapsedStr = elapsed < 1 ? "menos de 1 min" : `${elapsed} min`;
            // Use time-based progress, fall back to step-based, then 0
            const pct = tp?.percent ?? scrapingProgress.step_progress_pct ?? 0;
            const remaining = tp?.remaining_min;
            const stepName = scrapingProgress.current_step || "";
            const stepsInfo = scrapingProgress.steps_completed != null && scrapingProgress.steps_total
              ? `Paso ${scrapingProgress.steps_completed}/${scrapingProgress.steps_total}`
              : null;
            return (
            <div className="mt-4 bg-indigo-50 border border-indigo-200 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-pulse"></div>
                  <span className="text-sm font-semibold text-indigo-800">Scraping en progreso</span>
                  {stepName && (
                    <span className="text-xs text-indigo-500 bg-indigo-100 px-2 py-0.5 rounded-full">{stepName}</span>
                  )}
                </div>
                <span className="text-sm font-bold text-indigo-700">
                  {elapsedStr}
                  {remaining != null && remaining > 0 && (
                    <span className="text-indigo-400 font-normal ml-1">· ~{remaining} min restantes</span>
                  )}
                </span>
              </div>
              <div className="w-full bg-indigo-100 rounded-full h-3 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 relative overflow-hidden ${pct > 0 ? "bg-indigo-500" : "bg-indigo-400"}`}
                  style={{ width: pct > 0 ? `${pct}%` : "100%", opacity: pct > 0 ? 1 : 0.4 }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/40 to-transparent"
                    style={{ animation: "shimmer 2s infinite linear", backgroundSize: "200% 100%" }}></div>
                </div>
              </div>
              <div className="flex items-center justify-between mt-2 text-xs text-indigo-600">
                <span>
                  {pct > 0 ? `${pct}%` : "Ejecutando..."}
                  {stepsInfo && <span className="ml-2 text-indigo-400">({stepsInfo})</span>}
                </span>
                {scrapingProgress.started_at && (
                  <span className="text-indigo-400">
                    Iniciado: {new Date(scrapingProgress.started_at).toLocaleTimeString("es-EC", { hour: "2-digit", minute: "2-digit" })}
                  </span>
                )}
              </div>
              {tp && !tp.is_estimate && (
                <div className="mt-1.5 text-[11px] text-indigo-400 italic">
                  Estimación basada en {tp.based_on_runs} ejecución{tp.based_on_runs !== 1 ? "es" : ""} anterior{tp.based_on_runs !== 1 ? "es" : ""} (~{tp.estimated_total_min} min promedio)
                </div>
              )}
              {tp?.is_estimate && (
                <div className="mt-1.5 text-[11px] text-indigo-400 italic">
                  Estimación aproximada (~{tp.estimated_total_min} min). Se ajustará con ejecuciones futuras.
                </div>
              )}
              {scrapingProgress.html_url && (
                <a href={scrapingProgress.html_url} target="_blank" rel="noopener noreferrer"
                  className="inline-block mt-2 text-xs text-indigo-500 hover:text-indigo-700 underline">
                  Ver logs en GitHub Actions →
                </a>
              )}
            </div>
            );
          })()}

          {/* Último scraping completado */}
          {scrapingProgress && !scrapingProgress.running && scrapingProgress.status === "completed" && (
            <div className={`mt-4 text-xs px-3 py-2 rounded-lg ${scrapingProgress.conclusion === "success" ? "bg-green-50 text-green-700" : "bg-red-50 text-red-700"}`}>
              Último scraping: {scrapingProgress.conclusion === "success" ? "✅ completado" : "❌ " + (scrapingProgress.conclusion || "error")}
              {scrapingProgress.updated_at && (
                <span className="ml-2 text-gray-400">
                  {new Date(scrapingProgress.updated_at).toLocaleString("es-EC", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}
                </span>
              )}
              {scrapingProgress.html_url && (
                <a href={scrapingProgress.html_url} target="_blank" rel="noopener noreferrer" className="ml-2 underline">ver logs</a>
              )}
            </div>
          )}
        </div>

        {/* Cookie AVAC */}
        <AvacCookieManager />
        <CifradoBackfillManager />

        {/* Herramientas de Alertas */}
        <AlertTools />

        <div className="mt-4 pt-4 border-t border-gray-100">
          <label className="block text-sm font-semibold text-gray-700 mb-2">
            Subir datos y ejecutar ETL
          </label>
          <p className="text-xs text-gray-400 mb-2">
            Sube un archivo ZIP con los CSVs de calificaciones históricas (TableauHistorico/), IngresosAVAC/, Tareas/, Reportes/ y TercerasMatriculas/.
            Se extraen a la carpeta data/ del servidor y se ejecuta el ETL automáticamente.
          </p>
          <div className="flex items-center gap-3">
            <input
              type="file"
              accept=".zip"
              id="etl-zip-upload"
              className="text-sm file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
              disabled={uploadLoading}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                setUploadLoading(true);
                setUploadMsg("");
                try {
                  const result = await api.uploadAndRunETL(file);
                  setUploadMsg(result.message || "ZIP subido y ETL iniciado");
                  setTimeout(() => api.getETLRuns().then(setRuns), 3000);
                } catch (err) {
                  setUploadMsg("Error: " + err.message);
                } finally {
                  setUploadLoading(false);
                  e.target.value = "";
                }
              }}
            />
            {uploadLoading && <span className="text-sm text-blue-600 animate-pulse">Subiendo y ejecutando...</span>}
          </div>
          {uploadMsg && (
            <div className={`text-sm mt-3 px-4 py-2 rounded-lg ${uploadMsg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
              {uploadMsg}
            </div>
          )}
        </div>

        {/* Carga Histórica: subir datos AVAC/reporte de un periodo pasado */}
        <HistoricoUpload />

        {/* Subir archivos de Prácticas Preprofesionales */}
        <PracticasUpload />
      </div>

      {/* Historial ETL */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <h2 className="px-5 py-4 font-semibold text-gray-800 border-b border-gray-100">
          Historial de Ejecuciones ETL
          {runsData.total > 0 && <span className="text-xs font-normal text-gray-400 ml-2">({runsData.total})</span>}
        </h2>
        {runsData.items.length === 0 ? (
          <p className="text-center py-8 text-gray-400 text-sm">Sin ejecuciones registradas</p>
        ) : (
          <>
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-4 py-2.5 text-gray-600 font-medium">Inicio</th>
                  <th className="text-left px-4 py-2.5 text-gray-600 font-medium">Tipo</th>
                  <th className="text-left px-4 py-2.5 text-gray-600 font-medium">Descripción</th>
                  <th className="text-center px-4 py-2.5 text-gray-600 font-medium">Estado</th>
                  <th className="text-center px-4 py-2.5 text-gray-600 font-medium">Registros</th>
                  <th className="text-left px-4 py-2.5 text-gray-600 font-medium">Disparado por</th>
                </tr>
              </thead>
              <tbody>
                {runsData.items.map(run => (
                  <tr key={run.id} className="border-t border-gray-100">
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">
                      {run.started_at ? new Date(run.started_at).toLocaleString("es-EC") : "—"}
                    </td>
                    <td className="px-4 py-3 capitalize text-gray-700">{run.tipo}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs max-w-[260px] truncate" title={run.descripcion || ""}>
                      {run.descripcion || "—"}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                        ${run.status === "success" ? "bg-green-100 text-green-700"
                          : run.status === "error" ? "bg-red-100 text-red-700"
                          : run.status === "partial" ? "bg-orange-100 text-orange-700"
                          : "bg-yellow-100 text-yellow-700"}`}>
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center font-mono">{run.registros_insertados ?? "—"}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{run.triggered_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {/* Paginación */}
            {runsData.pages > 1 && (
              <div className="flex items-center justify-center gap-1 py-3 border-t border-gray-100">
                <button
                  onClick={() => loadRuns(runsPage - 1)}
                  disabled={runsPage <= 1}
                  className="px-2 py-1 text-xs rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
                >‹</button>
                {Array.from({ length: runsData.pages }, (_, i) => i + 1).map(p => (
                  <button
                    key={p}
                    onClick={() => loadRuns(p)}
                    className={`px-2.5 py-1 text-xs rounded font-medium ${p === runsPage ? "bg-blue-600 text-white" : "text-gray-600 hover:bg-gray-100"}`}
                  >{p}</button>
                ))}
                <button
                  onClick={() => loadRuns(runsPage + 1)}
                  disabled={runsPage >= runsData.pages}
                  className="px-2 py-1 text-xs rounded text-gray-500 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed"
                >›</button>
              </div>
            )}
          </>
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
              setMlMsg("Iniciando entrenamiento...");
              try {
                const r = await api.trainModel();
                if (r.status === "started" || r.status === "already_running") {
                  setMlMsg("Entrenando en background...");
                  // Polling cada 3s hasta que termine
                  const poll = setInterval(async () => {
                    try {
                      const st = await api.getTaskStatus();
                      if (!st.running) {
                        clearInterval(poll);
                        setMlLoading(false);
                        if (st.error) {
                          setMlMsg("Error: " + st.error);
                        } else if (st.result?.status === "ok") {
                          setMlMsg(`Modelo entrenado (${st.result.estudiantes} estudiantes, ${st.result.periodos?.length} periodos) en ${st.elapsed_seconds}s`);
                          loadMlStatus();
                        } else {
                          setMlMsg(`Aviso: ${st.result?.message || "sin resultado"}`);
                        }
                      } else {
                        setMlMsg(`Entrenando... (${Math.round(st.elapsed_seconds)}s)`);
                      }
                    } catch { /* ignore polling errors */ }
                  }, 3000);
                } else {
                  setMlMsg(r.status === "ok"
                    ? `Modelo entrenado (${r.estudiantes} estudiantes)`
                    : `Aviso: ${r.message || "sin resultado"}`);
                  setMlLoading(false);
                  loadMlStatus();
                }
              } catch (e) { setMlMsg("Error: " + e.message); setMlLoading(false); }
            }}
            disabled={mlLoading}
            className="bg-brand text-white px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-brand-light transition-colors disabled:opacity-60"
          >
            {mlLoading ? "Entrenando..." : "Reentrenar Modelo"}
          </button>
          <button
            onClick={async () => {
              setMlLoading(true);
              setMlMsg("Iniciando predicciones...");
              try {
                const r = await api.runPredictions();
                if (r.status === "started" || r.status === "already_running") {
                  setMlMsg("Ejecutando predicciones...");
                  const poll = setInterval(async () => {
                    try {
                      const st = await api.getTaskStatus();
                      if (!st.running) {
                        clearInterval(poll);
                        setMlLoading(false);
                        if (st.error) {
                          setMlMsg("Error: " + st.error);
                        } else if (st.result?.status === "ok") {
                          setMlMsg(`Predicciones actualizadas para ${st.result.updated} estudiantes en ${st.elapsed_seconds}s`);
                          loadMlStatus();
                        } else {
                          setMlMsg(`Aviso: ${st.result?.message || "sin resultado"}`);
                        }
                      } else {
                        setMlMsg(`Ejecutando predicciones... (${Math.round(st.elapsed_seconds)}s)`);
                      }
                    } catch { /* ignore polling errors */ }
                  }, 3000);
                } else {
                  setMlMsg(r.status === "ok"
                    ? `Predicciones actualizadas para ${r.updated} estudiantes`
                    : `Aviso: ${r.message || "sin resultado"}`);
                  setMlLoading(false);
                }
              } catch (e) { setMlMsg("Error: " + e.message); setMlLoading(false); }
            }}
            disabled={mlLoading}
            className="bg-brand-gold text-brand-dark px-5 py-2.5 rounded-lg text-sm font-semibold hover:bg-brand-gold-light transition-colors disabled:opacity-60"
          >
            {mlLoading ? "Ejecutando..." : "Ejecutar Predicciones"}
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-2">
          Entrena modelos de deserción y reprobación con datos históricos (P57-P67). Las predicciones se ejecutan automáticamente al final del ETL si hay un modelo entrenado.
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
// ── Subcomponente: Carga Histórica (AVAC + reporte para periodo pasado) ──
// ─────────────────────────────────────────────────────────────────────────────
// Herramientas de diagnóstico y regeneración de alertas
function AlertTools() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [debugData, setDebugData] = useState(null);
  const [showDebug, setShowDebug] = useState(false);

  const regenerar = async () => {
    if (!confirm("¿Regenerar todas las alertas? Esto eliminará las actuales y creará nuevas.")) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await api.generateAlerts();
      setResult(res);
    } catch (e) {
      setResult({ error: e.message });
    }
    setLoading(false);
  };

  const [diag, setDiag] = useState(null);
  const [recalcLoading, setRecalcLoading] = useState(false);
  const [recalcResult, setRecalcResult] = useState(null);

  const recalcular = async () => {
    if (!confirm(
      "¿Recalcular riesgo y alertas desde los datos ya guardados?\n\n" +
      "NO vuelve a scrapear (eso tarda ~2h). Recalcula sobre la última foto de AVAC " +
      "aplicando las reglas actuales: descarta aulas donde el estudiante ya no está " +
      "matriculado, cursos de bloques cerrados y tareas que aún no vencen.\n\n" +
      "Los niveles de riesgo van a cambiar."
    )) return;
    setRecalcLoading(true);
    setRecalcResult(null);
    try {
      setRecalcResult(await api.recalcularIndicadores());
    } catch (e) {
      setRecalcResult({ error: e.message });
    }
    setRecalcLoading(false);
  };

  const loadDebug = async () => {
    setShowDebug(!showDebug);
    if (!showDebug && !debugData) {
      try {
        const res = await api.debugAlertConditions();
        setDebugData(res);
      } catch (e) {
        setDebugData({ error: e.message });
      }
    }
  };

  return (
    <div className="mt-4 pt-4 border-t border-gray-100">
      <div className="flex items-center justify-between mb-2">
        <label className="text-sm font-semibold text-gray-700">Alertas</label>
        <div className="flex gap-2">
          <button onClick={loadDebug}
            className="text-xs px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors">
            {showDebug ? "Ocultar" : "Diagnóstico"}
          </button>
          <button onClick={regenerar} disabled={loading}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-100 hover:bg-indigo-200 text-indigo-700 transition-colors disabled:opacity-50">
            {loading ? "Regenerando..." : "Regenerar Alertas"}
          </button>
          {/* Regenerar alertas NO recalcula el riesgo: días, % de tareas y nivel los
              computa el ETL desde el scraping. Esto los recalcula desde la BD. */}
          <button onClick={recalcular} disabled={recalcLoading}
            className="text-xs px-3 py-1.5 rounded-lg bg-amber-100 hover:bg-amber-200 text-amber-800 font-medium transition-colors disabled:opacity-50"
            title="Recalcula días sin acceso, % de tareas y nivel de riesgo desde los datos ya guardados, sin volver a scrapear">
            {recalcLoading ? "Recalculando..." : "♻️ Recalcular riesgo (sin scraping)"}
          </button>
          <button onClick={async () => { setDiag(await api.getDiagnosticoRiesgo()); }}
            className="text-xs px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors"
            title="Mide qué componente hunde la clasificación de riesgo">
            🔬 Diagnóstico de riesgo
          </button>
        </div>
      </div>

      {diag && (
        <div className="text-xs p-3 rounded-lg mb-2 bg-slate-50 border border-slate-200 text-slate-800">
          <div className="font-semibold mb-2">🔬 Por qué sale ese nivel de riesgo</div>
          <div className="mb-1">
            Acceso AVAC (vale 0.30 del índice): con el <strong>máximo</strong> entre asignaturas vale{" "}
            <strong className="text-red-700">{diag.acceso?.puntaje_con_maximo}</strong>{" "}
            (prom. {diag.acceso?.promedio_maximo_dias}d) · con el <strong>último acceso real</strong> valdría{" "}
            <strong className="text-emerald-700">{diag.acceso?.puntaje_con_ultimo_acceso}</strong>{" "}
            (prom. {diag.acceso?.promedio_ultimo_acceso_dias}d).
          </div>
          <div className="mb-1">
            Índice promedio: <strong>{diag.indice?.promedio}</strong> · umbral para "Bajo": {diag.indice?.umbral_bajo} ·
            Tareas: {diag.tareas?.promedio_pct}%
          </div>
          <div className="text-slate-500 mt-2">{diag.acceso?.explicacion}</div>
          <div className="text-slate-500 mt-1">{diag.que_mirar}</div>
          <details className="mt-2"><summary className="cursor-pointer text-slate-600">Ver distribuciones</summary>
            <pre className="mt-1 text-[10px] overflow-auto">{JSON.stringify(
              { maximo: diag.acceso?.distribucion_maximo, ultimo_acceso: diag.acceso?.distribucion_ultimo_acceso, niveles: diag.niveles },
              null, 1)}</pre>
          </details>
        </div>
      )}

      {recalcResult && (
        <div className={`text-xs p-3 rounded-lg mb-2 ${recalcResult.error ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-900"}`}>
          {recalcResult.error ? `Error: ${recalcResult.error}` : !recalcResult.ok ? recalcResult.motivo : (
            <>
              <div className="font-semibold mb-1">
                ✅ {recalcResult.estudiantes_actualizados} estudiantes recalculados ·{" "}
                {recalcResult.cambiaron_de_nivel} cambiaron de nivel de riesgo
              </div>
              <div className="text-amber-800">
                Descartado: {recalcResult.registros_descartados?.aulas_fantasma} registros de aulas
                sin matrícula · {recalcResult.registros_descartados?.cursos_de_bloque_cerrado} de
                cursos de bloque cerrado · {recalcResult.registros_descartados?.tareas_aun_no_vencidas} tareas
                que aún no vencen.
              </div>
              {recalcResult.tareas?.por_que_importa && (
                <div className="mt-2 pt-2 border-t border-amber-200">
                  <strong className="text-amber-900">
                    ⚠️ Solo {recalcResult.tareas.estudiantes_con_datos} de {recalcResult.estudiantes_actualizados} estudiantes
                    ({recalcResult.tareas.pct_con_datos}%) tienen datos de tareas.
                  </strong>
                  <div className="text-amber-800 mt-1">{recalcResult.tareas.por_que_importa}</div>
                </div>
              )}
              {recalcResult.alertas && (
                <div className="text-amber-800 mt-1">
                  Alertas: {recalcResult.alertas.created} creadas ({recalcResult.alertas.cleaned} eliminadas).
                </div>
              )}
              <div className="text-gray-500 mt-1">{recalcResult.nota}</div>
            </>
          )}
        </div>
      )}
      {result && (
        <div className={`text-xs p-2 rounded-lg mb-2 ${result.error ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {result.error ? `Error: ${result.error}` : `✅ ${result.created} alertas creadas (${result.cleaned} anteriores eliminadas)`}
          {result.detail && <div className="mt-1 text-gray-500">{result.detail}</div>}
        </div>
      )}
      {showDebug && debugData && (
        <div className="text-xs bg-gray-50 rounded-lg p-3 max-h-64 overflow-auto font-mono whitespace-pre-wrap">
          {JSON.stringify(debugData, null, 2)}
        </div>
      )}
    </div>
  );
}

// Gestión de Cookie AVAC (MoodleSession)
// ─────────────────────────────────────────────────────────────────────────────
function CifradoBackfillManager() {
  const [loading, setLoading] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  const run = async (mode) => {
    if (mode === "apply" && !window.confirm("¿Cifrar el histórico ahora? Asegúrate de tener un BACKUP de la BD. No borra el texto plano.")) return;
    setLoading(mode); setError(""); setResult(null);
    try {
      const r = await api.cifradoBackfill(mode);
      setResult({ mode, data: r });
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading("");
    }
  };

  return (
    <div className="mt-4 pt-4 border-t border-gray-100">
      <div className="flex items-center justify-between mb-1">
        <label className="text-sm font-semibold text-gray-700">Cifrado en reposo (histórico)</label>
        <div className="flex gap-2">
          <button onClick={() => run("dry-run")} disabled={!!loading}
            className="text-xs px-3 py-1.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 transition-colors disabled:opacity-50">
            {loading === "dry-run" ? "Simulando..." : "Dry-run"}
          </button>
          <button onClick={() => run("apply")} disabled={!!loading}
            className="text-xs px-3 py-1.5 rounded-lg bg-indigo-100 hover:bg-indigo-200 text-indigo-700 transition-colors disabled:opacity-50">
            {loading === "apply" ? "Cifrando..." : "Aplicar"}
          </button>
          <button onClick={() => run("verify")} disabled={!!loading}
            className="text-xs px-3 py-1.5 rounded-lg bg-emerald-100 hover:bg-emerald-200 text-emerald-700 transition-colors disabled:opacity-50">
            {loading === "verify" ? "Verificando..." : "Verificar"}
          </button>
        </div>
      </div>
      <p className="text-xs text-gray-400 mb-2">
        Rellena el cifrado de los registros previos. Orden seguro: Dry-run &rarr; Aplicar &rarr; Verificar. Haz un backup antes de Aplicar.
      </p>
      {error && <div className="text-xs p-2 rounded-lg mb-2 bg-red-50 text-red-700">Error: {error}</div>}
      {result && (
        <div className="text-xs bg-gray-50 rounded-lg p-3 max-h-64 overflow-auto font-mono whitespace-pre-wrap">
          {JSON.stringify(result.data, null, 2)}
        </div>
      )}
    </div>
  );
}

function AvacCookieManager() {
  const [cookieValue, setCookieValue] = useState("");
  const [cookieStatus, setCookieStatus] = useState(null); // {configured, valid, message, cookie_preview}
  const [loading, setLoading] = useState(false);
  const [checkLoading, setCheckLoading] = useState(true);
  const [msg, setMsg] = useState("");

  const checkCookie = useCallback(async () => {
    setCheckLoading(true);
    try {
      const data = await api.getAvacCookie();
      setCookieStatus(data);
    } catch {
      setCookieStatus(null);
    } finally {
      setCheckLoading(false);
    }
  }, []);

  useEffect(() => { checkCookie(); }, [checkCookie]);

  const handleSave = async () => {
    const trimmed = cookieValue.trim();
    if (!trimmed) { setMsg("Error: Pega la cookie MoodleSession"); return; }
    setLoading(true);
    setMsg("");
    try {
      const result = await api.updateAvacCookie(trimmed);
      setMsg(result.message || "Cookie guardada y validada");
      setCookieValue("");
      await checkCookie();
    } catch (e) {
      setMsg("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  };

  const statusColor = cookieStatus?.valid
    ? "bg-green-100 text-green-700"
    : cookieStatus?.configured
      ? "bg-yellow-100 text-yellow-700"
      : "bg-gray-100 text-gray-500";

  const statusIcon = cookieStatus?.valid ? "\u2705" : cookieStatus?.configured ? "\u26A0\uFE0F" : "\u274C";

  return (
    <div className="mt-4 pt-4 border-t border-gray-100">
      <label className="block text-sm font-semibold text-gray-700 mb-1">
        Cookie AVAC (MoodleSession)
      </label>
      <p className="text-xs text-gray-400 mb-3">
        Para el scraping automático, pega aquí la cookie MoodleSession de tu sesión AVAC.
        Abre AVAC en tu navegador, inicia sesión, y copia la cookie desde DevTools (F12 &gt; Application &gt; Cookies).
      </p>

      {/* Estado actual */}
      {checkLoading ? (
        <p className="text-xs text-gray-400 mb-3">Verificando cookie...</p>
      ) : (
        <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium mb-3 ${statusColor}`}>
          <span>{statusIcon}</span>
          {cookieStatus?.valid
            ? `Cookie activa${cookieStatus.cookie_preview ? ` (${cookieStatus.cookie_preview})` : ""}`
            : cookieStatus?.configured
              ? `Cookie expirada${cookieStatus.cookie_preview ? ` (${cookieStatus.cookie_preview})` : ""}`
              : "Sin cookie configurada"}
        </div>
      )}

      <div className="flex items-center gap-3">
        <input
          type="text"
          value={cookieValue}
          onChange={(e) => setCookieValue(e.target.value)}
          placeholder="Pega aquí la cookie MoodleSession..."
          className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-blue-300 focus:border-blue-400 outline-none font-mono"
          disabled={loading}
        />
        <button
          onClick={handleSave}
          disabled={loading || !cookieValue.trim()}
          className="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm font-semibold hover:bg-indigo-700 transition-colors disabled:opacity-60 whitespace-nowrap"
        >
          {loading ? "Validando..." : "Guardar Cookie"}
        </button>
        <button
          onClick={checkCookie}
          disabled={checkLoading}
          className="text-gray-500 hover:text-gray-700 px-3 py-2 rounded-lg text-sm border border-gray-200 hover:bg-gray-50 transition-colors disabled:opacity-60"
          title="Verificar estado de la cookie"
        >
          {checkLoading ? "..." : "Verificar"}
        </button>
      </div>

      {msg && (
        <div className={`text-sm mt-3 px-4 py-2 rounded-lg ${msg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {msg}
        </div>
      )}
    </div>
  );
}

function HistoricoUpload() {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");
  const [periodo, setPeriodo] = useState("P67");

  return (
    <div className="mt-4 pt-4 border-t border-gray-100">
      <label className="block text-sm font-semibold text-gray-700 mb-2">
        Carga histórica (periodo pasado)
      </label>
      <p className="text-xs text-gray-400 mb-2">
        Sube un ZIP con datos AVAC y reporte de un <strong>periodo anterior</strong> (ej. P67).
        Los datos se etiquetan con ese periodo y NO afectan al semestre activo.
        Incluye: <em>IngresosAVAC/*.csv</em>, <em>Tareas/*.csv</em>, <em>Reportes/*_reporte.xlsx</em>.
        También re-enriquece las calificaciones del periodo con repitencias del reporte.
      </p>
      <div className="flex items-center gap-3 flex-wrap">
        <div>
          <label className="block text-xs text-gray-500 mb-1">Periodo</label>
          <input
            value={periodo}
            onChange={e => setPeriodo(e.target.value)}
            placeholder="P67"
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-24 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
        <div className="flex-1">
          <label className="block text-xs text-gray-500 mb-1">Archivo ZIP</label>
          <input
            type="file"
            accept=".zip"
            id="historico-upload"
            className="text-sm file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-purple-50 file:text-purple-700 hover:file:bg-purple-100"
            disabled={loading}
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              if (!periodo.trim()) { setMsg("Error: Ingresa el periodo (ej. P67)"); return; }
              setLoading(true);
              setMsg("");
              try {
                const result = await api.uploadHistorico(file, periodo.trim());
                setMsg(result.message || "ZIP histórico subido y ETL iniciado");
              } catch (err) {
                setMsg("Error: " + err.message);
              } finally {
                setLoading(false);
                e.target.value = "";
              }
            }}
          />
        </div>
        {loading && <span className="text-sm text-purple-600 animate-pulse self-end pb-2">Subiendo...</span>}
      </div>
      {msg && (
        <div className={`text-sm mt-3 px-4 py-2 rounded-lg ${msg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-purple-50 text-purple-700"}`}>
          {msg}
        </div>
      )}
    </div>
  );
}

// ── Subcomponente: Upload de Prácticas Preprofesionales ──
function PracticasUpload() {
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState("");

  return (
    <div className="mt-4 pt-4 border-t border-gray-100">
      <label className="block text-sm font-semibold text-gray-700 mb-2">
        Subir datos de Prácticas Preprofesionales
      </label>
      <p className="text-xs text-gray-400 mb-2">
        Sube los archivos .xlsx de prácticas: <strong>Formularios Practica P*.xlsx</strong> (datos de estudiantes y escuelas)
        y <strong>Escuelas Bilingues SEIBE*.xlsx</strong> (catálogo con ubicaciones). Se cruzan por código AMIE.
      </p>
      <div className="flex items-center gap-3">
        <input
          type="file"
          accept=".xlsx"
          multiple
          id="practicas-upload"
          className="text-sm file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-amber-50 file:text-amber-700 hover:file:bg-amber-100"
          disabled={loading}
          onChange={async (e) => {
            const files = Array.from(e.target.files || []);
            if (!files.length) return;
            setLoading(true);
            setMsg("");
            try {
              const result = await api.uploadPracticasFiles(files);
              setMsg(result.message || "Archivos subidos y ETL de prácticas iniciado");
            } catch (err) {
              setMsg("Error: " + err.message);
            } finally {
              setLoading(false);
              e.target.value = "";
            }
          }}
        />
        {loading && <span className="text-sm text-amber-600 animate-pulse">Subiendo...</span>}
      </div>
      {msg && (
        <div className={`text-sm mt-3 px-4 py-2 rounded-lg ${msg.startsWith("Error") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {msg}
        </div>
      )}
    </div>
  );
}


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
  const [semesters, setSemesters] = useState([]);
  const [filterSemestre, setFilterSemestre] = useState("__actual__");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 15;

  // Cargar lista de semestres disponibles
  useEffect(() => {
    (async () => {
      try {
        const data = await api.get("/courses/semester/all");
        setSemesters(data || []);
        // Preseleccionar el semestre activo
        const activo = (data || []).find(s => s.activo);
        if (activo) setFilterSemestre(activo.semestre);
      } catch { setSemesters([]); }
    })();
  }, []);

  const loadCourses = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (filterSemestre && filterSemestre !== "__todos__") {
        if (filterSemestre === "__actual__") {
          // Buscar el semestre activo
          const activo = semesters.find(s => s.activo);
          if (activo) params.set("semestre", activo.semestre);
        } else {
          params.set("semestre", filterSemestre);
        }
      }
      const qs = params.toString();
      const data = await api.get(`/courses${qs ? "?" + qs : ""}`);
      setCourses(data);
      setPage(1); // Reset page on filter change
    } catch { setCourses([]); }
    setLoading(false);
  }, [filterSemestre, semesters]);

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
        await api.post("/courses", form);
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

      {/* Filtro por período */}
      <div className="flex items-center gap-3">
        <label className="text-xs text-gray-500 font-medium">Período:</label>
        <select
          value={filterSemestre}
          onChange={e => setFilterSemestre(e.target.value)}
          className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
        >
          <option value="__todos__">Todos los períodos</option>
          {semesters.map(s => (
            <option key={s.semestre} value={s.semestre}>
              {s.semestre}{s.activo ? " (actual)" : ""}
            </option>
          ))}
        </select>
        <span className="text-xs text-gray-400">{courses.length} curso{courses.length !== 1 ? "s" : ""}</span>
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
          <p className="text-center py-8 text-gray-400 text-sm">No hay cursos configurados para este período</p>
        ) : (() => {
          const totalPages = Math.ceil(courses.length / PAGE_SIZE);
          const paged = courses.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
          return (
            <>
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
                  {paged.map(c => (
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
              {totalPages > 1 && (
                <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50">
                  <span className="text-xs text-gray-500">
                    Mostrando {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, courses.length)} de {courses.length}
                  </span>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setPage(p => Math.max(1, p - 1))}
                      disabled={page === 1}
                      className="px-2.5 py-1 rounded text-xs font-medium border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Anterior
                    </button>
                    {(() => {
                      // Show max 7 page buttons: 1 ... p-1 p p+1 ... last
                      const pages = [];
                      const show = new Set([1, totalPages, page, page - 1, page + 1, page - 2, page + 2]
                        .filter(p => p >= 1 && p <= totalPages));
                      const sorted = [...show].sort((a, b) => a - b);
                      sorted.forEach((p, i) => {
                        if (i > 0 && p - sorted[i - 1] > 1) {
                          pages.push(<span key={`e${p}`} className="px-1 text-xs text-gray-400">…</span>);
                        }
                        pages.push(
                          <button key={p} onClick={() => setPage(p)}
                            className={`px-2.5 py-1 rounded text-xs font-medium border ${
                              p === page ? "bg-brand text-white border-brand" : "border-gray-300 bg-white hover:bg-gray-50 text-gray-700"
                            }`}>{p}</button>
                        );
                      });
                      return pages;
                    })()}
                    <button
                      onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      disabled={page === totalPages}
                      className="px-2.5 py-1 rounded text-xs font-medium border border-gray-300 bg-white hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      Siguiente
                    </button>
                  </div>
                </div>
              )}
            </>
          );
        })()}
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
  const [editing, setEditing] = useState(null); // semestre string being edited (dates)
  const [editDates, setEditDates] = useState({});
  const [renamingSem, setRenamingSem] = useState(null); // semestre string being renamed
  const [renameValue, setRenameValue] = useState("");
  const [lastAction, setLastAction] = useState(null); // {type, data} for undo

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
      await api.post("/courses/semester", newSem);
      setMsg("Semestre creado");
      setNewSem({ semestre: "", bloque_actual: "1" });
      loadSemesters();
    } catch (err) {
      setMsg("Error: " + err.message);
    }
  };

  const handleActivate = async (semestre) => {
    try {
      const prev = semesters.find(s => s.activo)?.semestre || null;
      await api.post(`/courses/semester/${semestre}/activate`);
      setLastAction({ type: "activate", prev });
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

  const toLocalDate = (isoStr) => {
    if (!isoStr) return "";
    return isoStr.slice(0, 10); // "YYYY-MM-DD"
  };

  const [editCalendario, setEditCalendario] = useState([]);

  const parseCalendario = (jsonStr) => {
    try { return JSON.parse(jsonStr || "[]"); } catch { return []; }
  };

  const startEditing = (s) => {
    setEditing(s.semestre);
    setEditDates({
      bloque1_inicio: toLocalDate(s.bloque1_inicio),
      bloque1_fin: toLocalDate(s.bloque1_fin),
      bloque2_inicio: toLocalDate(s.bloque2_inicio),
      bloque2_fin: toLocalDate(s.bloque2_fin),
    });
    setEditCalendario(parseCalendario(s.calendario_academico));
  };

  const handleSaveDates = async () => {
    try {
      // Guardar fechas previas para deshacer
      const current = semesters.find(s => s.semestre === editing);
      const prevDates = current ? {
        bloque1_inicio: current.bloque1_inicio || null,
        bloque1_fin: current.bloque1_fin || null,
        bloque2_inicio: current.bloque2_inicio || null,
        bloque2_fin: current.bloque2_fin || null,
      } : null;

      const payload = {};
      for (const [k, v] of Object.entries(editDates)) {
        payload[k] = v ? `${v}T23:59:59` : null;
      }
      // For inicio fields, use start of day
      if (payload.bloque1_inicio) payload.bloque1_inicio = `${editDates.bloque1_inicio}T00:00:00`;
      if (payload.bloque2_inicio) payload.bloque2_inicio = `${editDates.bloque2_inicio}T00:00:00`;
      // Include calendario_academico
      payload.calendario_academico = JSON.stringify(editCalendario.filter(e => e.fecha));
      await api.patch(`/courses/semester/${editing}`, payload);
      setLastAction({ type: "dates", semestre: editing, prevDates });
      setMsg(`Fechas de ${editing} actualizadas`);
      setEditing(null);
      loadSemesters();
    } catch (err) {
      setMsg("Error: " + err.message);
    }
  };

  const startRename = (s) => {
    setRenamingSem(s.semestre);
    setRenameValue(s.semestre);
    setEditing(null); // close date editor if open
  };

  const handleRename = async () => {
    const trimmed = renameValue.trim();
    if (!trimmed || trimmed === renamingSem) { setRenamingSem(null); return; }
    try {
      await api.patch(`/courses/semester/${renamingSem}`, { semestre: trimmed });
      setLastAction({ type: "rename", from: renamingSem, to: trimmed });
      setMsg(`Semestre renombrado: ${renamingSem} → ${trimmed}`);
      setRenamingSem(null);
      loadSemesters();
    } catch (err) {
      setMsg("Error: " + (err?.response?.data?.detail || err.message));
    }
  };

  const handleUndo = async () => {
    if (!lastAction) return;
    try {
      if (lastAction.type === "rename") {
        await api.patch(`/courses/semester/${lastAction.to}`, { semestre: lastAction.from });
        setMsg(`Deshacer: ${lastAction.to} → ${lastAction.from}`);
      } else if (lastAction.type === "activate") {
        if (lastAction.prev) {
          await api.post(`/courses/semester/${lastAction.prev}/activate`);
          setMsg(`Deshacer: semestre activo restaurado a ${lastAction.prev}`);
        }
      } else if (lastAction.type === "dates") {
        await api.patch(`/courses/semester/${lastAction.semestre}`, lastAction.prevDates);
        setMsg(`Deshacer: fechas de ${lastAction.semestre} restauradas`);
      }
      setLastAction(null);
      loadSemesters();
    } catch (err) {
      setMsg("Error al deshacer: " + (err?.response?.data?.detail || err.message));
    }
  };

  const handleDelete = async (semestre) => {
    if (!window.confirm(`¿Eliminar el semestre "${semestre}"? Esta acción no se puede deshacer.`)) return;
    try {
      await api.delete(`/courses/semester/${semestre}`);
      setMsg(`Semestre ${semestre} eliminado`);
      loadSemesters();
    } catch (err) {
      setMsg("Error: " + (err?.response?.data?.detail || err.message));
    }
  };

  const handleDeactivateAll = async () => {
    if (!window.confirm("Esto desactivará todos los semestres y detendrá el scraping diario. ¿Continuar?")) return;
    try {
      await api.post("/courses/semester/deactivate-all");
      setMsg("Todos los semestres desactivados");
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
        <form onSubmit={handleCreate} className="flex gap-3 items-end flex-wrap">
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
          <div className="divide-y divide-gray-100">
            {semesters.map(s => {
              const isExpired = s.activo && (
                (s.bloque_actual === "1" && s.bloque1_fin && new Date(s.bloque1_fin) < new Date()) ||
                (s.bloque_actual === "2" && s.bloque2_fin && new Date(s.bloque2_fin) < new Date()) ||
                (!s.bloque1_fin && !s.bloque2_fin && false)
              );
              return (
              <div key={s.id} className="p-4">
                {/* Row 1: semestre info + actions */}
                <div className="flex items-center gap-4 flex-wrap">
                  {renamingSem === s.semestre ? (
                    <span className="flex items-center gap-1 min-w-[80px]">
                      <input value={renameValue} onChange={e => setRenameValue(e.target.value)}
                        onKeyDown={e => { if (e.key === "Enter") handleRename(); if (e.key === "Escape") setRenamingSem(null); }}
                        autoFocus
                        className="border border-blue-400 rounded px-2 py-0.5 text-sm font-semibold w-24 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      <button onClick={handleRename} className="text-xs text-green-600 hover:text-green-800">&#10003;</button>
                      <button onClick={() => setRenamingSem(null)} className="text-xs text-gray-400 hover:text-gray-600">&#10005;</button>
                    </span>
                  ) : (
                    <span className="font-semibold text-gray-800 min-w-[80px] cursor-pointer hover:text-blue-700"
                      onDoubleClick={() => startRename(s)} title="Doble clic para renombrar">
                      {s.semestre}
                    </span>
                  )}
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${s.activo ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                    {s.activo ? "Activo" : "Inactivo"}
                  </span>
                  {isExpired && (
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">
                      Finalizado
                    </span>
                  )}
                  <span className="text-gray-500 text-xs">Bloque {s.bloque_actual}</span>
                  <div className="flex items-center gap-2 ml-auto">
                    {!s.activo && (
                      <button onClick={() => handleActivate(s.semestre)}
                        className="text-xs px-2 py-1 rounded bg-brand text-white hover:bg-brand-light">
                        Activar
                      </button>
                    )}
                    <button onClick={() => startRename(s)}
                      className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50"
                      title="Renombrar semestre">
                      Editar
                    </button>
                    {!s.activo && (
                      <button onClick={() => handleDelete(s.semestre)}
                        className="text-xs px-2 py-1 rounded border border-red-300 text-red-600 hover:bg-red-50"
                        title="Eliminar semestre">
                        Eliminar
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
                    <button onClick={() => editing === s.semestre ? setEditing(null) : startEditing(s)}
                      className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-600 hover:bg-gray-50">
                      {editing === s.semestre ? "Cancelar" : "Fechas"}
                    </button>
                  </div>
                </div>

                {/* Row 2: dates + calendario display */}
                {editing !== s.semestre && (
                  <div className="mt-2 space-y-1">
                    {(s.bloque1_inicio || s.bloque1_fin || s.bloque2_inicio || s.bloque2_fin) && (
                      <div className="flex gap-6 text-xs text-gray-500">
                        {(s.bloque1_inicio || s.bloque1_fin) && (
                          <span>B1: {toLocalDate(s.bloque1_inicio) || "?"} a {toLocalDate(s.bloque1_fin) || "?"}</span>
                        )}
                        {(s.bloque2_inicio || s.bloque2_fin) && (
                          <span>B2: {toLocalDate(s.bloque2_inicio) || "?"} a {toLocalDate(s.bloque2_fin) || "?"}</span>
                        )}
                      </div>
                    )}
                    {s.calendario_academico && parseCalendario(s.calendario_academico).length > 0 && (
                      <div className="mt-2">
                        <div className="flex items-center gap-1.5 mb-1.5">
                          <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider">Calendario</span>
                          <span className="text-[10px] text-gray-300">({parseCalendario(s.calendario_academico).length} fechas)</span>
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {[...parseCalendario(s.calendario_academico)]
                            .sort((a, b) => (a.fecha || "").localeCompare(b.fecha || ""))
                            .map((e, i) => {
                              const tipoIcon = e.tipo === "paso_notas" ? "📊" :
                                               e.tipo === "examen" ? "📝" :
                                               e.tipo === "recuperacion" ? "🔄" : "📘";
                              const tipoBg = e.tipo === "paso_notas" ? "bg-amber-100 text-amber-800 border-amber-200" :
                                             e.tipo === "examen" ? "bg-purple-100 text-purple-800 border-purple-200" :
                                             e.tipo === "recuperacion" ? "bg-red-100 text-red-700 border-red-200" :
                                             "bg-blue-50 text-blue-700 border-blue-200";
                              return (
                                <span key={i} className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg border text-[11px] ${tipoBg}`}>
                                  <span>{tipoIcon}</span>
                                  <span className="font-semibold">{e.fecha?.split("-").reverse().join("/")}</span>
                                  <span className="text-gray-500">·</span>
                                  <span>{e.label || e.tipo}</span>
                                </span>
                              );
                            })}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Row 3: date editing form */}
                {editing === s.semestre && (
                  <div className="mt-3 bg-gray-50 rounded-lg p-4 space-y-3">
                    <p className="text-xs text-gray-600 font-medium">Fechas de bloque (el scraping se detiene al pasar la fecha fin)</p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Bloque 1 - Inicio</label>
                        <input type="date" value={editDates.bloque1_inicio}
                          onChange={e => setEditDates(d => ({ ...d, bloque1_inicio: e.target.value }))}
                          className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Bloque 1 - Fin</label>
                        <input type="date" value={editDates.bloque1_fin}
                          onChange={e => setEditDates(d => ({ ...d, bloque1_fin: e.target.value }))}
                          className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Bloque 2 - Inicio</label>
                        <input type="date" value={editDates.bloque2_inicio}
                          onChange={e => setEditDates(d => ({ ...d, bloque2_inicio: e.target.value }))}
                          className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-1">Bloque 2 - Fin</label>
                        <input type="date" value={editDates.bloque2_fin}
                          onChange={e => setEditDates(d => ({ ...d, bloque2_fin: e.target.value }))}
                          className="w-full border border-gray-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                      </div>
                    </div>

                    {/* Calendario académico */}
                    <div className="mt-4 border-t border-gray-200 pt-4">
                      <div className="flex items-center justify-between mb-3">
                        <div>
                          <p className="text-sm text-gray-700 font-semibold flex items-center gap-2">
                            <span className="text-base">📅</span> Calendario Académico
                          </p>
                          <p className="text-[11px] text-gray-400 mt-0.5">
                            Fechas clave del semestre — las alertas de "nota cero" inician 7 días después de la primera entrega
                          </p>
                        </div>
                        <button onClick={() => setEditCalendario(arr => [...arr, { fecha: "", tipo: "entrega", label: "" }])}
                          className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors flex items-center gap-1">
                          + Nueva fecha
                        </button>
                      </div>

                      {/* Leyenda de tipos */}
                      <div className="flex flex-wrap gap-3 mb-3 px-1">
                        <span className="inline-flex items-center gap-1 text-[10px]"><span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block"></span> Entrega</span>
                        <span className="inline-flex items-center gap-1 text-[10px]"><span className="w-2.5 h-2.5 rounded-full bg-purple-500 inline-block"></span> Examen</span>
                        <span className="inline-flex items-center gap-1 text-[10px]"><span className="w-2.5 h-2.5 rounded-full bg-amber-500 inline-block"></span> Paso de notas</span>
                        <span className="inline-flex items-center gap-1 text-[10px]"><span className="w-2.5 h-2.5 rounded-full bg-red-500 inline-block"></span> Recuperación</span>
                      </div>

                      {editCalendario.length === 0 ? (
                        <div className="text-center py-6 text-gray-400 text-sm border-2 border-dashed border-gray-200 rounded-xl">
                          No hay fechas configuradas. Haz clic en "+ Nueva fecha" para agregar.
                        </div>
                      ) : (
                        <div className="space-y-0">
                          {/* Header row */}
                          <div className="grid grid-cols-[40px_150px_160px_1fr_40px] gap-2 px-3 py-2 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
                            <span>#</span>
                            <span>Fecha</span>
                            <span>Tipo</span>
                            <span>Descripción</span>
                            <span></span>
                          </div>

                          {[...editCalendario]
                            .map((entry, origIdx) => ({ ...entry, origIdx }))
                            .sort((a, b) => (a.fecha || "9999").localeCompare(b.fecha || "9999"))
                            .map(({ origIdx: i, ...entry }, sortedIdx) => {
                              const isPasoNotas = entry.tipo === "paso_notas";
                              const isExamen = entry.tipo === "examen";
                              const isRecup = entry.tipo === "recuperacion";
                              const colorDot = isPasoNotas ? "bg-amber-500" :
                                               isExamen ? "bg-purple-500" :
                                               isRecup ? "bg-red-500" :
                                               "bg-blue-500";
                              const rowBg = isPasoNotas ? "bg-amber-50/60 hover:bg-amber-50" :
                                            isExamen ? "bg-purple-50/60 hover:bg-purple-50" :
                                            isRecup ? "bg-red-50/60 hover:bg-red-50" :
                                            "bg-white hover:bg-blue-50/40";
                              const borderLeft = isPasoNotas ? "border-l-amber-400" :
                                                 isExamen ? "border-l-purple-400" :
                                                 isRecup ? "border-l-red-400" :
                                                 "border-l-blue-400";
                              return (
                                <div key={i} className={`grid grid-cols-[40px_150px_160px_1fr_40px] gap-2 items-center px-3 py-2.5 rounded-lg border-l-[3px] ${borderLeft} ${rowBg} transition-colors ${sortedIdx > 0 ? "mt-1.5" : ""}`}>
                                  <span className={`w-6 h-6 rounded-full ${colorDot} text-white text-[10px] font-bold flex items-center justify-center`}>
                                    {sortedIdx + 1}
                                  </span>
                                  <input type="date" value={entry.fecha || ""}
                                    onChange={e => {
                                      const arr = [...editCalendario];
                                      arr[i] = { ...arr[i], fecha: e.target.value };
                                      setEditCalendario(arr);
                                    }}
                                    className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none" />
                                  <select value={entry.tipo || "entrega"}
                                    onChange={e => {
                                      const arr = [...editCalendario];
                                      arr[i] = { ...arr[i], tipo: e.target.value };
                                      setEditCalendario(arr);
                                    }}
                                    className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none font-medium">
                                    <option value="entrega">📘 Entrega</option>
                                    <option value="examen">📝 Examen</option>
                                    <option value="paso_notas">📊 Paso de notas</option>
                                    <option value="recuperacion">🔄 Recuperación</option>
                                  </select>
                                  <input type="text" value={entry.label || ""} placeholder="Ej: Entrega Unidad 1, Examen parcial..."
                                    onChange={e => {
                                      const arr = [...editCalendario];
                                      arr[i] = { ...arr[i], label: e.target.value };
                                      setEditCalendario(arr);
                                    }}
                                    className="border border-gray-200 rounded-lg px-2 py-1.5 text-sm bg-white focus:ring-2 focus:ring-blue-400 focus:border-transparent outline-none" />
                                  <button onClick={() => setEditCalendario(arr => arr.filter((_, j) => j !== i))}
                                    className="w-7 h-7 flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors text-sm">✕</button>
                                </div>
                              );
                            })}
                        </div>
                      )}
                    </div>

                    <button onClick={handleSaveDates}
                      className="bg-brand text-white px-4 py-1.5 rounded-lg text-sm font-semibold hover:bg-brand-light mt-3">
                      Guardar fechas y calendario
                    </button>
                  </div>
                )}
              </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="flex gap-3 items-center flex-wrap">
        {lastAction && (
          <button onClick={handleUndo}
            className="text-xs px-3 py-1.5 rounded border border-amber-400 text-amber-700 bg-amber-50 hover:bg-amber-100 font-medium">
            Deshacer {lastAction.type === "rename" ? `(${lastAction.from})` : lastAction.type === "activate" ? "(activación)" : "(fechas)"}
          </button>
        )}
        {semesters.some(s => s.activo) && (
          <button onClick={handleDeactivateAll}
            className="text-xs px-3 py-1.5 rounded border border-red-300 text-red-600 hover:bg-red-50">
            Desactivar todos los semestres
          </button>
        )}
      </div>

      <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 text-sm text-amber-800">
        <strong>Al inicio de cada semestre:</strong> Crea el nuevo semestre, configura las fechas de bloque
        (clic en "Fechas"), actívalo y agrega los cursos en la pestaña "Cursos".
        El scraping y las alertas se detendrán automáticamente al pasar la fecha de fin del bloque activo.
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// TAB: USUARIOS

// ── Pestañas disponibles para permisos granulares ──
const PERMISSION_TABS = [
  { key: "dashboard",      label: "Estudiantes",           group: "Monitoreo" },
  { key: "alertas",        label: "Alertas",               group: "Monitoreo" },
  { key: "intervenciones", label: "Intervenciones",        group: "Monitoreo" },
  { key: "ficha",          label: "Ficha Estudiante",      group: "Monitoreo" },
  { key: "asignaturas",    label: "Asignaturas",           group: "Académico" },
  { key: "entregas",       label: "Entregas",              group: "Académico" },
  { key: "docentes",       label: "Docentes",              group: "Académico" },
  { key: "tutorias",       label: "Tutorías",              group: "Académico" },
  { key: "resumen",        label: "Análisis Institucional",group: "Institucional" },
  { key: "about",          label: "Sobre Yachay Deep",     group: "Institucional" },
];

const ALL_TAB_KEYS = PERMISSION_TABS.map(t => t.key);

/* Permisos predefinidos por rol — se aplican al seleccionar el rol, pero se pueden personalizar */
const ROLE_PRESETS = {
  admin: null,  // null = acceso completo
  coordinador: ["dashboard", "alertas", "intervenciones", "ficha", "asignaturas", "entregas", "docentes", "tutorias", "resumen"],
  docente: ["dashboard", "ficha", "asignaturas", "entregas", "docentes"],
  monitor: ["dashboard", "alertas", "intervenciones", "ficha", "asignaturas", "entregas", "tutorias"],
};

const ROLE_LABELS = {
  admin: "Administrador",
  coordinador: "Coordinador",
  docente: "Docente",
  monitor: "Monitor",
};

function PermissionCheckboxes({ selected, onChange, compact = false }) {
  const grouped = {};
  PERMISSION_TABS.forEach(t => {
    if (!grouped[t.group]) grouped[t.group] = [];
    grouped[t.group].push(t);
  });

  const allSelected = selected === null || (Array.isArray(selected) && selected.length === ALL_TAB_KEYS.length);

  const handleToggleAll = () => {
    if (allSelected) {
      onChange([]);
    } else {
      onChange(null); // null = all access
    }
  };

  const handleToggle = (key) => {
    const current = selected === null ? [...ALL_TAB_KEYS] : [...(selected || [])];
    const idx = current.indexOf(key);
    if (idx >= 0) current.splice(idx, 1);
    else current.push(key);
    // If all selected, set to null (all access)
    if (current.length === ALL_TAB_KEYS.length) onChange(null);
    else onChange(current);
  };

  const isChecked = (key) => selected === null || (Array.isArray(selected) && selected.includes(key));

  return (
    <div className={compact ? "space-y-2" : "space-y-3"}>
      <label className="flex items-center gap-2 cursor-pointer">
        <input type="checkbox" checked={allSelected} onChange={handleToggleAll}
          className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
        <span className="text-sm font-semibold text-gray-700">Acceso completo</span>
      </label>
      {!allSelected && Object.entries(grouped).map(([group, tabs]) => (
        <div key={group} className={compact ? "" : "ml-2"}>
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide mb-1">{group}</p>
          <div className={compact ? "flex flex-wrap gap-x-4 gap-y-1" : "grid grid-cols-2 gap-1"}>
            {tabs.map(t => (
              <label key={t.key} className="flex items-center gap-1.5 cursor-pointer">
                <input type="checkbox" checked={isChecked(t.key)} onChange={() => handleToggle(t.key)}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
                <span className="text-sm text-gray-600">{t.label}</span>
              </label>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
function TabUsuarios() {
  const { isSuperAdmin, user: actor } = useAuth();
  const [users, setUsers] = useState([]);
  const [institutions, setInstitutions] = useState([]);
  const [newUser, setNewUser] = useState({ email: "", nombre: "", password: "", role: "monitor", permissions: null, tenant: null, send_welcome_email: true });
  const [userMsg, setUserMsg] = useState("");
  const [editing, setEditing] = useState(null); // user being edited, or null

  const reload = () => api.listUsers(getTenant()).then(setUsers).catch(() => setUserMsg("Error: No se pudieron cargar los usuarios"));

  const deleteUsuario = async (u) => {
    if (!window.confirm(`¿Eliminar definitivamente al usuario "${u.email}"? Esta acción no se puede deshacer.`)) return;
    const password = window.prompt("Para confirmar, ingresa TU contraseña de administrador:");
    if (!password) return;
    try {
      await api.deleteUser(u.id, password);
      setUserMsg("");
      reload();
    } catch (e) { setUserMsg("Error: " + e.message); }
  };

  useEffect(() => { reload(); }, []);
  useEffect(() => { api.getInstitutions().then(setInstitutions).catch(() => {}); }, []);
  useEffect(() => { if (!isSuperAdmin && actor?.tenant) setNewUser(u => ({ ...u, tenant: actor.tenant })); }, [isSuperAdmin, actor]);

  // Códigos de institución (subdominios) disponibles
  const tenantOptions = ["ups", "demo", ...institutions
    .map((i) => i.codigo)
    .filter((c) => c && !["ups", "demo"].includes(c))];

  const handleCreateUser = async (e) => {
    e.preventDefault();
    try {
      await api.createUser(newUser);
      setUserMsg("Usuario creado correctamente");
      setNewUser({ email: "", nombre: "", password: "", role: "monitor", permissions: null, tenant: null, send_welcome_email: true });
      reload();
    } catch (err) {
      setUserMsg("Error: " + err.message);
    }
  };

  const toggleUser = async (user) => {
    try {
      await api.updateUser(user.id, { is_active: !user.is_active });
      reload();
    } catch (err) {
      setUserMsg("Error: " + err.message);
    }
  };

  return (
    <div className="space-y-4">
      <h2 className="font-semibold text-gray-800">Gestión de Usuarios</h2>

      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="font-medium text-gray-700 mb-3 text-sm">Crear nuevo usuario</h3>
        <form onSubmit={handleCreateUser} className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <input value={newUser.email} onChange={e => setNewUser(u => ({ ...u, email: e.target.value }))}
            type="email" placeholder="Email" required
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <input value={newUser.nombre} onChange={e => setNewUser(u => ({ ...u, nombre: e.target.value }))}
            placeholder="Nombre completo" required
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <input value={newUser.password} onChange={e => setNewUser(u => ({ ...u, password: e.target.value }))}
            type="password" placeholder="Contraseña" required minLength={8}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          <select value={newUser.role} onChange={e => {
              const r = e.target.value;
              setNewUser(u => ({ ...u, role: r, permissions: ROLE_PRESETS[r] ?? null }));
            }}
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
            {Object.entries(ROLE_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          {isSuperAdmin ? (
          <select value={newUser.tenant ?? ""} onChange={e => setNewUser(u => ({ ...u, tenant: e.target.value || null }))}
            title="Institución a la que pertenece el usuario"
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white">
            <option value="">🌐 Global (todas)</option>
            {tenantOptions.map((c) => (
              <option key={c} value={c}>{c.toUpperCase()}</option>
            ))}
          </select>
          ) : (
            <input value={(actor?.tenant || "").toUpperCase()} disabled title="Tu institución"
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-600" />
          )}
          <button type="submit"
            className="bg-brand text-white rounded-lg py-2 text-sm font-semibold hover:bg-brand-light">
            Crear usuario
          </button>
        </form>

        {/* Permisos de pestañas */}
        <div className="mt-4 border-t border-gray-100 pt-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-700">Permisos de acceso</h4>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={newUser.send_welcome_email}
                onChange={e => setNewUser(u => ({ ...u, send_welcome_email: e.target.checked }))}
                className="rounded border-gray-300 text-blue-600 focus:ring-blue-500" />
              <span className="text-xs text-gray-500">Enviar email de bienvenida</span>
            </label>
          </div>
          <div className="flex items-center gap-2 mb-2">
            <span className="text-[11px] text-gray-400">
              Preset: <strong className="text-gray-600">{ROLE_LABELS[newUser.role]}</strong>
            </span>
            <button type="button" onClick={() => setNewUser(u => ({ ...u, permissions: ROLE_PRESETS[u.role] ?? null }))}
              className="text-[11px] text-blue-500 hover:text-blue-700 underline">
              Restaurar permisos del rol
            </button>
          </div>
          <PermissionCheckboxes
            selected={newUser.permissions}
            onChange={(perms) => setNewUser(u => ({ ...u, permissions: perms }))}
            compact
          />
        </div>
        {userMsg && <p className="text-sm mt-3">{userMsg}</p>}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Nombre</th>
              <th className="text-left px-5 py-2.5 text-gray-600 font-medium">Email</th>
              <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Rol</th>
              <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Institución</th>
              <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Estado</th>
              <th className="text-center px-5 py-2.5 text-gray-600 font-medium">Permisos</th>
              <th className="text-right px-5 py-2.5 text-gray-600 font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {users.map(u => (
              <tr key={u.id} className="border-t border-gray-100">
                <td className="px-5 py-2.5 font-medium text-gray-800">{u.nombre}</td>
                <td className="px-5 py-2.5 text-gray-500">{u.email}</td>
                <td className="px-5 py-2.5 text-center text-xs font-medium text-blue-600">{ROLE_LABELS[u.role] || u.role}</td>
                <td className="px-5 py-2.5 text-center text-xs text-gray-600">{u.tenant ? u.tenant.toUpperCase() : "Global"}</td>
                <td className="px-5 py-2.5 text-center">
                  <button onClick={() => toggleUser(u)}
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${u.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                    {u.is_active ? "Activo" : "Inactivo"}
                  </button>
                </td>
                <td className="px-5 py-2.5 text-center text-xs text-gray-500">
                  {u.permissions === null ? (
                    <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded-full">Completo</span>
                  ) : u.permissions?.length > 0 ? (
                    <span className="bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full">{u.permissions.length} módulos</span>
                  ) : (
                    <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded-full">Sin acceso</span>
                  )}
                </td>
                <td className="px-5 py-2.5 text-right">
                  <button onClick={() => setEditing(u)}
                    className="text-xs font-medium text-brand hover:text-brand-dark underline-offset-2 hover:underline">
                    Editar
                  </button>
                  {u.id !== actor?.id && (
                    <button onClick={() => deleteUsuario(u)}
                      className="ml-3 text-xs font-medium text-red-600 hover:text-red-700 underline-offset-2 hover:underline">
                      Eliminar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editing && (
        <EditUserModal
          user={editing}
          tenantOptions={tenantOptions}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); reload(); }}
          onError={(msg) => setUserMsg("Error: " + msg)}
        />
      )}
    </div>
  );
}

function EditUserModal({ user, tenantOptions = [], isSuperAdmin = false, actorTenant = null, onClose, onSaved, onError }) {
  const [nombre, setNombre] = useState(user.nombre || "");
  const [email, setEmail] = useState(user.email || "");
  const [role, setRole] = useState(user.role || "monitor");
  const [permissions, setPermissions] = useState(user.permissions ?? null);
  const [isActive, setIsActive] = useState(!!user.is_active);
  const [tenant, setTenant] = useState(user.tenant ?? null);
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const payload = {};
      if (email.trim() && email.trim().toLowerCase() !== user.email) payload.email = email.trim();
      if (nombre !== user.nombre) payload.nombre = nombre;
      if (role !== user.role) payload.role = role;
      if (isActive !== !!user.is_active) payload.is_active = isActive;
      if ((tenant ?? null) !== (user.tenant ?? null)) payload.tenant = tenant;
      if (password.trim()) payload.password = password;
      // Always send permissions if changed
      const permChanged = JSON.stringify(permissions) !== JSON.stringify(user.permissions ?? null);
      if (permChanged) payload.permissions = permissions;

      if (Object.keys(payload).length === 0) {
        onClose();
        return;
      }
      await api.updateUser(user.id, payload);
      onSaved();
    } catch (err) {
      onError(err.message || "Error al actualizar usuario");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Editar usuario</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
        </div>

        <p className="text-xs text-gray-400 mb-4">ID #{user.id}</p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Correo</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="correo@dominio.com" required />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Nombre completo</label>
            <input value={nombre} onChange={(e) => setNombre(e.target.value)} required
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Rol</label>
              <select value={role} onChange={(e) => {
                  const r = e.target.value;
                  setRole(r);
                  setPermissions(ROLE_PRESETS[r] ?? null);
                }}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                {Object.entries(ROLE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Estado</label>
              <select value={isActive ? "1" : "0"} onChange={(e) => setIsActive(e.target.value === "1")}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="1">Activo</option>
                <option value="0">Inactivo</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Institución</label>
            {isSuperAdmin ? (
            <select value={tenant ?? ""} onChange={(e) => setTenant(e.target.value || null)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-white focus:outline-none focus:ring-2 focus:ring-blue-500">
              <option value="">🌐 Global (todas)</option>
              {tenantOptions.map((c) => (
                <option key={c} value={c}>{c.toUpperCase()}</option>
              ))}
            </select>
            ) : (
              <input value={(actorTenant || "").toUpperCase()} disabled title="Tu institución"
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-100 text-gray-600" />
            )}
            <p className="text-[11px] text-gray-400 mt-1">
              Al iniciar sesión en kapak.yachaydeep.com el usuario será dirigido a su institución.
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Nueva contraseña <span className="text-gray-400 font-normal">(opcional, mín. 8 caracteres)</span>
            </label>
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
              placeholder="Dejar en blanco para no cambiar" minLength={password ? 8 : undefined}
              autoComplete="new-password"
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>

          {/* Permisos */}
          <div className="border-t border-gray-100 pt-3">
            <div className="flex items-center justify-between mb-2">
              <label className="block text-xs font-medium text-gray-700">Permisos de acceso</label>
              <button type="button" onClick={() => setPermissions(ROLE_PRESETS[role] ?? null)}
                className="text-[11px] text-blue-500 hover:text-blue-700 underline">
                Restaurar del rol
              </button>
            </div>
            <PermissionCheckboxes
              selected={permissions}
              onChange={setPermissions}
              compact
            />
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-gray-600 hover:bg-gray-100">
              Cancelar
            </button>
            <button type="submit" disabled={saving}
              className="bg-brand text-white rounded-lg px-4 py-2 text-sm font-semibold hover:bg-brand-light disabled:opacity-60">
              {saving ? "Guardando..." : "Guardar cambios"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// PÁGINA PRINCIPAL ADMIN
// ─────────────────────────────────────────────────────────────────────────────
export default function Admin() {
  const { tab: tabParam } = useParams();
  const navigate = useNavigate();
  const onKapak = isAdminHost();
  // En kapak (core) solo Usuarios y Seguridad; en instancias, todas las pestañas.
  const visibleTabs = onKapak ? TABS.filter(t => t === "Usuarios" || t === "Seguridad") : TABS;
  const _default = onKapak ? "usuarios" : "sistema";
  let activeTab = SLUG_TO_TAB[(tabParam || _default).toLowerCase()] || (onKapak ? "Usuarios" : "Sistema");
  if (!visibleTabs.includes(activeTab)) activeTab = visibleTabs[0];
  const setActiveTab = (t) => navigate(`/admin/${TAB_SLUGS[t] || _default}`);

  // Polling de progreso del scraping cada 15s
  useEffect(() => {
    let interval;
    const checkProgress = async () => {
      try {
        const prog = await api.getScrapingProgress();
        setScrapingProgress(prog);
        if (!prog.running && interval) {
          clearInterval(interval);
          interval = null;
        }
      } catch { /* ignore */ }
    };
    checkProgress();
    interval = setInterval(checkProgress, 15000);
    return () => { if (interval) clearInterval(interval); };
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">Administración</h1>

      {/* Tab bar */}
      <div className="flex gap-1 border-b border-gray-200">
        {visibleTabs.map(tab => (
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
      {activeTab === "Seguridad" && <Seguridad2FA />}
    </div>
  );
}
