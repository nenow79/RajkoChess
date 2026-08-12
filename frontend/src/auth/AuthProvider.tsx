import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import axios from "axios";

import { AuthContext, type AuthContextValue } from "./AuthContext";
import { getCsrfToken, getCurrentUser, loginUser, logoutUser, registerUser } from "./api";
import type { AuthStatus, AuthUser, LoginCredentials, RegisterCredentials } from "./types";

interface AuthProviderProps {
  children: ReactNode;
}

export default function AuthProvider({ children }: AuthProviderProps) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    getCurrentUser()
      .then(async (currentUser) => {
        const restoredCsrfToken = await getCsrfToken();
        if (!active) return;
        axios.defaults.headers.common["X-CSRF-Token"] = restoredCsrfToken;
        setUser(currentUser);
        setCsrfToken(restoredCsrfToken);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (!axios.isAxiosError(error) || error.response?.status !== 401) {
          console.error("Nie udało się odtworzyć sesji użytkownika:", error);
        }
        setUser(null);
        setStatus("anonymous");
      });

    return () => { active = false; };
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const result = await loginUser(credentials);
    axios.defaults.headers.common["X-CSRF-Token"] = result.csrf_token;
    setUser(result.user);
    setCsrfToken(result.csrf_token);
    setStatus("authenticated");
  }, []);

  const register = useCallback(async (credentials: RegisterCredentials) => {
    await registerUser(credentials);
  }, []);

  const logout = useCallback(async () => {
    const token = csrfToken || await getCsrfToken();
    await logoutUser(token);
    delete axios.defaults.headers.common["X-CSRF-Token"];
    setUser(null);
    setCsrfToken(null);
    setStatus("anonymous");
  }, [csrfToken]);

  const value = useMemo<AuthContextValue>(() => ({
    status,
    user,
    login,
    register,
    logout,
  }), [status, user, login, register, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
