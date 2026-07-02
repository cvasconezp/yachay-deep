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
import { isAdminHost } from "./useTenant";

const AuthContext = createContext(null);
const SESSION_CHECK_MS = 120_000; // verificar sesión cada 2 min

// [AUDIT] Presets de permisos por rol (deben coincidir con Admin.jsx ROLE_PRESETS)
const ROLE_PRESETS = {
  admin: null,
  coordinador: ["dashboard","alertas","intervenciones","ficha","asignaturas","entregas","docentes","tutorias","resumen"],
  docente: ["dashboard","ficha","asignaturas","entregas","docentes"],
  monitor: ["dashboard","alertas","intervenciones","ficha","asignaturas","entregas","tutorias"],
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [locked, setLocked] = useState(false);
  const [viewAsRole, setViewAsRoleState] = useState(() => sessionStorage.getItem("yd_view_as") || null);
  const pendingViewAsRef = useRef(typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("view_as") : null);
  const intervalRef = useRef(null);

  // Cargar usuario al montar (la cookie HttpOnly se envía automáticamente)
  useEffect(() => {
    api.me()
      .then((u) => { setUser(u); if (u?.locked) setLocked(true); })  // [SEC-03] re-bloquear tras reload
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
    const onLocked = () => setLocked(true);  // [SEC-03] 423 desde el API
    window.addEventListener("yd:locked", onLocked);
    return () => {
      window.removeEventListener("yd:unauthorized", onUnauth);
      window.removeEventListener("yd:locked", onLocked);
    };
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
    sessionStorage.removeItem("yd_view_as");
    setViewAsRoleState(null);
  }, []);

  // [SEC-03] Idle lock
  const lock = useCallback(() => {
    if (user?.has_pin) {
      api.lock().catch(() => {});  // [SEC-03] bloquear server-side; el 423 protege aunque falle la UI
      setLocked(true);
    }
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

  // [AUDIT] Ver como rol (solo super-admin). null = vista real.
  const setViewAsRole = useCallback((role) => {
    if (role && !user?.is_super_admin) return;
    if (role) sessionStorage.setItem("yd_view_as", role);
    else sessionStorage.removeItem("yd_view_as");
    setViewAsRoleState(role || null);
  }, [user]);

  const realSuper = !!user?.is_super_admin;
  const previewing = !!(viewAsRole && realSuper && !isAdminHost());
  const effUser = previewing
    ? { ...user, role: viewAsRole, permissions: ROLE_PRESETS[viewAsRole] ?? null }
    : user;
  const isReadOnly = previewing && viewAsRole === "docente";

  useEffect(() => { api.setPreviewReadOnly && api.setPreviewReadOnly(isReadOnly); }, [isReadOnly]);

  // [AUDIT] Aplicar ?view_as=<rol> al entrar desde el portal (cross-subdominio)
  useEffect(() => {
    const role = pendingViewAsRef.current;
    if (role && user?.is_super_admin) {
      pendingViewAsRef.current = null;
      if (["monitor", "docente", "coordinador"].includes(role)) {
        sessionStorage.setItem("yd_view_as", role);
        setViewAsRoleState(role);
      }
      try {
        const u = new URL(window.location.href); u.searchParams.delete("view_as");
        window.history.replaceState({}, "", u.toString());
      } catch { /* ignore */ }
    }
  }, [user]);

  return (
    <AuthContext.Provider value={{
      user: effUser, realUser: user, loading, login, logout,
      isAdmin: effUser?.role === "admin",
      isSuperAdmin: previewing ? false : realSuper,
      realIsSuperAdmin: realSuper,
      mustEnroll2FA: !!user?.must_enroll_2fa,
      viewAsRole, setViewAsRole, previewing, isReadOnly,
      locked, lock, unlock, refreshUser,
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
