import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { api } from "../services/api";
import { YachayLogo, YachayIcon } from "./YachayLogo";
import NotificationBell from "./NotificationBell";

const NAV_ITEMS = [
  { path: "/dashboard",      label: "Dashboard",        icon: "📊" },
  { path: "/ficha",          label: "Ficha Estudiante",  icon: "🎓" },
  { path: "/asignaturas",    label: "Asignaturas",       icon: "📚" },
  { path: "/docentes",       label: "Docentes",          icon: "👨‍🏫" },
  { path: "/tutorias",       label: "Tutorías",          icon: "📋" },
  { path: "/intervenciones", label: "Intervenciones",     icon: "🤝" },
  { path: "/alertas",        label: "Alertas",           icon: "🔔" },
  { path: "/entregas",       label: "Entregas",            icon: "📝" },
  { path: "/resumen",        label: "Resumen de Datos",   icon: "📈" },
  { path: "/about",          label: "Sobre Yachay Deep",  icon: "ℹ️" },
];

const ADMIN_ITEMS = [
  { path: "/admin",          label: "Administración", icon: "⚙️" },
];

export function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [alertCount, setAlertCount] = useState(null);
  const [alertAltoCount, setAlertAltoCount] = useState(0);

  // Sidebar open/closed con persistencia en localStorage
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem("yd_sidebar");
    return saved !== null ? JSON.parse(saved) : true;
  });

  // Load alert count on mount
  useEffect(() => {
    const loadAlertCount = async () => {
      try {
        const data = await api.getAlertCount();
        
        setAlertAltoCount(data.alto || 0);
        setAlertCount((data.alto || 0) + (data.medio || 0));
      } catch (e) {
        console.error("Error loading alert count:", e);
      }
    };
    loadAlertCount();
    // Refresh every 30 seconds
    const interval = setInterval(loadAlertCount, 30000);
    return () => clearInterval(interval);
  }, []);

  const toggleSidebar = () => {
    setSidebarOpen(prev => {
      const next = !prev;
      localStorage.setItem("yd_sidebar", JSON.stringify(next));
      return next;
    });
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const navItems = isAdmin ? [...NAV_ITEMS, ...ADMIN_ITEMS] : NAV_ITEMS;

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside
        className={`${sidebarOpen ? "w-64" : "w-16"} bg-brand text-white flex flex-col shadow-xl transition-all duration-300 flex-shrink-0 sticky top-0 h-screen overflow-y-auto overflow-x-hidden`}
      >
        {/* Header con logo — full-width white brand strip (edge-to-edge) in
            both expanded and collapsed states. The entire area is a link
            back to the public landing (/). */}
        <div className="border-b border-gray-200 bg-white">
          {sidebarOpen ? (
            <Link
              to="/"
              aria-label="Ir al inicio de Yachay Deep"
              className="block px-4 py-3.5 transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-inset"
            >
              <YachayLogo variant="light" className="w-full h-auto block" />
            </Link>
          ) : (
            <Link
              to="/"
              aria-label="Ir al inicio de Yachay Deep"
              className="block px-2 py-3 transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-gold focus-visible:ring-inset"
            >
              <YachayIcon className="w-full h-auto block" />
            </Link>
          )}
        </div>

        {/* Navigation */}
        <nav className={`flex-1 ${sidebarOpen ? "p-4" : "p-2"} space-y-1`}>
          {navItems.map(item => (
            <div key={item.path} className="relative">
              <Link
                to={item.path}
                title={!sidebarOpen ? item.label : undefined}
                className={`flex items-center ${sidebarOpen ? "gap-3 px-3" : "justify-center px-0"} py-2.5 rounded-lg text-sm font-medium transition-colors
                  ${location.pathname.startsWith(item.path)
                    ? "bg-brand-gold/90 text-brand-dark"
                    : "text-blue-200 hover:bg-white/10 hover:text-white"}`}
              >
                <span className={sidebarOpen ? "" : "text-lg"}>{item.icon}</span>
                {sidebarOpen && item.label}
              </Link>
              {/* Alert badge for Alertas item */}
              {item.path === "/alertas" && alertCount > 0 && (
                <div className={`absolute ${sidebarOpen ? "top-1 right-2" : "top-0 right-0"} w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold ${
                  alertAltoCount > 0 ? "bg-red-600" : "bg-orange-500"
                }`}>
                  {alertCount}
                </div>
              )}
            </div>
          ))}
        </nav>

        {/* Notification bell + User section */}
        <div className={`border-t border-white/10 ${sidebarOpen ? "p-4" : "p-2 flex flex-col items-center"}`}>
          {/* Campana de notificaciones (Épica 2.2) */}
          <div className={`mb-2 ${sidebarOpen ? "flex items-center justify-between" : "flex justify-center"}`}>
            <NotificationBell alertCount={alertCount} altoCount={alertAltoCount} />
            {sidebarOpen && alertCount > 0 && (
              <span className="text-[10px] text-blue-300">
                {alertAltoCount > 0 ? `${alertAltoCount} alto riesgo` : `${alertCount} alertas`}
              </span>
            )}
          </div>
          {sidebarOpen ? (
            <>
              <div className="text-sm text-blue-300 mb-2">
                <div className="font-medium text-white truncate">{user?.nombre}</div>
                <div className="text-xs capitalize text-brand-ice">{user?.role}</div>
              </div>
              <button
                onClick={handleLogout}
                className="w-full text-left text-xs text-blue-400 hover:text-white transition-colors"
              >
                Cerrar sesión
              </button>
            </>
          ) : (
            <button
              onClick={handleLogout}
              title={`${user?.nombre || "Usuario"} — Cerrar sesión`}
              className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center text-sm font-bold text-blue-200 hover:bg-white/20 hover:text-white transition-colors"
            >
              {user?.nombre?.charAt(0)?.toUpperCase() || "U"}
            </button>
          )}
        </div>
      </aside>

      {/* Botón toggle sidebar — fixed para que siempre sea visible al hacer scroll */}
      <button
        onClick={toggleSidebar}
        className="fixed z-30 w-7 h-7 bg-brand-gold text-brand-dark border-2 border-white rounded-full flex items-center justify-center hover:bg-brand-gold-light hover:scale-110 transition-all shadow-lg"
        style={{ top: "2.25rem", left: sidebarOpen ? "calc(16rem - 0.875rem)" : "calc(4rem - 0.875rem)", transition: "left 300ms" }}
        title={sidebarOpen ? "Ocultar panel" : "Mostrar panel"}
      >
        <svg xmlns="http://www.w3.org/2000/svg" className={`w-3.5 h-3.5 transition-transform ${sidebarOpen ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
      </button>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
