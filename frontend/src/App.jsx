// frontend/src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { RotateOverlay } from "./components/RotateOverlay";
import { useLandscapeEnforcer } from "./hooks/useLandscapeEnforcer";
import { useIdleTimer } from "./hooks/useIdleTimer";
import IdleLockScreen from "./components/IdleLockScreen";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import FichaEstudiante from "./pages/FichaEstudiante";
import Asignaturas from "./pages/Asignaturas";
import Docentes from "./pages/Docentes";
import Tutorias from "./pages/Tutorias";
import Intervenciones from "./pages/Intervenciones";
import Alertas from "./pages/Alertas";
import ResumenDatos from "./pages/ResumenDatos";
import Admin from "./pages/Admin";
import About from "./pages/About";
import EntregasPendientes from "./pages/EntregasPendientes";
import { isSubdomain } from "./hooks/useTenant";
import TenantPortal from "./pages/TenantPortal";

function PrivateRoute({ children, adminOnly = false, tabKey = null }) {
  const { user, loading } = useAuth();

  // ← NUEVO: activa el enforcer solo cuando el usuario está autenticado
  const showOverlay = useLandscapeEnforcer(!!user);

  if (loading)
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400">
        Cargando...
      </div>
    );
  if (!user) return <Navigate to="/login" />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/dashboard" />;
  if (tabKey && user.permissions && !user.permissions.includes(tabKey)) {
    return <Navigate to="/dashboard" />;
  }

  return (
    <>
      {showOverlay && <RotateOverlay />}
      <Layout>{children}</Layout>
    </>
  );
}

/**
 * [SEC-03] Componente que maneja el idle lock a nivel de aplicación.
 * Solo activo cuando el usuario tiene PIN configurado (has_pin: true).
 */
function IdleLockManager() {
  const { user, locked, lock, unlock, logout } = useAuth();

  // Solo activar idle timer si el usuario tiene PIN configurado
  useIdleTimer({
    timeoutMs: 5 * 60 * 1000, // 5 minutos
    onIdle: lock,
    enabled: !!user && !!user.has_pin && !locked,
  });

  if (!locked || !user) return null;

  return (
    <IdleLockScreen
      onUnlock={unlock}
      onLogout={logout}
      userName={user.nombre}
    />
  );
}


/**
 * On root domain (yachaydeep.com), admin users see the tenant portal.
 * On subdomains, everyone sees the regular dashboard.
 */
function PortalOrDashboard() {
  const { user } = useAuth();
  if (!isSubdomain() && user?.role === "admin") {
    return <Navigate to="/instituciones" replace />;
  }
  return (
    <PrivateRoute tabKey="dashboard">
      <Dashboard />
    </PrivateRoute>
  );
}


/**
 * Auth-protected route WITHOUT sidebar/Layout.
 * Used for the admin portal which has its own header.
 */
function PortalRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading)
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-400">
        Cargando...
      </div>
    );
  if (!user) return <Navigate to="/login" />;
  if (user.role !== "admin") return <Navigate to="/dashboard" />;
  return children;
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <IdleLockManager />
          <Routes>
            <Route path="/" element={isSubdomain() ? <Navigate to="/login" replace /> : <Landing />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/instituciones"
              element={
                <PortalRoute>
                  <TenantPortal />
                </PortalRoute>
              }
            />
            <Route
              path="/dashboard"
              element={<PortalOrDashboard />}
            />
            <Route
              path="/ficha"
              element={
                <PrivateRoute tabKey="ficha">
                  <FichaEstudiante />
                </PrivateRoute>
              }
            />
            <Route
              path="/ficha/:studentId"
              element={
                <PrivateRoute>
                  <FichaEstudiante />
                </PrivateRoute>
              }
            />
            <Route
              path="/asignaturas"
              element={
                <PrivateRoute tabKey="asignaturas">
                  <Asignaturas />
                </PrivateRoute>
              }
            />
            <Route
              path="/docentes"
              element={
                <PrivateRoute tabKey="docentes">
                  <Docentes />
                </PrivateRoute>
              }
            />
            <Route
              path="/seguimiento-docente"
              element={<Navigate to="/docentes?tab=calificaciones" replace />}
            />
            <Route
              path="/tutorias"
              element={
                <PrivateRoute tabKey="tutorias">
                  <Tutorias />
                </PrivateRoute>
              }
            />
            <Route
              path="/intervenciones"
              element={
                <PrivateRoute tabKey="intervenciones">
                  <Intervenciones />
                </PrivateRoute>
              }
            />
            <Route
              path="/alertas"
              element={
                <PrivateRoute tabKey="alertas">
                  <Alertas />
                </PrivateRoute>
              }
            />
            <Route path="/mi-bandeja" element={<Navigate to="/alertas" replace />} />
            <Route
              path="/resumen"
              element={
                <PrivateRoute tabKey="resumen">
                  <ResumenDatos />
                </PrivateRoute>
              }
            />
            <Route
              path="/entregas"
              element={
                <PrivateRoute tabKey="entregas">
                  <EntregasPendientes />
                </PrivateRoute>
              }
            />
            <Route
              path="/about"
              element={
                <PrivateRoute tabKey="about">
                  <About />
                </PrivateRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <PrivateRoute adminOnly>
                  <Admin />
                </PrivateRoute>
              }
            />
            <Route path="*" element={<Navigate to={isSubdomain() ? "/login" : "/"} />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
