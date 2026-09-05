import { useEffect, useState } from "react";

import { getAuthErrorMessage } from "../auth/api";
import {
  createManualPaymentOrder,
  getManualPaymentSummary,
  type ManualPaymentSummary,
  type PaymentOrder,
} from "../billing/api";

interface PaymentDialogProps {
  onClose: () => void;
}

const money = (minor: number, currency: string) =>
  new Intl.NumberFormat("pl-PL", { style: "currency", currency }).format(minor / 100);

const spacedIban = (iban: string) => iban.replace(/(.{4})/g, "$1 ").trim();

const statusLabel: Record<PaymentOrder["status"], string> = {
  pending: "Oczekuje na wpłatę",
  paid: "Opłacone",
  cancelled: "Anulowane",
};

export default function PaymentDialog({ onClose }: PaymentDialogProps) {
  const [summary, setSummary] = useState<ManualPaymentSummary | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState("");

  const load = () => getManualPaymentSummary().then(setSummary);

  useEffect(() => {
    let active = true;
    getManualPaymentSummary()
      .then((result) => { if (active) setSummary(result); })
      .catch((requestError) => {
        if (active) setError(getAuthErrorMessage(requestError, "Nie udało się pobrać zamówień."));
      });
    return () => { active = false; };
  }, []);

  const createOrder = async () => {
    setBusy(true);
    setError("");
    try {
      await createManualPaymentOrder();
      await load();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się utworzyć zamówienia."));
    } finally {
      setBusy(false);
    }
  };

  const refresh = async () => {
    setBusy(true);
    setError("");
    try {
      await load();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się odświeżyć statusu."));
    } finally {
      setBusy(false);
    }
  };

  const copy = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(label);
      window.setTimeout(() => setCopied(""), 1800);
    } catch {
      setError("Nie udało się skopiować. Zaznacz wartość ręcznie.");
    }
  };

  const pending = summary?.orders.find((order) => order.status === "pending");

  return (
    <div className="payment-overlay" onMouseDown={onClose}>
      <section className="payment-card" role="dialog" aria-modal="true" aria-labelledby="payment-title" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div><p className="auth-eyebrow">RAJKO CHESS</p><h2 id="payment-title">{pending ? "Dokończ zamówienie" : "Kup Premium"}</h2><p className="payment-lead">Więcej analiz i narzędzi treningowych przez 30 dni.</p></div>
          <button type="button" onClick={onClose} aria-label="Zamknij">×</button>
        </header>
        {error && <p className="account-settings-error" role="alert">{error}</p>}
        {!summary && !error && <p>Ładowanie…</p>}
        {summary && !summary.enabled && <p className="payment-unavailable">Płatności przelewem nie są jeszcze dostępne.</p>}
        {summary?.enabled && !pending && summary.offer && (
          <section className="payment-offer">
            <div className="payment-offer-heading">
              <div><span className="payment-offer-tag">Płatność jednorazowa</span><strong>Premium</strong><small>Pełny dostęp na {summary.offer.premium_days} dni</small></div>
              <div className="payment-price"><strong>{money(summary.offer.amount_minor, summary.offer.currency).replace(/\s*zł$/, "")}</strong><span>zł / {summary.offer.premium_days} dni</span></div>
            </div>
            <ul className="payment-benefits">
              <li>Do 30 pełnych analiz partii AI miesięcznie</li>
              <li>Do 50 pytań do trenera RajkoAI miesięcznie</li>
              <li>Własne boty i komentarze AI podczas gry</li>
            </ul>
            <button type="button" disabled={busy} onClick={() => void createOrder()}>{busy ? "Tworzę zamówienie…" : "Pokaż dane do przelewu"}<span aria-hidden="true">→</span></button>
            <p className="payment-offer-note">Bez automatycznego odnowienia. Dostęp aktywujemy po zaksięgowaniu przelewu.</p>
          </section>
        )}
        {pending && (
          <section className="payment-instructions">
            <div className="payment-instructions-heading"><div><span>KROK 2 Z 2</span><h3>Wykonaj przelew</h3></div><span className="payment-status pending">Oczekuje na wpłatę</span></div>
            <p>Przelej dokładną kwotę i koniecznie wpisz poniższy kod w tytule.</p>
            <dl>
              <div><dt>Odbiorca</dt><dd>{pending.recipient}</dd></div>
              <div><dt>Numer rachunku</dt><dd><code>{spacedIban(pending.iban)}</code><button type="button" onClick={() => void copy(pending.iban, "iban")}>{copied === "iban" ? "Skopiowano" : "Kopiuj"}</button></dd></div>
              <div><dt>Kwota</dt><dd>{money(pending.amount_minor, pending.currency)}</dd></div>
              <div><dt>Tytuł</dt><dd><code>{pending.reference_code}</code><button type="button" onClick={() => void copy(pending.reference_code, "code")}>{copied === "code" ? "Skopiowano" : "Kopiuj"}</button></dd></div>
            </dl>
            <small>Premium zostanie włączone dopiero po potwierdzeniu wpływu na rachunek. Nie wysyłaj zrzutu ekranu jako dowodu wpłaty.</small>
            <button className="payment-refresh" type="button" disabled={busy} onClick={() => void refresh()}>{busy ? "Odświeżam…" : "Odśwież status"}</button>
          </section>
        )}
        {summary && summary.orders.length > 0 && (
          <section className="payment-history">
            <h3>Historia zamówień</h3>
            <div className="payment-table-wrap"><table><thead><tr><th>Kod</th><th>Data</th><th>Kwota</th><th>Status</th></tr></thead><tbody>
              {summary.orders.map((order) => <tr key={order.id}><td><code>{order.reference_code}</code></td><td>{new Date(order.created_at).toLocaleDateString("pl-PL")}</td><td>{money(order.amount_minor, order.currency)}</td><td><span className={`payment-status ${order.status}`}>{statusLabel[order.status]}</span></td></tr>)}
            </tbody></table></div>
          </section>
        )}
      </section>
    </div>
  );
}
