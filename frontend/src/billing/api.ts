import axios from "axios";

import { API_URL } from "../config";

export type PaymentOrderStatus = "pending" | "paid" | "cancelled";

export interface PaymentOrder {
  id: string;
  reference_code: string;
  amount_minor: number;
  currency: "PLN";
  premium_days: number;
  recipient: string;
  iban: string;
  status: PaymentOrderStatus;
  created_at: string;
  paid_at: string | null;
  cancelled_at: string | null;
  admin_note?: string | null;
  user_email?: string;
}

export interface ManualPaymentSummary {
  enabled: boolean;
  offer: {
    amount_minor: number;
    currency: "PLN";
    premium_days: number;
  } | null;
  orders: PaymentOrder[];
}

export const getManualPaymentSummary = () =>
  axios.get<ManualPaymentSummary>(`${API_URL}/billing/manual`).then((response) => response.data);

export const createManualPaymentOrder = () =>
  axios.post<PaymentOrder>(`${API_URL}/billing/manual/orders`).then((response) => response.data);

export const getAdminPaymentOrders = () =>
  axios.get<PaymentOrder[]>(`${API_URL}/admin/payment-orders`).then((response) => response.data);

export const confirmAdminPaymentOrder = (orderId: string, reason: string) =>
  axios.post<PaymentOrder>(`${API_URL}/admin/payment-orders/${orderId}/confirm`, { reason })
    .then((response) => response.data);

export const cancelAdminPaymentOrder = (orderId: string, reason: string) =>
  axios.post<PaymentOrder>(`${API_URL}/admin/payment-orders/${orderId}/cancel`, { reason })
    .then((response) => response.data);
