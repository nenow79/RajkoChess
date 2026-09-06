import { useEffect, useState } from "react";

import { getAuthErrorMessage } from "../auth/api";
import { cancelAdminPaymentOrder, confirmAdminPaymentOrder, getAdminPaymentOrders, type PaymentOrder } from "../billing/api";
import {
  getAdminStatistics,
  getBotStrengthSetting,
  getAdminUsers,
  grantPremium,
  revokePremium,
  updateBotStrengthSetting,
  type AdminStatistics,
  type AdminUser,
  type BotStrengthSetting,
} from "../admin/api";
import AdminSupportView from "./AdminSupportView";

interface AdminPanelProps {
  onClose: () => void;
  supportUnreadCount: number;
  onSupportUnreadChange: (count: number) => void;
  initialView?: "statistics" | "support";
}

const usageLabels: Record<string, string> = {
  ai_game_review: "Analizy całej partii",
  ai_chat: "Pytania i tłumaczenia AI",
  ai_bot_draft: "Generowanie botów",
  ai_bot_commentary: "Komentarze w grze z botem",
};

const sourceLabels: Record<string, string> = {
  chesscom: "Chess.com",
  bot: "Bot",
  pgn: "PGN",
};

const formatNumber = (value: number) => new Intl.NumberFormat("pl-PL").format(value);

export default function AdminPanel({ onClose, supportUnreadCount, onSupportUnreadChange, initialView = "statistics" }: AdminPanelProps) {
  const [view, setView] = useState<"statistics" | "users" | "orders" | "support">(initialView);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [orders, setOrders] = useState<PaymentOrder[]>([]);
  const [statistics, setStatistics] = useState<AdminStatistics | null>(null);
  const [botStrength, setBotStrength] = useState<BotStrengthSetting | null>(null);
  const [loading, setLoading] = useState(true);
  const [busyUser, setBusyUser] = useState<string | null>(null);
  const [busySetting, setBusySetting] = useState(false);
  const [busyOrder, setBusyOrder] = useState<string | null>(null);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [userItems, stats, strengthSetting, paymentOrders] = await Promise.all([
        getAdminUsers(),
        getAdminStatistics(),
        getBotStrengthSetting(),
        getAdminPaymentOrders(),
      ]);
      setUsers(userItems);
      setStatistics(stats);
      setBotStrength(strengthSetting);
      setOrders(paymentOrders);
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się pobrać danych panelu."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    Promise.all([getAdminUsers(), getAdminStatistics(), getBotStrengthSetting(), getAdminPaymentOrders()])
      .then(([userItems, stats, strengthSetting, paymentOrders]) => {
        if (!active) return;
        setUsers(userItems);
        setStatistics(stats);
        setBotStrength(strengthSetting);
        setOrders(paymentOrders);
      })
      .catch((requestError) => {
        if (active) {
          setError(getAuthErrorMessage(requestError, "Nie udało się pobrać danych panelu."));
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, []);

  const givePremium = async (user: AdminUser) => {
    const rawDays = window.prompt("Na ile dni przyznać Premium?", "30");
    if (!rawDays) return;
    const days = Number(rawDays);
    if (!Number.isInteger(days) || days < 1 || days > 366) {
      setError("Liczba dni musi być całkowita i mieścić się w zakresie 1–366.");
      return;
    }
    const reason = window.prompt("Powód przyznania Premium:", "Dostęp do bety");
    if (!reason || reason.trim().length < 3) return;
    setBusyUser(user.id);
    setError("");
    try {
      await grantPremium(user.id, days, reason.trim());
      await load();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się przyznać Premium."));
    } finally {
      setBusyUser(null);
    }
  };

  const removePremium = async (user: AdminUser) => {
    const reason = window.prompt("Powód odebrania Premium:");
    if (!reason || reason.trim().length < 3) return;
    setBusyUser(user.id);
    setError("");
    try {
      await revokePremium(user.id, reason.trim());
      await load();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się odebrać Premium."));
    } finally {
      setBusyUser(null);
    }
  };

  const chartMax = Math.max(
    1,
    ...(statistics?.daily.flatMap((day) => [day.registrations, day.games, day.ai_operations]) ?? []),
  );

  const confirmOrder = async (order: PaymentOrder) => {
    const reason = window.prompt(`Potwierdź wpływ ${order.reference_code}. Notatka:`, "Wpłata widoczna na rachunku");
    if (!reason || reason.trim().length < 3) return;
    setBusyOrder(order.id);
    setError("");
    try {
      await confirmAdminPaymentOrder(order.id, reason.trim());
      await load();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się potwierdzić zamówienia."));
    } finally {
      setBusyOrder(null);
    }
  };

  const cancelOrder = async (order: PaymentOrder) => {
    const reason = window.prompt(`Powód anulowania ${order.reference_code}:`, "Nie odnaleziono wpłaty");
    if (!reason || reason.trim().length < 3) return;
    setBusyOrder(order.id);
    setError("");
    try {
      await cancelAdminPaymentOrder(order.id, reason.trim());
      await load();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się anulować zamówienia."));
    } finally {
      setBusyOrder(null);
    }
  };

  const saveBotStrength = async () => {
    if (!botStrength) return;
    const value = botStrength.bot_global_elo_offset;
    if (!Number.isInteger(value) || value < botStrength.minimum || value > botStrength.maximum) {
      setError(`Korekta musi być liczbą całkowitą od ${botStrength.minimum} do ${botStrength.maximum}.`);
      return;
    }
    const reason = window.prompt("Powód zmiany globalnej siły botów:", "Kalibracja na podstawie feedbacku");
    if (!reason || reason.trim().length < 3) return;
    setBusySetting(true);
    setError("");
    try {
      setBotStrength(await updateBotStrengthSetting(value, reason.trim()));
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się zapisać siły botów."));
    } finally {
      setBusySetting(false);
    }
  };

  return (
    <div className="admin-overlay" role="dialog" aria-modal="true" aria-labelledby="admin-title">
      <section className="admin-panel">
        <header>
          <div><p className="auth-eyebrow">ADMINISTRACJA</p><h2 id="admin-title">Panel zamkniętej bety</h2></div>
          <button type="button" onClick={onClose} aria-label="Zamknij">×</button>
        </header>
        <nav className="admin-tabs" aria-label="Sekcje panelu">
          <button className={view === "statistics" ? "active" : ""} type="button" onClick={() => setView("statistics")}>Statystyki</button>
          <button className={view === "users" ? "active" : ""} type="button" onClick={() => setView("users")}>Użytkownicy</button>
          <button className={view === "orders" ? "active" : ""} type="button" onClick={() => setView("orders")}>Zamówienia{orders.some(order => order.status === "pending") ? ` (${orders.filter(order => order.status === "pending").length})` : ""}</button>
          <button className={view === "support" ? "active" : ""} type="button" onClick={() => setView("support")}>Zgłoszenia{supportUnreadCount > 0 && <i className="notification-badge">{supportUnreadCount > 99 ? "99+" : supportUnreadCount}</i>}</button>
          <button className="admin-refresh" type="button" disabled={loading} onClick={() => void load()}>Odśwież</button>
        </nav>
        {error && <p className="auth-error" role="alert">{error}</p>}
        {loading ? <p>Ładowanie danych…</p> : view === "statistics" && statistics ? (
          <div className="admin-dashboard">
            <div className="admin-metric-grid">
              <article><span>Konta</span><strong>{formatNumber(statistics.users.total)}</strong><small>{statistics.users.verified} zweryfikowanych</small></article>
              <article><span>Aktywni 7 dni</span><strong>{formatNumber(statistics.users.active_7d)}</strong><small>{statistics.users.active_30d} w ciągu 30 dni</small></article>
              <article><span>Zapisane partie</span><strong>{formatNumber(statistics.games.total)}</strong><small>{statistics.games.users} użytkowników</small></article>
              <article><span>Import → analiza</span><strong>{statistics.games.analysis_rate.toLocaleString("pl-PL")}%</strong><small>{statistics.games.analyzed} analizowanych partii</small></article>
              <article><span>Operacje AI · 30 dni</span><strong>{formatNumber(statistics.ai.operations)}</strong><small>{statistics.ai.users} użytkowników</small></article>
              <article><span>Koszt OpenRouter · 30 dni</span><strong>{statistics.ai.openrouter_cost_credits.toLocaleString("pl-PL", { maximumFractionDigits: 4 })}</strong><small>{formatNumber(statistics.ai.total_tokens)} tokenów</small></article>
            </div>

            <section className="admin-stat-section">
              <h3>Ostatnie 14 dni</h3>
              <div className="admin-chart-legend"><span className="registrations">Rejestracje</span><span className="games">Partie</span><span className="ai">AI</span></div>
              <div className="admin-mini-chart">
                {statistics.daily.map((day) => (
                  <div className="admin-chart-day" key={day.date} title={`${day.date}: rejestracje ${day.registrations}, partie ${day.games}, AI ${day.ai_operations}`}>
                    <div className="admin-chart-bars">
                      <i className="registrations" style={{ height: `${(day.registrations / chartMax) * 100}%` }} />
                      <i className="games" style={{ height: `${(day.games / chartMax) * 100}%` }} />
                      <i className="ai" style={{ height: `${(day.ai_operations / chartMax) * 100}%` }} />
                    </div>
                    <time>{new Date(`${day.date}T00:00:00`).toLocaleDateString("pl-PL", { day: "2-digit", month: "2-digit" })}</time>
                  </div>
                ))}
              </div>
            </section>

            <div className="admin-stat-columns">
              <section className="admin-stat-section">
                <h3>Wykorzystanie AI · 30 dni</h3>
                {statistics.ai.by_key.length ? statistics.ai.by_key.map((item) => (
                  <div className="admin-stat-row" key={item.key}><span>{usageLabels[item.key] || item.key}<small>{item.users} użytkowników</small></span><strong>{formatNumber(item.operations)}</strong></div>
                )) : <p className="admin-empty">Brak użycia AI w tym okresie.</p>}
              </section>
              <section className="admin-stat-section">
                <h3>Partie i rozmowy</h3>
                {statistics.games.by_source.map((item) => (
                  <div className="admin-stat-row" key={item.source}><span>{sourceLabels[item.source] || item.source}</span><strong>{formatNumber(item.count)}</strong></div>
                ))}
                <div className="admin-stat-row"><span>Pełne analizy</span><strong>{formatNumber(statistics.games.analyses)}</strong></div>
                <div className="admin-stat-row"><span>Wiadomości czatu</span><strong>{formatNumber(statistics.games.chat_messages)}</strong></div>
              </section>
            </div>
            <p className="admin-data-note">Aktywność jest przybliżona na podstawie ostatniego użycia sesji. Panel pokazuje wyłącznie agregaty z PostgreSQL, bez danych z logów nginx.</p>
          </div>
        ) : view === "users" ? (
          <>
            {botStrength && <section className="admin-settings-card"><div><h3>Globalna siła botów</h3><p>Korekta jest odejmowana lub dodawana do Elo każdego bota. Zmiana obejmie nowe partie bez restartu aplikacji.</p><small>Źródło: {botStrength.source === "database" ? "panel administratora" : "konfiguracja środowiska"}</small></div><label>Korekta Elo<input type="number" min={botStrength.minimum} max={botStrength.maximum} step="10" value={botStrength.bot_global_elo_offset} onChange={event => setBotStrength({ ...botStrength, bot_global_elo_offset: Number(event.target.value) })} /></label><button type="button" disabled={busySetting} onClick={() => void saveBotStrength()}>{busySetting ? "Zapisuję…" : "Zapisz"}</button></section>}
            <p className="admin-note">Przyznanie kolejnego okresu przedłuża aktywne Premium. Po terminie konto automatycznie wraca do Free.</p>
            <div className="admin-user-list">
              {users.map((user) => (
                <article className="admin-user-row" key={user.id}>
                  <div><strong>{user.display_name || user.email}</strong>{user.display_name && <small>{user.email}</small>}<small>{user.system_role === "admin" ? "Administrator" : "Użytkownik"}</small></div>
                  <div className={`plan-badge ${user.plan?.base_plan || "free"}`}>{user.system_role === "admin" ? "ADMIN" : (user.plan?.base_plan || "free").toUpperCase()}{user.plan?.expires_at && <small>do {new Date(user.plan.expires_at).toLocaleDateString("pl-PL")}</small>}</div>
                  <div className="admin-user-actions">
                    {user.system_role !== "admin" && <button type="button" disabled={busyUser === user.id} onClick={() => void givePremium(user)}>{user.plan?.base_plan === "premium" ? "Przedłuż" : "Przyznaj Premium"}</button>}
                    {user.system_role !== "admin" && user.plan?.base_plan === "premium" && <button className="danger-action" type="button" disabled={busyUser === user.id} onClick={() => void removePremium(user)}>Odbierz</button>}
                  </div>
                </article>
              ))}
            </div>
          </>
        ) : view === "orders" ? (
          <section className="admin-orders">
            <p className="admin-note">Potwierdzaj zamówienie wyłącznie po zaksięgowaniu przelewu na rachunku. Potwierdzenie automatycznie przedłuża Premium.</p>
            <div className="payment-table-wrap"><table><thead><tr><th>Kod</th><th>Użytkownik</th><th>Utworzono</th><th>Kwota</th><th>Status</th><th>Akcje</th></tr></thead><tbody>
              {orders.map((order) => (
                <tr key={order.id}>
                  <td><code>{order.reference_code}</code></td>
                  <td>{order.user_email}</td>
                  <td>{new Date(order.created_at).toLocaleString("pl-PL")}</td>
                  <td>{new Intl.NumberFormat("pl-PL", { style: "currency", currency: order.currency }).format(order.amount_minor / 100)}</td>
                  <td><span className={`payment-status ${order.status}`}>{order.status === "pending" ? "Oczekuje" : order.status === "paid" ? "Opłacone" : "Anulowane"}</span></td>
                  <td>{order.status === "pending" && <div className="admin-order-actions"><button type="button" disabled={busyOrder === order.id} onClick={() => void confirmOrder(order)}>Potwierdź</button><button className="danger-action" type="button" disabled={busyOrder === order.id} onClick={() => void cancelOrder(order)}>Anuluj</button></div>}</td>
                </tr>
              ))}
              {!orders.length && <tr><td colSpan={6} className="admin-empty">Brak zamówień.</td></tr>}
            </tbody></table></div>
          </section>
        ) : view === "support" ? (
          <AdminSupportView onUnreadChange={onSupportUnreadChange} />
        ) : null}
      </section>
    </div>
  );
}
