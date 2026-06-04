import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { YachayLogo } from "../components/YachayLogo";
import { isSubdomain, isAdminHost } from "../hooks/useTenant";

/**
 * Destino tras iniciar sesión (login centralizado):
 * - En kapak/dominio raíz: admin → panel KAPAK; usuario con institución →
 *   su subdominio (la cookie de sesión es válida en *.yachaydeep.com).
 * - En un subdominio de institución: dashboard normal.
 */
function goAfterLogin(u, navigate) {
  if (!isSubdomain()) {
    if (u?.role === "admin") {
      navigate(isAdminHost() ? "/" : "/core/kapak", { replace: true });
      return;
    }
    if (u?.tenant) {
      window.location.href = `https://${u.tenant}.yachaydeep.com/dashboard`;
      return;
    }
  }
  navigate("/dashboard", { replace: true });
}

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login, user, loading: authLoading } = useAuth();
  const navigate = useNavigate();

  // [SESSION-UX] If the user already has a valid session (HttpOnly cookie),
  // skip the login form entirely and send them straight to the dashboard.
  // This prevents the "ghost logout" effect when navigating to /login from
  // the public landing while already authenticated.
  useEffect(() => {
    if (!authLoading && user) {
      goAfterLogin(user, navigate);
    }
  }, [authLoading, user, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const u = await login(email, password);
      goAfterLogin(u, navigate);
    } catch (err) {
      setError(err.message || "Credenciales incorrectas");
    } finally {
      setLoading(false);
    }
  };

  // While the auth provider is resolving session state, or while we
  // already know there's a session and we're about to redirect, render
  // nothing (avoids a flash of the login form).
  if (authLoading || user) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center p-4">
        <div className="text-white/80 text-sm">Cargando…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-brand to-brand-dark flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8">
        <div className="text-center mb-8">
          <a href="https://yachaydeep.com" className="flex justify-center mb-5">
            {/* Login card bg is white → CLARO renders natively without a wrapper.
                Logo scales with the card / viewport. */}
            <YachayLogo
              variant="light"
              className="block w-[min(80%,20rem)] sm:w-[min(80%,22rem)] h-auto"
            />
          </a>
          <h1 className="sr-only">Yachay Deep</h1>
          <p className="text-gray-500 mt-2 text-sm">Sistema de Monitoreo Académico</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold"
              placeholder="usuario@yachaydeep.org"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Contraseña</label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-gold"
              placeholder="••••••••"
              required
            />
          </div>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-brand-gold text-brand-dark rounded-lg py-3 font-semibold text-sm hover:bg-brand-gold-light transition-colors disabled:opacity-60"
          >
            {loading ? "Ingresando..." : "Ingresar"}
          </button>
        </form>

        <p className="text-center text-xs text-gray-400 mt-6">
          Yachay Deep &copy; 2026
        </p>
      </div>
    </div>
  );
}
