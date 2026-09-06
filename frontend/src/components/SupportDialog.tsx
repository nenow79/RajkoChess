import { useEffect, useState, type FormEvent } from "react";

import { getAuthErrorMessage } from "../auth/api";
import {
  createSupportTicket,
  getMySupportTicket,
  getMySupportTickets,
  markSupportTicketRead,
  replyToSupportTicket,
  type SupportTicket,
  type TicketCategory,
} from "../support/api";

interface SupportDialogProps {
  onClose: () => void;
  onUnreadChange: (count: number) => void;
}

const categoryLabels: Record<TicketCategory, string> = {
  problem: "Problem",
  idea: "Pomysł",
  question: "Pytanie",
};

const statusLabels = {
  open: "Nowe",
  waiting_user: "Oczekuje na Ciebie",
  closed: "Zamknięte",
};

export default function SupportDialog({ onClose, onUnreadChange }: SupportDialogProps) {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
  const [creating, setCreating] = useState(false);
  const [category, setCategory] = useState<TicketCategory>("problem");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [reply, setReply] = useState("");
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
    getMySupportTickets()
      .then((items) => {
        if (active) setTickets(items);
      })
      .catch((requestError) => {
        if (active) setError(getAuthErrorMessage(requestError, "Nie udało się pobrać zgłoszeń."));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const openTicket = async (ticketId: string) => {
    setLoading(true);
    setError("");
    try {
      const detail = await getMySupportTicket(ticketId);
      setSelected({ ...detail, unread_count: 0 });
      setCreating(false);
      const lastMessage = detail.messages?.[detail.messages.length - 1];
      if (lastMessage) {
        const unread = await markSupportTicketRead(ticketId, lastMessage.id);
        onUnreadChange(unread);
      }
      setTickets((items) => items.map((item) => item.id === ticketId ? { ...item, unread_count: 0 } : item));
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się otworzyć zgłoszenia."));
    } finally {
      setLoading(false);
    }
  };

  const submitNew = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await createSupportTicket(category, subject.trim(), message.trim());
      setSubject("");
      setMessage("");
      setCreating(false);
      setSelected(created);
      await loadTickets();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wysłać zgłoszenia."));
    } finally {
      setBusy(false);
    }
  };

  const submitReply = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected || !reply.trim()) return;
    setBusy(true);
    setError("");
    try {
      const updated = await replyToSupportTicket(selected.id, reply.trim());
      setReply("");
      setSelected(updated);
      await loadTickets();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wysłać odpowiedzi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="support-overlay" role="dialog" aria-modal="true" aria-labelledby="support-title">
      <section className="support-dialog">
        <header>
          <div><p className="auth-eyebrow">POMOC I POMYSŁY</p><h2 id="support-title">Napisz do Rajko Chess</h2></div>
          <button type="button" onClick={onClose} aria-label="Zamknij">×</button>
        </header>
        <div className="support-layout">
          <aside className="support-ticket-list">
            <button className="support-new-button" type="button" onClick={() => { setCreating(true); setSelected(null); setError(""); }}>＋ Nowe zgłoszenie</button>
            {tickets.map((ticket) => (
              <button className={selected?.id === ticket.id ? "active" : ""} type="button" key={ticket.id} onClick={() => void openTicket(ticket.id)}>
                <span><strong>{ticket.subject}</strong>{ticket.unread_count > 0 && <i className="notification-badge">{ticket.unread_count > 99 ? "99+" : ticket.unread_count}</i>}</span>
                <small>{categoryLabels[ticket.category]} · {statusLabels[ticket.status]}</small>
              </button>
            ))}
            {!tickets.length && !loading && <p>Nie masz jeszcze żadnych zgłoszeń.</p>}
          </aside>
          <main className="support-content">
            {error && <p className="auth-error" role="alert">{error}</p>}
            {loading ? <p>Ładowanie…</p> : creating ? (
              <form className="support-form" onSubmit={submitNew}>
                <h3>Nowe zgłoszenie</h3>
                <label>Rodzaj<select value={category} onChange={(event) => setCategory(event.target.value as TicketCategory)}><option value="problem">Problem</option><option value="idea">Pomysł</option><option value="question">Pytanie</option></select></label>
                <label>Temat<input value={subject} minLength={5} maxLength={160} required onChange={(event) => setSubject(event.target.value)} placeholder="Krótko opisz, czego dotyczy wiadomość" /></label>
                <label>Wiadomość<textarea value={message} minLength={3} maxLength={5000} required rows={8} onChange={(event) => setMessage(event.target.value)} placeholder="Opisz problem lub pomysł. Przy problemie napisz też, co robiłeś przed jego wystąpieniem." /></label>
                <small>{message.length} / 5000</small>
                <button type="submit" disabled={busy}>{busy ? "Wysyłanie…" : "Wyślij zgłoszenie"}</button>
              </form>
            ) : selected ? (
              <div className="support-thread-view">
                <div className="support-thread-heading"><div><span className={`support-category ${selected.category}`}>{categoryLabels[selected.category]}</span><h3>{selected.subject}</h3></div><span className={`support-status ${selected.status}`}>{statusLabels[selected.status]}</span></div>
                <div className="support-messages">
                  {selected.messages?.map((item) => <article className={item.author_role} key={item.id}><strong>{item.author_role === "admin" ? "Zespół Rajko Chess" : "Ty"}</strong><p>{item.content}</p><time>{new Date(item.created_at).toLocaleString("pl-PL")}</time></article>)}
                </div>
                <form className="support-reply-form" onSubmit={submitReply}><label htmlFor="support-reply">Twoja odpowiedź</label><textarea id="support-reply" rows={4} maxLength={5000} value={reply} onChange={(event) => setReply(event.target.value)} placeholder="Dopisz wiadomość…" /><div><small>{reply.length} / 5000</small><button type="submit" disabled={busy || !reply.trim()}>{busy ? "Wysyłanie…" : "Wyślij"}</button></div></form>
              </div>
            ) : <div className="support-placeholder"><span aria-hidden="true">✉</span><h3>Wybierz zgłoszenie lub napisz nowe</h3><p>Odpowiedzi nie muszą być prowadzone na żywo. Wróć tutaj, gdy zobaczysz licznik nowej wiadomości.</p></div>}
          </main>
        </div>
      </section>
    </div>
  );
}
