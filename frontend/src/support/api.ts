import axios from "axios";

import { API_URL } from "../config";

export type TicketCategory = "problem" | "idea" | "question" | "message";
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
  initiated_by: "user" | "admin" | "system";
  source_announcement_id: string | null;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  unread_count: number;
  owner?: TicketOwner;
  messages?: SupportMessage[];
}

export interface Announcement {
  id: string;
  title: string;
  content: string;
  published_at: string;
  expires_at: string | null;
  archived_at: string | null;
  read?: boolean;
  replied_ticket_id?: string | null;
  recipient_count?: number;
  read_count?: number;
  reply_count?: number;
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

export const getMyAnnouncements = () =>
  axios.get<{ announcements: Announcement[] }>(`${API_URL}/support/announcements`).then((response) => response.data.announcements);

export const markAnnouncementRead = (announcementId: string) =>
  axios.post<{ unread_count: number }>(`${API_URL}/support/announcements/${announcementId}/read`).then((response) => response.data.unread_count);

export const replyToAnnouncement = (announcementId: string, message: string) =>
  axios.post<SupportTicket>(`${API_URL}/support/announcements/${announcementId}/reply`, { message }).then((response) => response.data);

export const createAdminSupportThread = (userId: string, subject: string, message: string) =>
  axios.post<SupportTicket>(`${API_URL}/admin/support/tickets`, { user_id: userId, subject, message }).then((response) => response.data);

export const getAdminAnnouncements = () =>
  axios.get<{ announcements: Announcement[] }>(`${API_URL}/admin/support/announcements`).then((response) => response.data.announcements);

export const createAdminAnnouncement = (title: string, content: string, expiresAt: string | null) =>
  axios.post<Announcement>(`${API_URL}/admin/support/announcements`, { title, content, expires_at: expiresAt }).then((response) => response.data);

export const archiveAdminAnnouncement = (announcementId: string) =>
  axios.post<Announcement>(`${API_URL}/admin/support/announcements/${announcementId}/archive`).then((response) => response.data);
