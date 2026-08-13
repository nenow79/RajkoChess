import { useEffect, useState } from "react";

import { getAuthErrorMessage } from "../auth/api";
import { useAuth } from "../auth/useAuth";
import { getMyPlan, type PlanSummary } from "../admin/api";
import AdminPanel from "./AdminPanel";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [plan, setPlan] = useState<PlanSummary | null>(null);
  const [adminOpen, setAdminOpen] = useState(false);

  useEffect(() => {
    getMyPlan().then(setPlan).catch(() => setPlan(null));
  }, []);

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
      <span className={`user-plan-pill ${plan?.base_plan || "free"}`} title={plan?.expires_at ? `Premium do ${new Date(plan.expires_at).toLocaleDateString("pl-PL")}` : undefined}>{(plan?.key || "free").toUpperCase()}</span>
      {user.system_role === "admin" && <button type="button" onClick={() => setAdminOpen(true)}>Administracja</button>}
      <button type="button" onClick={handleLogout} disabled={busy}>{busy ? "Wylogowywanie…" : "Wyloguj"}</button>
      {error && <span className="user-menu-error" role="alert">{error}</span>}
      {adminOpen && <AdminPanel onClose={() => setAdminOpen(false)} />}
    </div>
  );
}
