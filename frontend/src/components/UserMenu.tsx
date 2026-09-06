import { useCallback, useEffect, useRef, useState } from "react";

import { getAuthErrorMessage } from "../auth/api";
import { useAuth } from "../auth/useAuth";
import { getMyPlan, type PlanSummary } from "../admin/api";
import AdminPanel from "./AdminPanel";
import AccountSettings from "./AccountSettings";
import PaymentDialog from "./PaymentDialog";
import SupportDialog from "./SupportDialog";
import { getAdminSupportUnreadCount, getSupportUnreadCount } from "../support/api";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const menuRef = useRef<HTMLDivElement>(null);
  const initialGoogleResult = new URLSearchParams(window.location.search).get("google_auth");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(() => ({
    email_mismatch: "Wybrane konto Google ma inny adres e-mail.",
    identity_conflict: "To konto Google jest już połączone z innym kontem.",
    link_requires_login: "Sesja wygasła przed podłączeniem Google.",
  } as Record<string, string>)[initialGoogleResult || ""] || "");
  const [notice] = useState(() => initialGoogleResult === "linked" ? "Konto Google zostało podłączone." : "");
  const [plan, setPlan] = useState<PlanSummary | null>(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [adminInitialView, setAdminInitialView] = useState<"statistics" | "support">("statistics");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [paymentsOpen, setPaymentsOpen] = useState(false);
  const [supportOpen, setSupportOpen] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [supportUnreadCount, setSupportUnreadCount] = useState(0);
  const [adminSupportUnreadCount, setAdminSupportUnreadCount] = useState(0);

  const loadPlan = useCallback(
    () => getMyPlan().then(setPlan).catch(() => setPlan(null)),
    [],
  );

  useEffect(() => {
    void loadPlan();
    const url = new URL(window.location.href);
    const googleResult = url.searchParams.get("google_auth");
    if (googleResult) {
      url.searchParams.delete("google_auth");
      window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
    }
  }, [loadPlan]);

  const loadUnreadCounts = useCallback(() => {
    void getSupportUnreadCount().then(setSupportUnreadCount).catch(() => undefined);
    if (user?.system_role === "admin") {
      void getAdminSupportUnreadCount().then(setAdminSupportUnreadCount).catch(() => undefined);
    }
  }, [user?.system_role]);

  useEffect(() => {
    loadUnreadCounts();
    const timer = window.setInterval(loadUnreadCounts, 60_000);
    return () => window.clearInterval(timer);
  }, [loadUnreadCounts]);

  useEffect(() => {
    if (!accountMenuOpen && !planOpen) return;
    const closeOutside = (event: PointerEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setAccountMenuOpen(false);
        setPlanOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setAccountMenuOpen(false);
        setPlanOpen(false);
      }
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [accountMenuOpen, planOpen]);

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
    <div className="user-menu" ref={menuRef}>
      <button
        className="support-icon-button"
        type="button"
        title={user.system_role === "admin" ? "Zgłoszenia użytkowników" : "Pomoc i pomysły"}
        aria-label={user.system_role === "admin"
          ? `Zgłoszenia użytkowników${adminSupportUnreadCount ? `, ${adminSupportUnreadCount} nieprzeczytanych wiadomości` : ""}`
          : `Pomoc i pomysły${supportUnreadCount ? `, ${supportUnreadCount} nieprzeczytanych wiadomości` : ""}`}
        onClick={() => {
          setAccountMenuOpen(false);
          setPlanOpen(false);
          if (user.system_role === "admin") {
            setAdminInitialView("support");
            setAdminOpen(true);
          } else {
            setSupportOpen(true);
          }
        }}
      >
        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none">
          <path d="M4.5 6.75h15v10.5h-15z" />
          <path d="m5 7.25 7 5.5 7-5.5" />
        </svg>
        {(user.system_role === "admin" ? adminSupportUnreadCount : supportUnreadCount) > 0 && (
          <i className="notification-badge">
            {(user.system_role === "admin" ? adminSupportUnreadCount : supportUnreadCount) > 99
              ? "99+"
              : user.system_role === "admin" ? adminSupportUnreadCount : supportUnreadCount}
          </i>
        )}
      </button>
      <button
        type="button"
        className="user-account-trigger"
        aria-haspopup="menu"
        aria-expanded={accountMenuOpen}
        onClick={() => {
          setPlanOpen(false);
          setAccountMenuOpen((open) => !open);
        }}
      >
        <span className="user-avatar" aria-hidden="true">{(user.display_name || user.email).charAt(0).toUpperCase()}</span>
        <span className="user-identity"><strong>{user.display_name || user.email}</strong>{user.display_name && <small>{user.email}</small>}</span>
        <span className="user-menu-chevron" aria-hidden="true">⌄</span>
      </button>
      <button
        type="button"
        className={`user-plan-pill ${plan?.base_plan || "free"}`}
        title={plan?.expires_at ? `Premium do ${new Date(plan.expires_at).toLocaleDateString("pl-PL")}` : "Pokaż wykorzystanie planu"}
        onClick={() => {
          const nextOpen = !planOpen;
          setAccountMenuOpen(false);
          setPlanOpen(nextOpen);
          if (nextOpen) void loadPlan();
        }}
      >
        {(plan?.key || "free").toUpperCase()}
      </button>
      {plan?.key === "free" && <button className="premium-upgrade-cta" type="button" title="Premium na 30 dni — płatność jednorazowa" onClick={() => { setAccountMenuOpen(false); setPlanOpen(false); setPaymentsOpen(true); }}><span aria-hidden="true">♛</span> Kup Premium · 10 zł</button>}
      {accountMenuOpen && (
        <div className="user-account-popover" role="menu">
          <div className="user-account-popover-heading"><strong>{user.display_name || "Twoje konto"}</strong><small>{user.email}</small></div>
          <button type="button" role="menuitem" onClick={() => { setAccountMenuOpen(false); setPlanOpen(true); void loadPlan(); }}><span aria-hidden="true">◔</span> Wykorzystanie planu</button>
          <button type="button" role="menuitem" onClick={() => { setAccountMenuOpen(false); setSettingsOpen(true); }}><span aria-hidden="true">⚙</span> Ustawienia konta</button>
          {user.system_role === "admin" && <button type="button" role="menuitem" onClick={() => { setAccountMenuOpen(false); setAdminInitialView("statistics"); setAdminOpen(true); }}><span aria-hidden="true">▦</span> Administracja{adminSupportUnreadCount > 0 && <i className="notification-badge menu-badge">{adminSupportUnreadCount > 99 ? "99+" : adminSupportUnreadCount}</i>}</button>}
          <div className="user-account-menu-separator" />
          <button className="logout-action" type="button" role="menuitem" onClick={handleLogout} disabled={busy}><span aria-hidden="true">↪</span> {busy ? "Wylogowywanie…" : "Wyloguj"}</button>
        </div>
      )}
      {error && <span className="user-menu-error" role="alert">{error}</span>}
      {notice && <span className="user-menu-notice" role="status">{notice}</span>}
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
          {plan.key !== "admin" && <button className="plan-buy-button" type="button" onClick={() => { setPlanOpen(false); setPaymentsOpen(true); }}>Kup Premium</button>}
        </div>
      )}
      {adminOpen && <AdminPanel onClose={() => { setAdminOpen(false); loadUnreadCounts(); }} supportUnreadCount={adminSupportUnreadCount} onSupportUnreadChange={setAdminSupportUnreadCount} initialView={adminInitialView} />}
      {settingsOpen && <AccountSettings onClose={() => setSettingsOpen(false)} />}
      {paymentsOpen && <PaymentDialog onClose={() => { setPaymentsOpen(false); void loadPlan(); }} />}
      {supportOpen && <SupportDialog onClose={() => { setSupportOpen(false); loadUnreadCounts(); }} onUnreadChange={setSupportUnreadCount} />}
    </div>
  );
}
