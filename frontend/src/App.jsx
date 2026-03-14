import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { Layout } from "./components/Layout";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import FichaEstudiante from "./pages/FichaEstudiante";
import Asignaturas from "./pages/Asignaturas";
import Docentes from "./pages/Docentes";
import Tutorias from "./pages/Tutorias";
import Admin from "./pages/Admin";
import About from "./pages/About";

function PrivateRoute({ children, adminOnly = false }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Cargando...</div>;
  if (!user) return <Navigate to="/login" />;
  if (adminOnly && user.role !== "admin") return <Navigate to="/dashboard" />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/dashboard" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/ficha" element={<PrivateRoute><FichaEstudiante /></PrivateRoute>} />
          <Route path="/ficha/:studentId" element={<PrivateRoute><FichaEstudiante /></PrivateRoute>} />
          <Route path="/asignaturas" element={<PrivateRoute><Asignaturas /></PrivateRoute>} />
          <Route path="/docentes" element={<PrivateRoute><Docentes /></PrivateRoute>} />
          <Route path="/tutorias" element={<PrivateRoute><Tutorias /></PrivateRoute>} />
          <Route path="/about" element={<PrivateRoute><About /></PrivateRoute>} />
          <Route path="/admin" element={<PrivateRoute adminOnly><Admin /></PrivateRoute>} />
          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
