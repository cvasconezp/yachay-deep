/**
 * Hook de autenticación para Yachay Deep.
 *
 * [SEC-02] Fase 2: HttpOnly cookies — el token ya NO se guarda en localStorage.
 * El backend setea una cookie HttpOnly en /auth/login y la borra en /auth/logout.
 * El frontend solo necesita enviar credentials: "include" en cada fetch.
 *
 * [BUG-01] Race condition resuelta: polling periódico de /auth/me.
 */
import { createContext, useContext, useState, useEffect, useCallback, useRef } from "react";
import { api } from "../services/api";

const AuthContext = createContext(null);
const SESSION_CHECK_MS = 120_000; // verificar sesión cada 2 min

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const intervalRef = useRef(null);

  // Cargar usuario al montar (la cookie HttpOnly se envía automáticamente)
  useEffect(() => {
    api.me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  // [BUG-01] FIX: Verificación periódica de sesión via /auth/me
  // Con HttpOnly cookies no podemos leer el token localmente,
  // así que verificamos la sesión con un ping periódico al backend.
  useEffect(() => {
    intervalRef.current = setInterval(() => {
      api.me().catch(() => setUser(null));
    }, SESSION_CHECK_MS);
    return () => clearInterval(intervalRef.current);
  }, []);

  // Listener para 401 centralizado (interceptor en api.js)
  useEffect(() => {
    const onUnauth = () => setUser(null);
    window.addEventListener("yd:unauthorized", onUnauth);
    return () => window.removeEventListener("yd:unauthorized", onUnauth);
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await api.login(email, password);
    // El token viene en la HttpOnly cookie (set por el backend).
    // Solo guardamos el user del body de la respuesta.
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout(); // POST /auth/logout → borra cookie HttpOnly
    } catch {
      // Si falla, igual limpiar estado local
    }
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin: user?.role === "admin" }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
