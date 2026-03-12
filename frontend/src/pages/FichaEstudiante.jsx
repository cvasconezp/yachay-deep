import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../services/api";
import { RiskBadge } from "../components/RiskBadge";
import InterventionForm from "./InterventionForm";

// ── Gauge circular de compromiso ─────────────────────────────────────────────
function CompromisoGauge({ valor = 0, size = 96 }) {
  const r = size * 0.39;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, valor || 0));
  const dash = circ * pct;
  const color = pct < 0.3 ? "#ef4444" : pct < 0.6 ? "#f97316" : "#22c55e";
  const label = pct < 0.3 ? "Bajo" : pct < 0.6 ? "Medio" : "Alto";

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#e5e7eb" strokeWidth="7" />
        <circle
          cx={cx} cy={cy} r={r} fill="none"
          stroke={color} strokeWidth="7"
          strokeDasharray={`${dash} ${circ - dash}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${cx} ${cy})`}
        />
        <text x={cx} y={cy - 5} textAnchor="middle" fill="#111827" fontSize={size * 0.16} fontWeight="bold">
          {Math.round(pct * 100)}%
        </text>
        <text x={cx} y={cy + 10} textAnchor="middle" fill="#6b7280" fontSize={size * 0.095}>
          compromiso
        </text>
      </svg>
      <span className="text-xs font-semibold" style={{ color }}>{label}</span>
    </div>
  );
}

// ── Card pequeña de indicador ─────────────────────────────────────────────────
function KpiCard({ label, value, sub, highlight, className = "" }) {
  return (
    <div className={`rounded-lg p-3 ${highlight ? "bg-red-50 border border-red-100" : "bg-gray-50"} ${className}`}>
      <div className="text-xs text-gray-500 font-medium mb-0.5">{label}</div>
      <div className={`text-lg font-bold leading-tight ${highlight ? "text-red-700" : "text-gray-800"}`}>{value}</div>
      {sub && <div className="text-xs text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Fila de dato personal ─────────────────────────────────────────────────────
function DataRow({ icon, label, value, href }) {
  if (!value) return null;
  return (
    <div className="flex items-start gap-2 text-sm py-1.5 border-b border-gray-50 last:border-0">
      <span className="w-4 text-base flex-shrink-0">{icon}</span>
      <div className="min-w-0">
        <span className="text-gray-400 text-xs block">{label}</span>
        {href
          ? <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline break-all">{value}</a>
          : <span className="text-gray-800 break-all">{value}</span>
        }
      </div>
    </div>
  );
}

// ── Proyección académica ──────────────────────────────────────────────────────
function ProyeccionCard({ nivel_riesgo, dias_sin_acceso, porcentaje_tareas }) {
  const config = {
    Alto:  { label: "Riesgo de Deserción",   bg: "bg-red-50",    border: "border-red-200",    text: "text-red-800",    dot: "🔴" },
    Medio: { label: "Riesgo Moderado",        bg: "bg-orange-50", border: "border-orange-200", text: "text-orange-800", dot: "🟡" },
    Bajo:  { label: "Sin Riesgo Inmediato",   bg: "bg-green-50",  border: "border-green-200",  text: "text-green-800",  dot: "🟢" },
  };
  const c = config[nivel_riesgo] || { label: "Sin evaluar", bg: "bg-gray-50", border: "border-gray-200", text: "text-gray-600", dot: "⚪" };

  return (
    <div className={`rounded-xl border p-4 ${c.bg} ${c.border}`}>
      <div className={`text-xs font-semibold uppercase tracking-wide mb-1 opacity-60 ${c.text}`}>Proyección Académica</div>
      <div className={`flex items-center gap-1.5 font-bold text-sm ${c.text}`}>
        <span>{c.dot}</span>
        <span>{c.label}</span>
      </div>
      <div className={`mt-2 text-xs opacity-70 space-y-0.5 ${c.text}`}>
        {dias_sin_acceso != null && <div>• {dias_sin_acceso}d sin acceder a AVAC</div>}
        {porcentaje_tareas != null && <div>• {Math.round(porcentaje_tareas)}% tareas entregadas</div>}
      </div>
    </div>
  );
}

// ── Tabla de accesos AVAC por curso ───────────────────────────────────────────
function AvacCursoRow({ acceso, tareas }) {
  const entregadas = tareas.filter(t => t.entregada).length;
  const retrasadas = tareas.filter(t => t.retrasada).length;
  const total = tareas.length;
  const dias = acceso?.dias_sin_acceso;
  const diasInt = dias != null ? Math.round(dias) : null;
  const diasColor = diasInt == null ? "text-gray-400" : diasInt > 14 ? "text-red-600 font-semibold" : diasInt > 7 ? "text-orange-600" : "text-green-600";

  return (
    <div className="border border-gray-100 rounded-lg overflow-hidden">
      {/* Cabecera del curso */}
      <div className="bg-gray-50 px-4 py-2 flex items-center justify-between">
        <div>
          <span className="text-xs font-semibold text-gray-600 uppercase tracking-wide">Curso {acceso?.codigo_curso || tareas[0]?.codigo_curso}</span>
          {acceso?.estado_avac && (
            <span className="ml-2 text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">{acceso.estado_avac}</span>
          )}
        </div>
        <div className="flex items-center gap-4 text-xs">
          {acceso && (
            <span className={`flex items-center gap-1 ${diasColor}`}>
              🕐 {acceso.ultimo_acceso_texto || (diasInt != null ? `${diasInt} días` : "—")}
            </span>
          )}
          {total > 0 && (
            <span className="text-gray-500">
              {entregadas}/{total} tareas
              {retrasadas > 0 && <span className="text-red-500 ml-1">⚠️{retrasadas} retrasadas</span>}
            </span>
          )}
        </div>
      </div>

      {/* Tareas del curso */}
      {tareas.length > 0 && (
        <table className="w-full text-xs">
          <thead>
            <tr className="text-gray-400 border-b border-gray-100">
              <th className="text-left px-4 py-1.5 font-medium">Unidad</th>
              <th className="text-center px-3 py-1.5 font-medium">Entregada</th>
              <th className="text-center px-3 py-1.5 font-medium">Calificación</th>
              <th className="text-center px-3 py-1.5 font-medium">Retrasada</th>
              <th className="text-left px-3 py-1.5 font-medium max-w-[180px]">Estado</th>
            </tr>
          </thead>
          <tbody>
            {tareas.sort((a, b) => String(a.unidad).localeCompare(String(b.unidad))).map((t, i) => (
              <tr key={i} className={`border-t border-gray-50 ${t.retrasada ? "bg-red-50/40" : ""}`}>
                <td className="px-4 py-2 font-medium text-gray-700">Unidad {t.unidad}</td>
                <td className="px-3 py-2 text-center">{t.entregada ? "✅" : "❌"}</td>
                <td className="px-3 py-2 text-center font-mono text-gray-600">
                  {t.calificacion != null ? `${t.calificacion}/${t.calificacion_maxima ?? "?"}` : "—"}
                </td>
                <td className="px-3 py-2 text-center">{t.retrasada ? "⚠️" : "—"}</td>
                <td className="px-3 py-2 text-gray-400 max-w-[180px] truncate">
                  {(t.estado && t.estado !== "NaN" && t.estado !== "nan") ? t.estado : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ── Componente principal ───────────────────────────────────────────────────────
export default function FichaEstudiante() {
  const { studentId } = useParams();
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [ficha, setFicha] = useState(null);
  const [loading, setLoading] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const searchTimeout = useRef(null);

  useEffect(() => {
    if (studentId) loadFicha(studentId);
  }, [studentId]);

  const handleSearch = (value) => {
    setQuery(value);
    clearTimeout(searchTimeout.current);
    if (value.length < 2) { setSearchResults([]); return; }
    searchTimeout.current = setTimeout(async () => {
      try {
        const results = await api.searchStudents(value);
        setSearchResults(results);
      } catch (e) { console.error(e); }
    }, 300);
  };

  const loadFicha = async (id) => {
    setLoading(true);
    setSearchResults([]);
    try {
      const data = await api.getFicha(id);
      setFicha(data);
      setQuery(data.nombre || "");
      navigate(`/ficha/${id}`, { replace: true });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleExportPDF = async () => {
    if (!ficha) return;
    const blob = await api.exportFichaPDF(ficha.id);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ficha_${(ficha.nombre || ficha.id).toString().replace(/\s+/g, "_")}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Construir mapa de accesos y tareas por código de curso
  const cursos = {};
  if (ficha) {
    // Indexar accesos
    (ficha.accesos_avac || []).forEach(a => {
      if (!cursos[a.codigo_curso]) cursos[a.codigo_curso] = { acceso: null, tareas: [] };
      cursos[a.codigo_curso].acceso = a;
    });
    // Indexar tareas
    (ficha.tareas || []).forEach(t => {
      if (!cursos[t.codigo_curso]) cursos[t.codigo_curso] = { acceso: null, tareas: [] };
      cursos[t.codigo_curso].tareas.push(t);
    });
  }

  return (
    <div>
      {/* ── Título + buscador ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Ficha del Estudiante</h1>
          <p className="text-gray-400 text-sm">Carrera EIB — Monitoreo académico individual</p>
        </div>
      </div>

      <div className="relative mb-5">
        <input
          type="text"
          value={query}
          onChange={e => handleSearch(e.target.value)}
          placeholder="🔍 Buscar por nombre, correo o cédula..."
          className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 pr-10 bg-white shadow-sm"
        />
        {loading && <span className="absolute right-3 top-3.5 text-gray-400 text-sm">⏳</span>}
        {searchResults.length > 0 && (
          <div className="absolute z-10 w-full bg-white border border-gray-200 rounded-xl shadow-lg mt-1 max-h-64 overflow-y-auto">
            {searchResults.map(s => (
              <button
                key={s.id}
                onClick={() => loadFicha(s.id)}
                className="w-full text-left px-4 py-3 hover:bg-blue-50 flex items-center justify-between border-b border-gray-100 last:border-0"
              >
                <div>
                  <div className="font-medium text-gray-900 text-sm">{s.nombre || "Sin nombre"}</div>
                  <div className="text-xs text-gray-400">{s.correo_institucional} · {s.carrera || "EIB"}</div>
                </div>
                <RiskBadge nivel={s.nivel_riesgo} />
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Ficha completa ────────────────────────────────────────────── */}
      {ficha && (
        <div className="space-y-4">

          {/* === CABECERA === */}
          <div className="bg-[#1B3A6B] text-white rounded-xl px-6 py-4">
            <div className="flex items-start justify-between flex-wrap gap-3">
              <div>
                <div className="text-xs font-semibold uppercase tracking-widest opacity-60 mb-0.5">
                  Carrera EIB — Educación Intercultural Bilingüe [En Línea]
                </div>
                <h2 className="text-xl font-bold">{ficha.nombre || "—"}</h2>
                <div className="flex flex-wrap gap-4 mt-1 text-sm opacity-80">
                  {ficha.correo_institucional && <span>📧 {ficha.correo_institucional}</span>}
                  {ficha.cedula && <span>🪪 {ficha.cedula}</span>}
                  {ficha.telefono && <span>📱 {ficha.telefono}</span>}
                  {ficha.sede && <span>🏫 {ficha.sede}</span>}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleExportPDF}
                  className="bg-white/10 hover:bg-white/20 text-white px-3 py-2 rounded-lg text-xs font-medium transition-colors"
                >
                  📄 Exportar PDF
                </button>
                <button
                  onClick={() => setShowForm(true)}
                  className="bg-white text-[#1B3A6B] hover:bg-blue-50 px-3 py-2 rounded-lg text-xs font-semibold transition-colors"
                >
                  + Registrar intervención
                </button>
              </div>
            </div>
          </div>

          {/* === GRID PRINCIPAL: 3 columnas === */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

            {/* ─── COL 1: Datos personales ─── */}
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-3 pb-2 border-b border-gray-100">
                📋 Datos Personales
              </h3>
              <div className="space-y-0.5">
                <DataRow icon="📧" label="Correo institucional" value={ficha.correo_institucional} />
                <DataRow icon="📬" label="Correo personal" value={ficha.correo} />
                <DataRow icon="📱" label="Teléfono / WhatsApp" value={ficha.telefono}
                  href={ficha.telefono ? `https://wa.me/593${ficha.telefono.replace(/\D/g, "").replace(/^0/, "")}` : null}
                />
                <DataRow icon="🏫" label="Sede" value={ficha.sede} />
                <DataRow icon="📝" label="Estado matrícula" value={ficha.estado_matricula} />
              </div>

              {/* Sin datos visibles → mensaje */}
              {!ficha.correo && !ficha.telefono && !ficha.sede && (
                <p className="text-xs text-gray-400 mt-2 italic">
                  Datos adicionales no disponibles en AVAC.<br />
                  Disponible con integración al sistema académico.
                </p>
              )}

              <div className="mt-4 pt-3 border-t border-gray-100">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
                  🗺️ Lugar de Residencia
                </h3>
                <p className="text-xs text-gray-400 italic">Sin datos geográficos disponibles</p>
              </div>

              <div className="mt-4 pt-3 border-t border-gray-100">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">
                  💰 Datos Socioeconómicos
                </h3>
                <p className="text-xs text-gray-400 italic">Sin datos socioeconómicos disponibles</p>
              </div>
            </div>

            {/* ─── COL 2: Indicadores de riesgo ─── */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 flex flex-col gap-4">
              <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider pb-2 border-b border-gray-100">
                📊 Indicadores de Compromiso
              </h3>

              {/* Gauge circular */}
              <div className="flex justify-center">
                <CompromisoGauge valor={ficha.indice_compromiso} size={110} />
              </div>

              {/* KPIs */}
              <div className="grid grid-cols-2 gap-2">
                <KpiCard
                  label="Días sin AVAC"
                  value={ficha.dias_sin_acceso != null ? `${Math.round(ficha.dias_sin_acceso)}d` : "—"}
                  highlight={ficha.dias_sin_acceso > 14}
                  sub={ficha.dias_sin_acceso > 14 ? "⚠️ Inactividad alta" : null}
                />
                <KpiCard
                  label="Tareas entregadas"
                  value={ficha.porcentaje_tareas != null ? `${Math.round(ficha.porcentaje_tareas)}%` : "—"}
                  highlight={ficha.porcentaje_tareas != null && ficha.porcentaje_tareas < 50}
                />
                <div className="col-span-2">
                  <KpiCard
                    label="Nivel de Riesgo"
                    value={<RiskBadge nivel={ficha.nivel_riesgo} size="lg" />}
                  />
                </div>
              </div>

              {/* Proyección */}
              <ProyeccionCard
                nivel_riesgo={ficha.nivel_riesgo}
                dias_sin_acceso={ficha.dias_sin_acceso != null ? Math.round(ficha.dias_sin_acceso) : null}
                porcentaje_tareas={ficha.porcentaje_tareas}
              />
            </div>

            {/* ─── COL 3: Intervenciones ─── */}
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden flex flex-col">
              <div className="flex items-center justify-between px-4 py-3 border-b border-gray-100">
                <h3 className="text-xs font-bold text-gray-500 uppercase tracking-wider">
                  📞 Seguimiento ({ficha.total_intervenciones})
                </h3>
                <button
                  onClick={() => setShowForm(true)}
                  className="text-xs text-blue-600 hover:text-blue-800 font-medium"
                >
                  + Nueva
                </button>
              </div>

              <div className="flex-1 overflow-y-auto max-h-72">
                {ficha.intervenciones?.length === 0 ? (
                  <div className="text-center py-8">
                    <div className="text-3xl mb-2">📋</div>
                    <p className="text-xs text-gray-400">Sin intervenciones registradas</p>
                  </div>
                ) : (
                  <div className="divide-y divide-gray-50">
                    {ficha.intervenciones.map(inv => (
                      <div key={inv.id} className="px-4 py-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <div className="flex flex-wrap items-center gap-1 mb-1">
                              {inv.medio && (
                                <span className="inline-flex items-center bg-blue-100 text-blue-700 text-xs font-medium px-1.5 py-0.5 rounded-full">
                                  {inv.medio}
                                </span>
                              )}
                              {inv.motivo && (
                                <span className="text-xs text-gray-500 truncate">{inv.motivo}</span>
                              )}
                            </div>
                            {inv.observacion && (
                              <p className="text-xs text-gray-700 leading-relaxed">{inv.observacion}</p>
                            )}
                            <div className="flex flex-wrap gap-2 mt-1 text-xs text-gray-400">
                              {inv.estado && <span>Estado: <strong className="text-gray-600">{inv.estado}</strong></span>}
                              {inv.asignatura && <span>· {inv.asignatura}</span>}
                            </div>
                          </div>
                          <div className="text-right flex-shrink-0">
                            <div className="text-xs text-gray-400">
                              {inv.created_at ? new Date(inv.created_at).toLocaleDateString("es-EC") : ""}
                            </div>
                            {inv.monitor_nombre && (
                              <div className="text-xs text-gray-400 truncate max-w-[80px]">{inv.monitor_nombre}</div>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* === ACTIVIDAD AVAC Y TAREAS POR CURSO === */}
          {Object.keys(cursos).length > 0 && (
            <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
                <h3 className="font-semibold text-gray-800 text-sm">
                  📚 Actividad AVAC y Tareas por Curso ({Object.keys(cursos).length} cursos)
                </h3>
                <div className="text-xs text-gray-400">
                  {(ficha.tareas || []).filter(t => t.entregada).length} /
                  {(ficha.tareas || []).length} tareas entregadas
                </div>
              </div>
              <div className="p-4 space-y-3">
                {Object.entries(cursos).map(([codigo, { acceso, tareas: ts }]) => (
                  <AvacCursoRow key={codigo} acceso={acceso} tareas={ts} />
                ))}
              </div>
            </section>
          )}

          {/* === PRÁCTICAS PREPROFESIONALES === */}
          <section className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-800 text-sm mb-3 pb-2 border-b border-gray-100">
              🏫 Prácticas Preprofesionales
            </h3>
            <p className="text-xs text-gray-400 italic">
              Datos de prácticas no disponibles en la fuente actual (AVAC).
              Requiere integración con el sistema de prácticas institucional.
            </p>
          </section>

          {/* === CALIFICACIONES INSTITUCIONALES === */}
          {ficha.calificaciones?.length > 0 && (
            <section className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <h3 className="px-5 py-3 font-semibold text-gray-800 text-sm border-b border-gray-100">
                🎓 Calificaciones Institucionales ({ficha.calificaciones.length} asignaturas)
              </h3>
              <table className="w-full text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="text-left px-5 py-2.5 text-gray-500 font-medium text-xs">Asignatura</th>
                    <th className="text-left px-5 py-2.5 text-gray-500 font-medium text-xs">Docente</th>
                    <th className="text-left px-5 py-2.5 text-gray-500 font-medium text-xs">Grupo</th>
                    <th className="text-center px-5 py-2.5 text-gray-500 font-medium text-xs">Nota Final</th>
                  </tr>
                </thead>
                <tbody>
                  {ficha.calificaciones.map((g, i) => (
                    <tr key={i} className="border-t border-gray-100 hover:bg-gray-50">
                      <td className="px-5 py-2.5 font-medium text-gray-800">{g.asignatura}</td>
                      <td className="px-5 py-2.5 text-gray-500 text-xs">{g.docente || "—"}</td>
                      <td className="px-5 py-2.5 text-gray-400 text-xs">{g.grupo || "—"}</td>
                      <td className="px-5 py-2.5 text-center">
                        <span className={`font-bold ${(g.nota_final ?? 0) < 28 ? "text-red-600" : "text-green-600"}`}>
                          {g.nota_final ?? "—"}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

        </div>
      )}

      {/* Modal de intervención */}
      {showForm && ficha && (
        <InterventionForm
          student={ficha}
          onClose={() => setShowForm(false)}
          onSaved={() => { setShowForm(false); loadFicha(ficha.id); }}
        />
      )}
    </div>
  );
}
