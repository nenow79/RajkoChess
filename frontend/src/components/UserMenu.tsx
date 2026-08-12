import { useState } from "react";

import { getAuthErrorMessage } from "../auth/api";
import { useAuth } from "../auth/useAuth";

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

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
      <button type="button" onClick={handleLogout} disabled={busy}>{busy ? "Wylogowywanie…" : "Wyloguj"}</button>
      {error && <span className="user-menu-error" role="alert">{error}</span>}
    </div>
  );
}

