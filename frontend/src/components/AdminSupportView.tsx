import { useEffect, useMemo, useState, type FormEvent } from "react";

import type { AdminUser } from "../admin/api";
import { getAuthErrorMessage } from "../auth/api";
import {
  archiveAdminAnnouncement,
  createAdminAnnouncement,
  createAdminSupportThread,
  getAdminAnnouncements,
  getAdminSupportTicket,
  getAdminSupportTickets,
  markAdminSupportTicketRead,
  replyToAdminSupportTicket,
  setAdminSupportTicketStatus,
  type Announcement,
  type SupportTicket,
  type TicketStatus,
} from "../support/api";

interface AdminSupportViewProps {
  users: AdminUser[];
  onUnreadChange: (count: number) => void;
}

const categoryLabels = { problem: "Problem", idea: "Pomysł", question: "Pytanie", message: "Wiadomość" };
const statusLabels = { open: "Nowe", waiting_user: "Oczekuje na użytkownika", closed: "Zamknięte" };

export default function AdminSupportView({ users, onUnreadChange }: AdminSupportViewProps) {
  const recipients = useMemo(
    () => users.filter((user) => user.status === "active" && user.email_verified && user.system_role !== "admin"),
    [users],
  );
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [selectedAnnouncement, setSelectedAnnouncement] = useState<Announcement | null>(null);
  const [compose, setCompose] = useState<"direct" | "announcement" | null>(null);
  const [filter, setFilter] = useState<"active" | "all">("active");
  const [reply, setReply] = useState("");
  const [targetUserId, setTargetUserId] = useState("");
  const [subject, setSubject] = useState("");
  const [outboundMessage, setOutboundMessage] = useState("");
  const [announcementTitle, setAnnouncementTitle] = useState("");
  const [announcementContent, setAnnouncementContent] = useState("");
  const [announcementExpiry, setAnnouncementExpiry] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadAll = async () => {
    const [ticketItems, announcementItems] = await Promise.all([getAdminSupportTickets(), getAdminAnnouncements()]);
    setTickets(ticketItems);
    setAnnouncements(announcementItems);
  };

  useEffect(() => {
    let active = true;
    Promise.all([getAdminSupportTickets(), getAdminAnnouncements()])
      .then(([ticketItems, announcementItems]) => {
        if (!active) return;
        setTickets(ticketItems);
        setAnnouncements(announcementItems);
      })
      .catch((requestError) => { if (active) setError(getAuthErrorMessage(requestError, "Nie udało się pobrać wiadomości.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const openTicket = async (ticketId: string) => {
    setLoading(true); setError(""); setCompose(null); setSelectedAnnouncement(null);
    try {
      const detail = await getAdminSupportTicket(ticketId);
      setSelected({ ...detail, unread_count: 0 });
      const lastMessage = detail.messages?.at(-1);
      if (lastMessage) onUnreadChange(await markAdminSupportTicketRead(ticketId, lastMessage.id));
      setTickets((items) => items.map((item) => item.id === ticketId ? { ...item, unread_count: 0 } : item));
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się otworzyć rozmowy."));
    } finally { setLoading(false); }
  };

  const submitReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    setBusy(true); setError("");
    try {
      setSelected(await replyToAdminSupportTicket(selected.id, reply.trim()));
      setReply(""); await loadAll();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wysłać odpowiedzi."));
    } finally { setBusy(false); }
  };

  const submitDirect = async (event: FormEvent) => {
    event.preventDefault();
    const resolvedTargetUserId = targetUserId || recipients[0]?.id || "";
    if (!resolvedTargetUserId || !subject.trim() || !outboundMessage.trim()) return;
    setBusy(true); setError("");
    try {
      const thread = await createAdminSupportThread(resolvedTargetUserId, subject.trim(), outboundMessage.trim());
      setSubject(""); setOutboundMessage(""); setCompose(null); setSelected(thread);
      await loadAll();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się rozpocząć rozmowy."));
    } finally { setBusy(false); }
  };

  const submitAnnouncement = async (event: FormEvent) => {
    event.preventDefault();
    if (!announcementTitle.trim() || !announcementContent.trim()) return;
    if (!window.confirm(`Opublikować ogłoszenie dla ${recipients.length} aktywnych użytkowników?`)) return;
    setBusy(true); setError("");
    try {
      const expiresAt = announcementExpiry ? new Date(`${announcementExpiry}T23:59:59`).toISOString() : null;
      const item = await createAdminAnnouncement(announcementTitle.trim(), announcementContent.trim(), expiresAt);
      setAnnouncementTitle(""); setAnnouncementContent(""); setAnnouncementExpiry("");
      setCompose(null); setSelected(null); setSelectedAnnouncement(item);
      await loadAll();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się opublikować ogłoszenia."));
    } finally { setBusy(false); }
  };

  const changeStatus = async (status: TicketStatus) => {
    if (!selected) return;
    setBusy(true); setError("");
    try {
      setSelected(await setAdminSupportTicketStatus(selected.id, status));
      await loadAll();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się zmienić statusu."));
    } finally { setBusy(false); }
  };

  const archiveAnnouncement = async (item: Announcement) => {
    if (!window.confirm(`Archiwizować ogłoszenie „${item.title}”? Zniknie z wiadomości użytkowników.`)) return;
    setBusy(true); setError("");
    try {
      await archiveAdminAnnouncement(item.id);
      setSelectedAnnouncement(null); await loadAll();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się zarchiwizować ogłoszenia."));
    } finally { setBusy(false); }
  };

  const visibleTickets = filter === "active" ? tickets.filter((ticket) => ticket.status !== "closed") : tickets;

  return (
    <section className="admin-support-view">
      <div className="admin-support-toolbar"><div className="admin-message-actions"><button type="button" onClick={() => { setCompose("direct"); setSelected(null); setSelectedAnnouncement(null); }}>＋ Wiadomość do użytkownika</button><button type="button" onClick={() => { setCompose("announcement"); setSelected(null); setSelectedAnnouncement(null); }}>＋ Ogłoszenie dla wszystkich</button></div><label>Pokaż<select value={filter} onChange={(event) => setFilter(event.target.value as "active" | "all")}><option value="active">Aktywne</option><option value="all">Wszystkie</option></select></label></div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="admin-support-layout">
        <div className="admin-support-list">
          {announcements.length > 0 && <p className="support-list-label">OGŁOSZENIA</p>}
          {announcements.map((item) => <button className={selectedAnnouncement?.id === item.id ? "active" : ""} type="button" key={item.id} onClick={() => { setSelectedAnnouncement(item); setSelected(null); setCompose(null); }}><span><strong>{item.title}</strong></span><small>{item.archived_at ? "Zarchiwizowane" : "Opublikowane"} · odczyty: {item.read_count ?? 0} · odpowiedzi: {item.reply_count ?? 0}</small></button>)}
          {visibleTickets.length > 0 && <p className="support-list-label">ROZMOWY</p>}
          {visibleTickets.map((ticket) => <button className={selected?.id === ticket.id ? "active" : ""} type="button" key={ticket.id} onClick={() => void openTicket(ticket.id)}><span><strong>{ticket.subject}</strong>{ticket.unread_count > 0 && <i className="notification-badge">{ticket.unread_count > 99 ? "99+" : ticket.unread_count}</i>}</span><small>{ticket.owner?.display_name || ticket.owner?.email}</small><small>{categoryLabels[ticket.category]} · {statusLabels[ticket.status]}</small></button>)}
          {!visibleTickets.length && !announcements.length && !loading && <p className="admin-empty">Brak wiadomości.</p>}
        </div>
        <div className="admin-support-thread">
          {loading ? <p>Ładowanie…</p> : compose === "direct" ? (
            <form className="support-form admin-compose-form" onSubmit={submitDirect}><h3>Nowa wiadomość prywatna</h3><label>Użytkownik<select required value={targetUserId || recipients[0]?.id || ""} onChange={(event) => setTargetUserId(event.target.value)}>{recipients.map((user) => <option value={user.id} key={user.id}>{user.display_name ? `${user.display_name} · ` : ""}{user.email}</option>)}</select></label><label>Temat<input required minLength={5} maxLength={160} value={subject} onChange={(event) => setSubject(event.target.value)} /></label><label>Wiadomość<textarea required rows={8} maxLength={5000} value={outboundMessage} onChange={(event) => setOutboundMessage(event.target.value)} /></label><small>{outboundMessage.length} / 5000</small><button type="submit" disabled={busy || !recipients.length}>{busy ? "Wysyłanie…" : "Wyślij wiadomość"}</button></form>
          ) : compose === "announcement" ? (
            <form className="support-form admin-compose-form" onSubmit={submitAnnouncement}><h3>Ogłoszenie dla wszystkich</h3><p className="admin-note">Ogłoszenie zobaczy {recipients.length} obecnych, aktywnych użytkowników. Odpowiedzi utworzą osobne prywatne rozmowy.</p><label>Tytuł<input required minLength={5} maxLength={160} value={announcementTitle} onChange={(event) => setAnnouncementTitle(event.target.value)} /></label><label>Treść<textarea required rows={10} maxLength={5000} value={announcementContent} onChange={(event) => setAnnouncementContent(event.target.value)} /></label><label>Wygaśnięcie (opcjonalne)<input type="date" value={announcementExpiry} onChange={(event) => setAnnouncementExpiry(event.target.value)} /></label><small>{announcementContent.length} / 5000</small><button type="submit" disabled={busy}>{busy ? "Publikowanie…" : "Opublikuj ogłoszenie"}</button></form>
          ) : selectedAnnouncement ? (
            <div className="admin-announcement-detail"><div className="support-thread-heading"><div><span className="support-category message">Ogłoszenie</span><h3>{selectedAnnouncement.title}</h3><small>{new Date(selectedAnnouncement.published_at).toLocaleString("pl-PL")}</small></div>{!selectedAnnouncement.archived_at && <button className="danger-action" type="button" disabled={busy} onClick={() => void archiveAnnouncement(selectedAnnouncement)}>Archiwizuj</button>}</div><div className="announcement-content">{selectedAnnouncement.content}</div><p className="admin-note">Odczyty: {selectedAnnouncement.read_count ?? 0} · prywatne odpowiedzi: {selectedAnnouncement.reply_count ?? 0}</p></div>
          ) : selected ? (
            <><div className="support-thread-heading"><div><span className={`support-category ${selected.category}`}>{categoryLabels[selected.category]}</span><h3>{selected.subject}</h3><small>{selected.owner?.display_name ? `${selected.owner.display_name} · ` : ""}{selected.owner?.email}</small></div><select aria-label="Status rozmowy" disabled={busy} value={selected.status} onChange={(event) => void changeStatus(event.target.value as TicketStatus)}><option value="open">Nowe</option><option value="waiting_user">Oczekuje na użytkownika</option><option value="closed">Zamknięte</option></select></div><div className="support-messages">{selected.messages?.map((item) => <article className={item.author_role} key={item.id}><strong>{item.author_role === "admin" ? "Administrator" : selected.owner?.display_name || selected.owner?.email || "Użytkownik"}</strong><p>{item.content}</p><time>{new Date(item.created_at).toLocaleString("pl-PL")}</time></article>)}</div><form className="support-reply-form" onSubmit={submitReply}><label htmlFor="admin-support-reply">Odpowiedź administratora</label><textarea id="admin-support-reply" rows={4} maxLength={5000} value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Napisz odpowiedź…" /><div><small>{reply.length} / 5000</small><button type="submit" disabled={busy || !reply.trim()}>{busy ? "Wysyłanie…" : "Wyślij odpowiedź"}</button></div></form></>
          ) : <div className="support-placeholder"><span aria-hidden="true">✉</span><h3>Wiadomości użytkowników</h3><p>Rozpocznij prywatną rozmowę, opublikuj ogłoszenie albo wybierz istniejący wątek.</p></div>}
        </div>
      </div>
    </section>
  );
}
