import axios from "axios";

import { API_URL } from "../config";

export type TicketCategory = "problem" | "idea" | "question";
export type TicketStatus = "open" | "waiting_user" | "closed";

export interface SupportMessage {
  id: string;
  author_role: "user" | "admin";
  content: string;
  created_at: string;
}

export interface TicketOwner {
  id: string;
  email: string;
  display_name: string | null;
}

export interface SupportTicket {
  id: string;
  category: TicketCategory;
  subject: string;
  status: TicketStatus;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  unread_count: number;
  owner?: TicketOwner;
  messages?: SupportMessage[];
}

export const getSupportUnreadCount = () =>
  axios.get<{ unread_count: number }>(`${API_URL}/support/unread-count`).then((response) => response.data.unread_count);

export const getMySupportTickets = () =>
  axios.get<{ tickets: SupportTicket[] }>(`${API_URL}/support/tickets`).then((response) => response.data.tickets);

export const getMySupportTicket = (ticketId: string) =>
  axios.get<SupportTicket>(`${API_URL}/support/tickets/${ticketId}`).then((response) => response.data);

export const createSupportTicket = (category: TicketCategory, subject: string, message: string) =>
  axios.post<SupportTicket>(`${API_URL}/support/tickets`, { category, subject, message }).then((response) => response.data);

export const replyToSupportTicket = (ticketId: string, message: string) =>
  axios.post<SupportTicket>(`${API_URL}/support/tickets/${ticketId}/messages`, { message }).then((response) => response.data);

export const markSupportTicketRead = (ticketId: string, throughMessageId: string) =>
  axios.post<{ unread_count: number }>(`${API_URL}/support/tickets/${ticketId}/read`, { through_message_id: throughMessageId }).then((response) => response.data.unread_count);

export const getAdminSupportUnreadCount = () =>
  axios.get<{ unread_count: number }>(`${API_URL}/admin/support/unread-count`).then((response) => response.data.unread_count);

export const getAdminSupportTickets = () =>
  axios.get<{ tickets: SupportTicket[] }>(`${API_URL}/admin/support/tickets`).then((response) => response.data.tickets);

export const getAdminSupportTicket = (ticketId: string) =>
  axios.get<SupportTicket>(`${API_URL}/admin/support/tickets/${ticketId}`).then((response) => response.data);

export const replyToAdminSupportTicket = (ticketId: string, message: string) =>
  axios.post<SupportTicket>(`${API_URL}/admin/support/tickets/${ticketId}/messages`, { message }).then((response) => response.data);

export const markAdminSupportTicketRead = (ticketId: string, throughMessageId: string) =>
  axios.post<{ unread_count: number }>(`${API_URL}/admin/support/tickets/${ticketId}/read`, { through_message_id: throughMessageId }).then((response) => response.data.unread_count);

export const setAdminSupportTicketStatus = (ticketId: string, status: TicketStatus) =>
  axios.patch<SupportTicket>(`${API_URL}/admin/support/tickets/${ticketId}/status`, { status }).then((response) => response.data);
