import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import axios from "axios";

import { AuthContext, type AuthContextValue } from "./AuthContext";
import { getCsrfToken, getCurrentUser, getPlatformAccounts, loginUser, logoutUser, registerUser } from "./api";
import type { AuthStatus, AuthUser, ChessPlatformAccount, LoginCredentials, RegisterCredentials } from "./types";

interface AuthProviderProps {
  children: ReactNode;
}

export default function AuthProvider({ children }: AuthProviderProps) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [platformAccounts, setPlatformAccounts] = useState<ChessPlatformAccount[]>([]);

  useEffect(() => {
    let active = true;

    getCurrentUser()
      .then(async (currentUser) => {
        const [restoredCsrfToken, restoredAccounts] = await Promise.all([
          getCsrfToken(),
          getPlatformAccounts().catch(() => []),
        ]);
        if (!active) return;
        axios.defaults.headers.common["X-CSRF-Token"] = restoredCsrfToken;
        setUser(currentUser);
        setCsrfToken(restoredCsrfToken);
        setPlatformAccounts(restoredAccounts);
        setStatus("authenticated");
      })
      .catch((error: unknown) => {
        if (!active) return;
        if (!axios.isAxiosError(error) || error.response?.status !== 401) {
          console.error("Nie udało się odtworzyć sesji użytkownika:", error);
        }
        setUser(null);
        setPlatformAccounts([]);
        setStatus("anonymous");
      });

    return () => { active = false; };
  }, []);

  const login = useCallback(async (credentials: LoginCredentials) => {
    const result = await loginUser(credentials);
    axios.defaults.headers.common["X-CSRF-Token"] = result.csrf_token;
    setUser(result.user);
    setCsrfToken(result.csrf_token);
    setPlatformAccounts(await getPlatformAccounts().catch(() => []));
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
    setPlatformAccounts([]);
    setStatus("anonymous");
  }, [csrfToken]);

  const refreshPlatformAccounts = useCallback(async () => {
    setPlatformAccounts(await getPlatformAccounts());
  }, []);

  const value = useMemo<AuthContextValue>(() => ({
    status,
    user,
    platformAccounts,
    refreshPlatformAccounts,
    login,
    register,
    logout,
  }), [status, user, platformAccounts, refreshPlatformAccounts, login, register, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
