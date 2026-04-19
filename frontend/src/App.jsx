// frontend/src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { Layout } from "./components/Layout";
import { RotateOverlay } from "./components/RotateOverlay";      // ← NUEVO
import { useLandscapeEnforcer } from "./hooks/useLandscapeEnforcer"; // ← NUEVO
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

function PrivateRoute({ children, adminOnly = false }) {
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

  return (
    <>
      {showOverlay && <RotateOverlay />}  {/* ← NUEVO: overlay de rotación */}
      <Layout>{children}</Layout>
    </>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route
              path="/dashboard"
              element={
                <PrivateRoute>
                  <Dashboard />
                </PrivateRoute>
              }
            />
            <Route
              path="/ficha"
              element={
                <PrivateRoute>
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
                <PrivateRoute>
                  <Asignaturas />
                </PrivateRoute>
              }
            />
            <Route
              path="/docentes"
              element={
                <PrivateRoute>
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
                <PrivateRoute>
                  <Tutorias />
                </PrivateRoute>
              }
            />
            <Route
              path="/intervenciones"
              element={
                <PrivateRoute>
                  <Intervenciones />
                </PrivateRoute>
              }
            />
            <Route
              path="/alertas"
              element={
                <PrivateRoute>
                  <Alertas />
                </PrivateRoute>
              }
            />
            <Route
              path="/resumen"
              element={
                <PrivateRoute>
                  <ResumenDatos />
                </PrivateRoute>
              }
            />
            <Route
              path="/entregas"
              element={
                <PrivateRoute>
                  <EntregasPendientes />
                </PrivateRoute>
              }
            />
            <Route
              path="/about"
              element={
                <PrivateRoute>
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
            <Route path="*" element={<Navigate to="/" />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ErrorBoundary>
  );
}
