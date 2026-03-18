/**
 * Hook de autenticación para Yachay Deep.
 *
 * REMEDIACIÓN:
 *   [BUG-01] Race condition resuelta: storage event + verificación periódica JWT
 *   [SEC-02] Fase 1: verificación local de expiración del token
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { api } from "../services/api";

const AuthContext = createContext(null);
const TOKEN_KEY = "yd_token";
const TOKEN_CHECK_MS = 60_000;

function decodeJwtPayload(token) {
  try {
    const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    return JSON.parse(atob(b64));
  } catch { return null; }
}

function isTokenExpired(token) {
  const p = decodeJwtPayload(token);
  if (!p || !p.exp) return true;
  return Date.now() >= (p.exp * 1000) - 30_000;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef(null);

  // Cargar usuario al montar
  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token && !isTokenExpired(token)) {
      api.me()
        .then(setUser)
        .catch(() => { localStorage.removeItem(TOKEN_KEY); setUser(null); })
        .finally(() => setLoading(false));
    } else {
      if (token) localStorage.removeItem(TOKEN_KEY);
      setLoading(false);
    }
  }, []);

  // [BUG-01] FIX: Verificación periódica de expiración
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      const token = localStorage.getItem(TOKEN_KEY);
      if (!token || isTokenExpired(token)) {
        localStorage.removeItem(TOKEN_KEY);
        setUser(null);
      }
    }, TOKEN_CHECK_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  // [BUG-01] FIX: Sincronización entre pestañas
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === TOKEN_KEY) {
        if (!e.newValue) { setUser(null); }
        else if (e.newValue !== e.oldValue) {
          api.me().then(setUser).catch(() => { localStorage.removeItem(TOKEN_KEY); setUser(null); });
        }
      }
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  // Listener 401 centralizado
  useEffect(() => {
    const onUnauth = () => { localStorage.removeItem(TOKEN_KEY); setUser(null); };
    window.addEventListener("yd:unauthorized", onUnauth);
    return () => window.removeEventListener("yd:unauthorized", onUnauth);
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api.login(email, password);
    localStorage.setItem(TOKEN_KEY, data.access_token);
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin: user?.role === "admin" }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
