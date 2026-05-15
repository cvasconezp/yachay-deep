/**
 * NotificationBell — campana de notificaciones in-app (Épica 2.2).
 *
 * Muestra un ícono de campana con badge de conteo. Al hacer clic,
 * despliega un panel con las últimas alertas no leídas usando un portal
 * para evitar que el overflow del sidebar lo recorte.
 */
import { useState, useEffect, useRef, useCallback } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { api } from "../services/api";

const SEVERITY_STYLES = {
  critico: { bg: "bg-red-50", border: "border-red-200", dot: "bg-red-500", text: "text-red-700", label: "Crítico" },
  alto:    { bg: "bg-orange-50", border: "border-orange-200", dot: "bg-orange-500", text: "text-orange-700", label: "Alto" },
  medio:   { bg: "bg-yellow-50", border: "border-yellow-200", dot: "bg-yellow-500", text: "text-yellow-700", label: "Medio" },
};

const TIPO_ICONS = {
  inactividad: "🔕",
  compromiso_bajo: "📉",
  nota_cero: "0️⃣",
  tareas_bajas: "📝",
  segunda_matricula: "2️⃣",
  tercera_matricula: "3️⃣",
  deterioro_progresivo: "📊",
};

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "ahora";
  if (mins < 60) return `hace ${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `hace ${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `hace ${days}d`;
}

export default function NotificationBell({ alertCount, criticoCount }) {
  const [open, setOpen] = useState(false);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [panelPos, setPanelPos] = useState({ top: 0, left: 0 });
  const bellRef = useRef(null);
  const panelRef = useRef(null);
  const navigate = useNavigate();

  // Calcular posición del panel relativo al botón de campana
  const updatePosition = useCallback(() => {
    if (!bellRef.current) return;
    const rect = bellRef.current.getBoundingClientRect();
    // Panel de 320px de ancho, 460px max alto — abrir a la derecha y hacia arriba
    const panelH = Math.min(460, window.innerHeight - 40);
    setPanelPos({
      top: Math.max(10, rect.top - panelH + rect.height),
      left: rect.right + 12,
      maxHeight: panelH,
    });
  }, []);

  // Cerrar al hacer clic fuera
  useEffect(() => {
    if (!open) return;
    const handler = (e) => {
      if (
        panelRef.current && !panelRef.current.contains(e.target) &&
        bellRef.current && !bellRef.current.contains(e.target)
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    window.addEventListener("resize", updatePosition);
    return () => {
      document.removeEventListener("mousedown", handler);
      window.removeEventListener("resize", updatePosition);
    };
  }, [open, updatePosition]);

  // Cargar alertas y posicionar al abrir
  useEffect(() => {
    if (!open) return;
    updatePosition();
    setLoading(true);
    api.getAlertsPending({ limit: 15 })
      .then(data => setAlerts(Array.isArray(data) ? data : []))
      .catch(() => setAlerts([]))
      .finally(() => setLoading(false));
  }, [open, updatePosition]);

  const handleMarkRead = async (e, alertId) => {
    e.stopPropagation();
    try {
      await api.markAlertRead(alertId);
      setAlerts(prev => prev.filter(a => a.id !== alertId));
    } catch { /* silently fail */ }
  };

  const handleClickAlert = (alert) => {
    if (alert.student_id) {
      navigate(`/ficha/${alert.student_id}`);
      setOpen(false);
    }
  };

  const handleViewAll = () => {
    navigate("/alertas");
    setOpen(false);
  };

  const total = alertCount || 0;

  const panel = open ? createPortal(
    <div
      ref={panelRef}
      className="fixed w-80 bg-white rounded-xl shadow-2xl border border-gray-200 z-[9999] overflow-hidden"
      style={{ top: panelPos.top, left: panelPos.left, maxHeight: panelPos.maxHeight || 460 }}
    >
      {/* Header */}
      <div className="bg-[#1B3A6B] text-white px-4 py-2.5 flex items-center justify-between">
        <span className="text-sm font-semibold">Notificaciones</span>
        {total > 0 && (
          <span className="text-[10px] bg-white/20 px-2 py-0.5 rounded-full">
            {total} pendientes
          </span>
        )}
      </div>

      {/* Contenido */}
      <div className="overflow-y-auto" style={{ maxHeight: (panelPos.maxHeight || 460) - 90 }}>
        {loading ? (
          <div className="py-8 text-center text-sm text-gray-400">Cargando...</div>
        ) : alerts.length === 0 ? (
          <div className="py-8 text-center">
            <div className="text-2xl mb-1">✅</div>
            <div className="text-sm text-gray-400">Sin alertas pendientes</div>
          </div>
        ) : (
          <div className="divide-y divide-gray-100">
            {alerts.map(alert => {
              const sev = SEVERITY_STYLES[alert.severidad] || SEVERITY_STYLES.medio;
              const icon = TIPO_ICONS[alert.tipo] || "⚠️";
              return (
                <div
                  key={alert.id}
                  onClick={() => handleClickAlert(alert)}
                  className={`px-3 py-2.5 ${sev.bg} hover:brightness-95 cursor-pointer transition-all flex gap-2.5 items-start`}
                >
                  <span className="text-base mt-0.5 flex-shrink-0">{icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1.5 mb-0.5">
                      <span className={`w-1.5 h-1.5 rounded-full ${sev.dot} flex-shrink-0`} />
                      <span className={`text-[10px] font-semibold uppercase ${sev.text}`}>{sev.label}</span>
                      <span className="text-[10px] text-gray-400 ml-auto flex-shrink-0">{timeAgo(alert.created_at)}</span>
                    </div>
                    {alert.student_nombre && (
                      <div className="text-xs font-semibold text-gray-800 truncate">{alert.student_nombre}</div>
                    )}
                    <div className="text-[11px] text-gray-600 leading-snug line-clamp-2">{alert.mensaje}</div>
                  </div>
                  <button
                    onClick={(e) => handleMarkRead(e, alert.id)}
                    className="flex-shrink-0 mt-1 p-1 rounded hover:bg-white/60 text-gray-400 hover:text-green-600 transition-colors"
                    title="Marcar como leída"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </button>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="border-t border-gray-200 bg-gray-50 px-4 py-2 text-center">
        <button
          onClick={handleViewAll}
          className="text-xs font-medium text-blue-600 hover:text-blue-800 transition-colors"
        >
          Ver todas las alertas →
        </button>
      </div>
    </div>,
    document.body
  ) : null;

  return (
    <div className="relative">
      {/* Campana */}
      <button
        ref={bellRef}
        onClick={() => setOpen(!open)}
        className="relative p-2 rounded-lg hover:bg-white/10 transition-colors group"
        title={`${total} alertas pendientes`}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-blue-200 group-hover:text-white transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {/* Badge */}
        {total > 0 && (
          <span className={`absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] rounded-full flex items-center justify-center text-[10px] font-bold text-white px-1 ${
            criticoCount > 0 ? "bg-red-500 animate-pulse" : "bg-orange-500"
          }`}>
            {total > 99 ? "99+" : total}
          </span>
        )}
      </button>

      {panel}
    </div>
  );
}
