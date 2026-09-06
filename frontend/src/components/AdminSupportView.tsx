import { useEffect, useState, type FormEvent } from "react";

import { getAuthErrorMessage } from "../auth/api";
import {
  getAdminSupportTicket,
  getAdminSupportTickets,
  markAdminSupportTicketRead,
  replyToAdminSupportTicket,
  setAdminSupportTicketStatus,
  type SupportTicket,
  type TicketStatus,
} from "../support/api";

interface AdminSupportViewProps {
  onUnreadChange: (count: number) => void;
}

const categoryLabels = { problem: "Problem", idea: "Pomysł", question: "Pytanie" };
const statusLabels = { open: "Nowe", waiting_user: "Oczekuje na użytkownika", closed: "Zamknięte" };

export default function AdminSupportView({ onUnreadChange }: AdminSupportViewProps) {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [filter, setFilter] = useState<"active" | "all">("active");
  const [reply, setReply] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadTickets = async () => {
    const items = await getAdminSupportTickets();
    setTickets(items);
    return items;
  };

  useEffect(() => {
    let active = true;
    getAdminSupportTickets()
      .then((items) => { if (active) setTickets(items); })
      .catch((requestError) => { if (active) setError(getAuthErrorMessage(requestError, "Nie udało się pobrać zgłoszeń.")); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const openTicket = async (ticketId: string) => {
    setLoading(true);
    setError("");
    try {
      const detail = await getAdminSupportTicket(ticketId);
      setSelected({ ...detail, unread_count: 0 });
      const lastMessage = detail.messages?.[detail.messages.length - 1];
      if (lastMessage) {
        const unread = await markAdminSupportTicketRead(ticketId, lastMessage.id);
        onUnreadChange(unread);
      }
      setTickets((items) => items.map((item) => item.id === ticketId ? { ...item, unread_count: 0 } : item));
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się otworzyć zgłoszenia."));
    } finally {
      setLoading(false);
    }
  };

  const submitReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    setBusy(true);
    setError("");
    try {
      const updated = await replyToAdminSupportTicket(selected.id, reply.trim());
      setSelected(updated);
      setReply("");
      await loadTickets();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wysłać odpowiedzi."));
    } finally {
      setBusy(false);
    }
  };

  const changeStatus = async (status: TicketStatus) => {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      const updated = await setAdminSupportTicketStatus(selected.id, status);
      setSelected(updated);
      await loadTickets();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się zmienić statusu."));
    } finally {
      setBusy(false);
    }
  };

  const visibleTickets = filter === "active" ? tickets.filter((ticket) => ticket.status !== "closed") : tickets;

  return (
    <section className="admin-support-view">
      <div className="admin-support-toolbar"><p className="admin-note">Odpowiedź zmienia status na „Oczekuje na użytkownika”. Jego kolejna wiadomość ponownie otwiera zgłoszenie.</p><label>Pokaż<select value={filter} onChange={(event) => setFilter(event.target.value as "active" | "all")}><option value="active">Aktywne</option><option value="all">Wszystkie</option></select></label></div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      <div className="admin-support-layout">
        <div className="admin-support-list">
          {visibleTickets.map((ticket) => (
            <button className={selected?.id === ticket.id ? "active" : ""} type="button" key={ticket.id} onClick={() => void openTicket(ticket.id)}>
              <span><strong>{ticket.subject}</strong>{ticket.unread_count > 0 && <i className="notification-badge">{ticket.unread_count > 99 ? "99+" : ticket.unread_count}</i>}</span>
              <small>{ticket.owner?.display_name || ticket.owner?.email}</small>
              <small>{categoryLabels[ticket.category]} · {statusLabels[ticket.status]}</small>
            </button>
          ))}
          {!visibleTickets.length && !loading && <p className="admin-empty">Brak zgłoszeń w tym widoku.</p>}
        </div>
        <div className="admin-support-thread">
          {loading ? <p>Ładowanie…</p> : selected ? (
            <>
              <div className="support-thread-heading"><div><span className={`support-category ${selected.category}`}>{categoryLabels[selected.category]}</span><h3>{selected.subject}</h3><small>{selected.owner?.display_name ? `${selected.owner.display_name} · ` : ""}{selected.owner?.email}</small></div><select aria-label="Status zgłoszenia" disabled={busy} value={selected.status} onChange={(event) => void changeStatus(event.target.value as TicketStatus)}><option value="open">Nowe</option><option value="waiting_user">Oczekuje na użytkownika</option><option value="closed">Zamknięte</option></select></div>
              <div className="support-messages">
                {selected.messages?.map((item) => <article className={item.author_role} key={item.id}><strong>{item.author_role === "admin" ? "Administrator" : selected.owner?.display_name || selected.owner?.email || "Użytkownik"}</strong><p>{item.content}</p><time>{new Date(item.created_at).toLocaleString("pl-PL")}</time></article>)}
              </div>
              <form className="support-reply-form" onSubmit={submitReply}><label htmlFor="admin-support-reply">Odpowiedź administratora</label><textarea id="admin-support-reply" rows={4} maxLength={5000} value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Napisz odpowiedź…" /><div><small>{reply.length} / 5000</small><button type="submit" disabled={busy || !reply.trim()}>{busy ? "Wysyłanie…" : "Wyślij odpowiedź"}</button></div></form>
            </>
          ) : <div className="support-placeholder"><span aria-hidden="true">✉</span><h3>Wybierz zgłoszenie</h3><p>Nieprzeczytane wiadomości są oznaczone czerwonym licznikiem.</p></div>}
        </div>
      </div>
    </section>
  );
}
