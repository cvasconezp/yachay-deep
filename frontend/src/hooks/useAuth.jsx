/**
 * Hook de autenticación para Yachay Deep.
 *
 * [SEC-02] Fase 2: HttpOnly cookies — el token ya NO se guarda en localStorage.
 * El backend setea una cookie HttpOnly en /auth/login y la borra en /auth/logout.
 * El frontend solo necesita enviar credentials: "include" en cada fetch.
 *
 * [BUG-01] Race condition resuelta: polling periódico de /auth/me.
 * [SEC-03] Idle lock: bloqueo por inactividad con PIN de 6 dígitos.
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { api } from "../services/api";

const AuthContext = createContext(null);
const SESSION_CHECK_MS = 120_000; // verificar sesión cada 2 min

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const intervalRef = useRef(null);

  // Cargar usuario al montar (la cookie HttpOnly se envía automáticamente)
  useEffect(() => {
    api.me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  // [BUG-01] FIX: Verificación periódica de sesión via /auth/me
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      api.me().catch(() => setUser(null));
    }, SESSION_CHECK_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  // Listener para 401 centralizado (interceptor en api.js)
  useEffect(() => {
    const onUnauth = () => { setUser(null); setLocked(false); };
    window.addEventListener("yd:unauthorized", onUnauth);
    return () => window.removeEventListener("yd:unauthorized", onUnauth);
  }, []);

  const login = useCallback(async (email, password, code = null) => {
    const data = await api.login(email, password, code);
    setUser(data.user);
    setLocked(false);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {
      // Si falla, igual limpiar estado local
    }
    setUser(null);
    setLocked(false);
  }, []);

  // [SEC-03] Idle lock
  const lock = useCallback(() => {
    if (user?.has_pin) setLocked(true);
  }, [user]);

  const unlock = useCallback(() => {
    setLocked(false);
  }, []);

  // Actualizar user tras cambiar PIN (para refrescar has_pin)
  const refreshUser = useCallback(async () => {
    try {
      const u = await api.me();
      setUser(u);
    } catch { /* ignore */ }
  }, []);

  return (
    <AuthContext.Provider value={{
      user, loading, login, logout, isAdmin: user?.role === "admin",
      isSuperAdmin: !!user?.is_super_admin, mustEnroll2FA: !!user?.must_enroll_2fa,
      locked, lock, unlock, refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
