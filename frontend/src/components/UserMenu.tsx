import { useCallback, useEffect, useState } from "react";

import { getAuthErrorMessage } from "../auth/api";
import { useAuth } from "../auth/useAuth";
import { getMyPlan, type PlanSummary } from "../admin/api";
import AdminPanel from "./AdminPanel";
import AccountSettings from "./AccountSettings";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [plan, setPlan] = useState<PlanSummary | null>(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const loadPlan = useCallback(
    () => getMyPlan().then(setPlan).catch(() => setPlan(null)),
    [],
  );

  useEffect(() => {
    void loadPlan();
  }, [loadPlan]);

  if (!user) return null;

  const handleLogout = async () => {
    setBusy(true);
    setError("");
    try {
      await logout();
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wylogować."));
      setBusy(false);
    }
  };

  return (
    <div className="user-menu">
      <div className="user-identity">
        <span className="user-avatar" aria-hidden="true">{(user.display_name || user.email).charAt(0).toUpperCase()}</span>
        <span><strong>{user.display_name || user.email}</strong>{user.display_name && <small>{user.email}</small>}</span>
      </div>
      <button
        type="button"
        className={`user-plan-pill ${plan?.base_plan || "free"}`}
        title={plan?.expires_at ? `Premium do ${new Date(plan.expires_at).toLocaleDateString("pl-PL")}` : "Pokaż wykorzystanie planu"}
        onClick={() => {
          const nextOpen = !planOpen;
          setPlanOpen(nextOpen);
          if (nextOpen) void loadPlan();
        }}
      >
        {(plan?.key || "free").toUpperCase()}
      </button>
      {user.system_role === "admin" && <button type="button" onClick={() => setAdminOpen(true)}>Administracja</button>}
      <button type="button" onClick={() => setSettingsOpen(true)}>Ustawienia</button>
      <button type="button" onClick={handleLogout} disabled={busy}>{busy ? "Wylogowywanie…" : "Wyloguj"}</button>
      {error && <span className="user-menu-error" role="alert">{error}</span>}
      {planOpen && plan && (
        <div className="plan-usage-popover">
          <strong>Wykorzystanie w tym miesiącu</strong>
          {Object.entries(plan.usage).map(([key, value]) => (
            <div key={key}>
              <span>{({ ai_game_review: "Analizy partii AI", ai_chat: "Pytania do trenera", ai_bot_draft: "Generowanie botów", ai_bot_commentary: "Komentarze podczas gry" } as Record<string, string>)[key] || key}</span>
              <b>{value.used} / {value.limit ?? "∞"}</b>
            </div>
          ))}
          {plan.expires_at && <small>Premium do {new Date(plan.expires_at).toLocaleDateString("pl-PL")}</small>}
        </div>
      )}
      {adminOpen && <AdminPanel onClose={() => setAdminOpen(false)} />}
      {settingsOpen && <AccountSettings onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
