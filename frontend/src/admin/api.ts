import axios from "axios";

import { API_URL } from "../config";

export interface PlanSummary {
  key: "free" | "premium" | "admin";
  base_plan: "free" | "premium";
  expires_at: string | null;
  usage: Record<string, { used: number; limit: number | null }>;
  resource_limits: Record<string, number | null>;
}

export interface AdminUser {
  id: string;
  email: string;
  display_name: string | null;
  status: string;
  system_role: string;
  email_verified: boolean;
  created_at: string;
  plan_key: "free" | "premium";
  premium_expires_at: string | null;
  plan?: PlanSummary;
}

export interface AdminStatistics {
  generated_at: string;
  users: {
    total: number;
    verified: number;
    new_7d: number;
    new_30d: number;
    active_7d: number;
    active_30d: number;
  };
  games: {
    total: number;
    users: number;
    analyzed: number;
    analysis_rate: number;
    analyses: number;
    chat_messages: number;
    by_source: Array<{ source: string; count: number }>;
  };
  ai: {
    period_days: number;
    operations: number;
    users: number;
    total_tokens: number;
    openrouter_cost_credits: number;
    by_key: Array<{ key: string; operations: number; users: number }>;
  };
  daily: Array<{
    date: string;
    registrations: number;
    games: number;
    ai_operations: number;
  }>;
}

export const getMyPlan = () =>
  axios.get<PlanSummary>(`${API_URL}/auth/plan`).then((response) => response.data);

export const getAdminUsers = async (): Promise<AdminUser[]> => {
  const users = await axios.get<AdminUser[]>(`${API_URL}/admin/users`).then((response) => response.data);
  return users.map((user) => ({
    ...user,
    plan: {
      key: user.system_role === "admin" ? "admin" : user.plan_key,
      base_plan: user.plan_key,
      expires_at: user.premium_expires_at,
      usage: {},
      resource_limits: {},
    },
  }));
};

export const getAdminStatistics = () =>
  axios
    .get<AdminStatistics>(`${API_URL}/admin/statistics`)
    .then((response) => response.data);

export const grantPremium = (userId: string, days: number, reason: string) =>
  axios.post(`${API_URL}/admin/users/${userId}/premium`, { days, reason });

export const revokePremium = (userId: string, reason: string) =>
  axios.delete(`${API_URL}/admin/users/${userId}/premium`, { data: { reason } });
