import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";

const NAV_ITEMS = [
  { path: "/dashboard",      label: "Dashboard",      icon: "📊" },
  { path: "/ficha",          label: "Ficha Estudiante", icon: "🎓" },
  { path: "/intervenciones", label: "Intervenciones", icon: "📋" },
];

const ADMIN_ITEMS = [
  { path: "/admin",          label: "Administración", icon: "⚙️" },
];

export function Layout({ children }) {
  const { user, logout, isAdmin } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const navItems = isAdmin ? [...NAV_ITEMS, ...ADMIN_ITEMS] : NAV_ITEMS;

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-64 bg-[#1B3A6B] text-white flex flex-col shadow-xl">
        <div className="p-6 border-b border-blue-800">
          <h1 className="text-xl font-bold tracking-tight">Yachay Deep</h1>
          <p className="text-blue-300 text-xs mt-1">Monitoreo Académico</p>
        </div>

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map(item => (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${location.pathname.startsWith(item.path)
                  ? "bg-blue-600 text-white"
                  : "text-blue-200 hover:bg-blue-800 hover:text-white"}`}
            >
              <span>{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="p-4 border-t border-blue-800">
          <div className="text-sm text-blue-300 mb-2">
            <div className="font-medium text-white truncate">{user?.nombre}</div>
            <div className="text-xs capitalize">{user?.role}</div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full text-left text-xs text-blue-400 hover:text-white transition-colors"
          >
            Cerrar sesión
          </button>
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
