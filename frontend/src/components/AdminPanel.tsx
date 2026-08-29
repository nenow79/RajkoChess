import { useEffect, useState } from "react";

import { getAuthErrorMessage } from "../auth/api";
import {
  getBotStrengthSetting,
  getAdminUsers,
  grantPremium,
  revokePremium,
  updateBotStrengthSetting,
  type AdminUser,
  type BotStrengthSetting,
} from "../admin/api";

interface AdminPanelProps {
  onClose: () => void;
}

export default function AdminPanel({ onClose }: AdminPanelProps) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyUser, setBusyUser] = useState<string | null>(null);
  const [botStrength, setBotStrength] = useState<BotStrengthSetting | null>(null);
  const [busySetting, setBusySetting] = useState(false);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [userItems, strengthSetting] = await Promise.all([
        getAdminUsers(),
        getBotStrengthSetting(),
      ]);
      setUsers(userItems);
      setBotStrength(strengthSetting);
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się pobrać użytkowników."));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    let active = true;
    Promise.all([getAdminUsers(), getBotStrengthSetting()])
      .then(([items, strengthSetting]) => {
        if (active) {
          setUsers(items);
          setBotStrength(strengthSetting);
        }
      })
      .catch((requestError) => {
        if (active) setError(getAuthErrorMessage(requestError, "Nie udało się pobrać użytkowników."));
      })
      .finally(() => { if (active) setLoading(false); });
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
          <div><p className="auth-eyebrow">ADMINISTRACJA</p><h2 id="admin-title">Ustawienia i użytkownicy</h2></div>
          <button type="button" onClick={onClose} aria-label="Zamknij">×</button>
        </header>
        {botStrength && <section className="admin-settings-card"><div><h3>Globalna siła botów</h3><p>Korekta jest odejmowana lub dodawana do Elo każdego bota. Zmiana obejmie nowe partie bez restartu aplikacji.</p><small>Źródło: {botStrength.source === "database" ? "panel administratora" : "konfiguracja środowiska"}</small></div><label>Korekta Elo<input type="number" min={botStrength.minimum} max={botStrength.maximum} step="10" value={botStrength.bot_global_elo_offset} onChange={event => setBotStrength({ ...botStrength, bot_global_elo_offset: Number(event.target.value) })} /></label><button type="button" disabled={busySetting} onClick={() => void saveBotStrength()}>{busySetting ? "Zapisuję…" : "Zapisz"}</button></section>}
        <p className="admin-note">Przyznanie kolejnego okresu przedłuża aktywne Premium. Po terminie konto automatycznie wraca do Free.</p>
        {error && <p className="auth-error" role="alert">{error}</p>}
        {loading ? <p>Ładowanie użytkowników…</p> : (
          <div className="admin-user-list">
            {users.map((user) => (
              <article className="admin-user-row" key={user.id}>
                <div>
                  <strong>{user.display_name || user.email}</strong>
                  {user.display_name && <small>{user.email}</small>}
                  <small>{user.system_role === "admin" ? "Administrator" : "Użytkownik"}</small>
                </div>
                <div className={`plan-badge ${user.plan?.base_plan || "free"}`}>
                  {user.system_role === "admin" ? "ADMIN" : (user.plan?.base_plan || "free").toUpperCase()}
                  {user.plan?.expires_at && <small>do {new Date(user.plan.expires_at).toLocaleDateString("pl-PL")}</small>}
                </div>
                <div className="admin-user-actions">
                  {user.system_role !== "admin" && <button type="button" disabled={busyUser === user.id} onClick={() => void givePremium(user)}>{user.plan?.base_plan === "premium" ? "Przedłuż" : "Przyznaj Premium"}</button>}
                  {user.system_role !== "admin" && user.plan?.base_plan === "premium" && <button className="danger-action" type="button" disabled={busyUser === user.id} onClick={() => void removePremium(user)}>Odbierz</button>}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
