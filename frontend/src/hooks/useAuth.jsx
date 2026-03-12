import { createContext, useContext, useState, useEffect } from "react";
import { api } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("yd_token");
    if (token) {
      api.me()
        .then(setUser)
        .catch(() => localStorage.removeItem("yd_token"))
        .finally(() => setLoading(false));
    } else {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => {
      if (!localStorage.getItem("yd_token")) {
        setUser(null);
      }
    };
    window.addEventListener("yd:unauthorized", handleUnauthorized);
    return () => window.removeEventListener("yd:unauthorized", handleUnauthorized);
  }, []);

  const login = async (email, password) => {
    const data = await api.login(email, password);
    localStorage.setItem("yd_token", data.access_token);
    setUser(data.user);
    return data.user;
  };

  const logout = () => {
    localStorage.removeItem("yd_token");
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, isAdmin: user?.role === "admin" }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
