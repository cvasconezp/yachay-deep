import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { YachayLogo, YachayIcon } from "./YachayLogo";

const NAV_ITEMS = [
  { path: "/dashboard",      label: "Dashboard",        icon: "📊" },
  { path: "/ficha",          label: "Ficha Estudiante",  icon: "🎓" },
  { path: "/asignaturas",    label: "Asignaturas",       icon: "📚" },
  { path: "/docentes",       label: "Docentes",          icon: "👨‍🏫" },
  { path: "/tutorias",       label: "Tutorías",          icon: "📋" },
  { path: "/about",          label: "Sobre Yachay Deep",  icon: "ℹ️" },
];

const ADMIN_ITEMS = [
  { path: "/admin",          label: "Administración", icon: "⚙️" },
];

export function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Sidebar open/closed con persistencia en localStorage
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    const saved = localStorage.getItem("yd_sidebar");
    return saved !== null ? JSON.parse(saved) : true;
  });

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
        className={`${sidebarOpen ? "w-64" : "w-16"} bg-brand text-white flex flex-col shadow-xl transition-all duration-300 relative flex-shrink-0`}
      >
        {/* Botón toggle */}
        <button
          onClick={toggleSidebar}
          className="absolute -right-3 top-9 w-6 h-6 bg-brand border-2 border-white rounded-full flex items-center justify-center text-white text-xs hover:bg-brand-light transition-colors z-10 shadow-md"
          title={sidebarOpen ? "Ocultar panel" : "Mostrar panel"}
        >
          {sidebarOpen ? "«" : "»"}
        </button>

        {/* Header con logo */}
        <div className={`border-b border-white/10 ${sidebarOpen ? "p-5" : "p-3 flex items-center justify-center"}`}>
          {sidebarOpen ? (
            <div className="flex items-center gap-3">
              <YachayIcon size={36} />
              <div>
                <h1 className="text-lg font-bold tracking-tight leading-tight">Yachay Deep</h1>
                <p className="text-brand-ice text-xs">Monitoreo Académico</p>
              </div>
            </div>
          ) : (
            <YachayIcon size={28} />
          )}
        </div>

        {/* Navigation */}
        <nav className={`flex-1 ${sidebarOpen ? "p-4" : "p-2"} space-y-1`}>
          {navItems.map(item => (
            <Link
              key={item.path}
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
          ))}
        </nav>

        {/* User section */}
        <div className={`border-t border-white/10 ${sidebarOpen ? "p-4" : "p-2 flex flex-col items-center"}`}>
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

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6 max-w-7xl mx-auto">
          {children}
        </div>
      </main>
    </div>
  );
}
