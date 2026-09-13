import { useEffect, useState, type FormEvent } from "react";

import { getAuthErrorMessage } from "../auth/api";
import {
  createSupportTicket,
  getMyAnnouncements,
  getMySupportTicket,
  getMySupportTickets,
  markAnnouncementRead,
  markSupportTicketRead,
  replyToAnnouncement,
  replyToSupportTicket,
  type Announcement,
  type SupportTicket,
  type TicketCategory,
} from "../support/api";

interface SupportDialogProps {
  onClose: () => void;
  onUnreadChange: (count: number) => void;
}

const categoryLabels: Record<TicketCategory, string> = {
  problem: "Problem", idea: "Pomysł", question: "Pytanie", message: "Wiadomość",
};
const statusLabels = { open: "Nowe", waiting_user: "Oczekuje na Ciebie", closed: "Zamknięte" };

export default function SupportDialog({ onClose, onUnreadChange }: SupportDialogProps) {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [selectedAnnouncement, setSelectedAnnouncement] = useState<Announcement | null>(null);
  const [creating, setCreating] = useState(false);
  const [category, setCategory] = useState<TicketCategory>("problem");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
  const [announcementReply, setAnnouncementReply] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadTickets = async () => {
    const items = await getMySupportTickets();
    setTickets(items);
    return items;
  };

  useEffect(() => {
    let active = true;
    Promise.all([getMySupportTickets(), getMyAnnouncements()])
      .then(([ticketItems, announcementItems]) => {
        if (!active) return;
        setTickets(ticketItems);
        setAnnouncements(announcementItems);
      })
      .catch((requestError) => {
        if (active) setError(getAuthErrorMessage(requestError, "Nie udało się pobrać wiadomości."));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const openTicket = async (ticketId: string) => {
    setLoading(true);
    setError("");
    try {
      const detail = await getMySupportTicket(ticketId);
      setSelected({ ...detail, unread_count: 0 });
      setSelectedAnnouncement(null);
      setCreating(false);
      const lastMessage = detail.messages?.at(-1);
      if (lastMessage) onUnreadChange(await markSupportTicketRead(ticketId, lastMessage.id));
      setTickets((items) => items.map((item) => item.id === ticketId ? { ...item, unread_count: 0 } : item));
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się otworzyć rozmowy."));
    } finally {
      setLoading(false);
    }
  };

  const openAnnouncement = async (announcement: Announcement) => {
    setSelectedAnnouncement({ ...announcement, read: true });
    setSelected(null);
    setCreating(false);
    setError("");
    if (!announcement.read) {
      try {
        onUnreadChange(await markAnnouncementRead(announcement.id));
        setAnnouncements((items) => items.map((item) => item.id === announcement.id ? { ...item, read: true } : item));
      } catch (requestError) {
        setError(getAuthErrorMessage(requestError, "Nie udało się oznaczyć ogłoszenia jako przeczytanego."));
      }
    }
  };

  const submitNew = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const created = await createSupportTicket(category, subject.trim(), message.trim());
      setSubject(""); setMessage(""); setCreating(false); setSelected(created);
      await loadTickets();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wysłać zgłoszenia."));
    } finally { setBusy(false); }
  };

  const submitReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    setBusy(true); setError("");
    try {
      setSelected(await replyToSupportTicket(selected.id, reply.trim()));
      setReply(""); await loadTickets();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wysłać odpowiedzi."));
    } finally { setBusy(false); }
  };

  const submitAnnouncementReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!selectedAnnouncement || !announcementReply.trim()) return;
    setBusy(true); setError("");
    try {
      const thread = await replyToAnnouncement(selectedAnnouncement.id, announcementReply.trim());
      setAnnouncementReply(""); setSelectedAnnouncement(null); setSelected(thread);
      await loadTickets();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wysłać odpowiedzi na ogłoszenie."));
    } finally { setBusy(false); }
  };

  return (
    <div className="support-overlay" role="dialog" aria-modal="true" aria-labelledby="support-title">
      <section className="support-dialog">
        <header><div><p className="auth-eyebrow">WIADOMOŚCI I POMOC</p><h2 id="support-title">Rajko Chess</h2></div><button type="button" onClick={onClose} aria-label="Zamknij">×</button></header>
        <div className="support-layout">
          <aside className="support-ticket-list">
            <button className="support-new-button" type="button" onClick={() => { setCreating(true); setSelected(null); setSelectedAnnouncement(null); setError(""); }}>＋ Nowe zgłoszenie</button>
            {announcements.length > 0 && <p className="support-list-label">OGŁOSZENIA</p>}
            {announcements.map((announcement) => <button className={selectedAnnouncement?.id === announcement.id ? "active" : ""} type="button" key={announcement.id} onClick={() => void openAnnouncement(announcement)}><span><strong>{announcement.title}</strong>{!announcement.read && <i className="notification-badge">1</i>}</span><small>Ogłoszenie · {new Date(announcement.published_at).toLocaleDateString("pl-PL")}</small></button>)}
            {tickets.length > 0 && <p className="support-list-label">ROZMOWY</p>}
            {tickets.map((ticket) => <button className={selected?.id === ticket.id ? "active" : ""} type="button" key={ticket.id} onClick={() => void openTicket(ticket.id)}><span><strong>{ticket.subject}</strong>{ticket.unread_count > 0 && <i className="notification-badge">{ticket.unread_count > 99 ? "99+" : ticket.unread_count}</i>}</span><small>{categoryLabels[ticket.category]} · {statusLabels[ticket.status]}</small></button>)}
            {!tickets.length && !announcements.length && !loading && <p>Nie masz jeszcze żadnych wiadomości.</p>}
          </aside>
          <main className="support-content">
            {error && <p className="auth-error" role="alert">{error}</p>}
            {loading ? <p>Ładowanie…</p> : selectedAnnouncement ? (
              <div className="support-thread-view announcement-view"><div className="support-thread-heading"><div><span className="support-category message">Ogłoszenie</span><h3>{selectedAnnouncement.title}</h3><small>{new Date(selectedAnnouncement.published_at).toLocaleString("pl-PL")}</small></div></div><div className="announcement-content">{selectedAnnouncement.content}</div><form className="support-reply-form" onSubmit={submitAnnouncementReply}><label htmlFor="announcement-reply">Odpowiedz prywatnie</label><textarea id="announcement-reply" rows={4} maxLength={5000} value={announcementReply} onChange={(event) => setAnnouncementReply(event.target.value)} placeholder="Twoja odpowiedź utworzy prywatną rozmowę z administratorem." /><div><small>{announcementReply.length} / 5000</small><button type="submit" disabled={busy || !announcementReply.trim()}>{busy ? "Wysyłanie…" : "Wyślij odpowiedź"}</button></div></form></div>
            ) : creating ? (
              <form className="support-form" onSubmit={submitNew}><h3>Nowe zgłoszenie</h3><label>Rodzaj<select value={category} onChange={(event) => setCategory(event.target.value as TicketCategory)}><option value="problem">Problem</option><option value="idea">Pomysł</option><option value="question">Pytanie</option></select></label><label>Temat<input value={subject} minLength={5} maxLength={160} required onChange={(event) => setSubject(event.target.value)} placeholder="Krótko opisz, czego dotyczy wiadomość" /></label><label>Wiadomość<textarea value={message} minLength={3} maxLength={5000} required rows={8} onChange={(event) => setMessage(event.target.value)} placeholder="Opisz problem lub pomysł." /></label><small>{message.length} / 5000</small><button type="submit" disabled={busy}>{busy ? "Wysyłanie…" : "Wyślij zgłoszenie"}</button></form>
            ) : selected ? (
              <div className="support-thread-view"><div className="support-thread-heading"><div><span className={`support-category ${selected.category}`}>{categoryLabels[selected.category]}</span><h3>{selected.subject}</h3></div><span className={`support-status ${selected.status}`}>{statusLabels[selected.status]}</span></div><div className="support-messages">{selected.messages?.map((item) => <article className={item.author_role} key={item.id}><strong>{item.author_role === "admin" ? "Zespół Rajko Chess" : "Ty"}</strong><p>{item.content}</p><time>{new Date(item.created_at).toLocaleString("pl-PL")}</time></article>)}</div><form className="support-reply-form" onSubmit={submitReply}><label htmlFor="support-reply">Twoja odpowiedź</label><textarea id="support-reply" rows={4} maxLength={5000} value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Dopisz wiadomość…" /><div><small>{reply.length} / 5000</small><button type="submit" disabled={busy || !reply.trim()}>{busy ? "Wysyłanie…" : "Wyślij"}</button></div></form></div>
            ) : <div className="support-placeholder"><span aria-hidden="true">✉</span><h3>Wybierz wiadomość lub napisz nowe zgłoszenie</h3><p>Wróć tutaj, gdy przy kopercie pojawi się licznik nowej wiadomości.</p></div>}
          </main>
        </div>
      </section>
    </div>
  );
}
