import { createContext } from "react";

import type { AuthStatus, AuthUser, ChessPlatformAccount, LoginCredentials, RegisterCredentials } from "./types";

export interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  platformAccounts: ChessPlatformAccount[];
  refreshPlatformAccounts: () => Promise<void>;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
