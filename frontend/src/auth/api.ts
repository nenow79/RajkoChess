import axios from "axios";

import { API_URL } from "../config";
import type { AuthUser, LoginCredentials, RegisterCredentials } from "./types";

interface LoginResponse {
  user: AuthUser;
  csrf_token: string;
}

interface CsrfResponse {
  csrf_token: string;
}

const authApi = axios.create({
  baseURL: `${API_URL}/auth`,
  withCredentials: true,
});

export const getCurrentUser = () =>
  authApi.get<AuthUser>("/me").then((response) => response.data);

export const loginUser = (credentials: LoginCredentials) =>
  authApi.post<LoginResponse>("/login", credentials).then((response) => response.data);

export const registerUser = ({ email, password, displayName }: RegisterCredentials) =>
  authApi.post<AuthUser>("/register", {
    email,
    password,
    display_name: displayName?.trim() || null,
  }).then((response) => response.data);

export const confirmEmail = (token: string) =>
  authApi.post<{ message: string }>("/email-verification/confirm", { token })
    .then((response) => response.data);

export const resendVerificationEmail = (email: string) =>
  authApi.post<{ message: string }>("/email-verification/resend", { email })
    .then((response) => response.data);

export const requestPasswordReset = (email: string) =>
  authApi.post<{ message: string }>("/password-reset/request", { email })
    .then((response) => response.data);

export const confirmPasswordReset = (token: string, password: string) =>
  authApi.post<{ message: string }>("/password-reset/confirm", { token, password })
    .then((response) => response.data);

export const getCsrfToken = () =>
  authApi.get<CsrfResponse>("/csrf").then((response) => response.data.csrf_token);

export const logoutUser = (csrfToken: string) =>
  authApi.post("/logout", null, {
    headers: { "X-CSRF-Token": csrfToken },
  });

export function getAuthErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;

  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const message = detail.find((item) => typeof item?.msg === "string")?.msg;
    if (message) return message.replace(/^Value error,\s*/, "");
  }
  if (!error.response) return "Nie udało się połączyć z serwerem.";
  return fallback;
}
