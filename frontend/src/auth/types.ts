export interface AuthUser {
  id: string;
  email: string;
  display_name: string | null;
  status: "active" | "blocked" | "deleted";
  system_role: "user" | "admin";
  email_verified: boolean;
  created_at: string;
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials extends LoginCredentials {
  displayName?: string;
}

export type AuthStatus = "loading" | "authenticated" | "anonymous";

export interface ChessPlatformAccount {
  provider: string;
  username: string;
  updated_at: string;
}
