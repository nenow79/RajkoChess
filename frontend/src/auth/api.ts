import axios from "axios";

import { API_URL } from "../config";
import type { AuthUser, ChessPlatformAccount, LoginCredentials, RegisterCredentials } from "./types";

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

export const getPlatformAccounts = () =>
  axios.get<{ accounts: ChessPlatformAccount[] }>(`${API_URL}/auth/platform-accounts`, {
    withCredentials: true,
  })
    .then((response) => response.data.accounts);

export const savePlatformAccount = (provider: string, username: string) =>
  axios.put<ChessPlatformAccount>(`${API_URL}/auth/platform-accounts/${provider}`, { username }, {
    withCredentials: true,
  })
    .then((response) => response.data);

export const deletePlatformAccount = (provider: string) =>
  axios.delete(`${API_URL}/auth/platform-accounts/${provider}`, {
    withCredentials: true,
  });

export const logoutUser = (csrfToken: string) =>
  authApi.post("/logout", null, {
    headers: { "X-CSRF-Token": csrfToken },
  });

export function getAuthErrorMessage(error: unknown, fallback: string): string {
  if (!axios.isAxiosError(error)) return fallback;

  const detail = error.response?.data?.detail;
  let message = fallback;
  if (typeof detail === "string") message = detail;
  if (Array.isArray(detail)) {
    const validationMessage = detail.find((item) => typeof item?.msg === "string")?.msg;
    if (validationMessage) message = validationMessage.replace(/^Value error,\s*/, "");
  }
  if (!error.response) return "Nie udało się połączyć z serwerem.";
  const retryAfter = error.response.headers["retry-after"];
  if (error.response.status === 429 && retryAfter) {
    return `${message} Spróbuj ponownie za ${retryAfter} s.`;
  }
  return message;
}
