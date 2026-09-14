import { createContext, useContext, useState, useCallback } from "react";
import api, { extractErrorMessage } from "../services/api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem("sifguard_token"));
  const [user, setUser] = useState(() => {
    const raw = localStorage.getItem("sifguard_user");
    return raw ? JSON.parse(raw) : null;
  });

  const login = useCallback(async (email, password) => {
    try {
      const resp = await api.post("/api/auth/login", { email, password });
      const { access_token, user: userData } = resp.data;
      localStorage.setItem("sifguard_token", access_token);
      localStorage.setItem("sifguard_user", JSON.stringify(userData));
      setToken(access_token);
      setUser(userData);
      return { success: true };
    } catch (err) {
      return { success: false, error: extractErrorMessage(err, "Login failed. Check your credentials.") };
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem("sifguard_token");
    localStorage.removeItem("sifguard_user");
    setToken(null);
    setUser(null);
  }, []);

  const hasRole = useCallback(
    (...roles) => !!user && roles.includes(user.role),
    [user]
  );

  return (
    <AuthContext.Provider value={{ token, user, login, logout, hasRole, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
