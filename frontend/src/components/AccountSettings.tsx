import { useState, type FormEvent } from "react";

import { deletePlatformAccount, getAuthErrorMessage, savePlatformAccount } from "../auth/api";
import { useAuth } from "../auth/useAuth";

interface AccountSettingsProps {
  onClose: () => void;
}

export default function AccountSettings({ onClose }: AccountSettingsProps) {
  const { platformAccounts, refreshPlatformAccounts } = useAuth();
  const savedChessCom = platformAccounts.find((account) => account.provider === "chesscom")?.username || "";
  const [chessComUsername, setChessComUsername] = useState(savedChessCom);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      const normalized = chessComUsername.trim();
      if (normalized) {
        await savePlatformAccount("chesscom", normalized);
      } else {
        await deletePlatformAccount("chesscom");
      }
      await refreshPlatformAccounts();
      setSuccess(normalized ? "Zapisano domyślny login Chess.com." : "Usunięto domyślny login Chess.com.");
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się zapisać ustawień konta."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="account-settings-overlay" onMouseDown={onClose}>
      <section className="account-settings-card" role="dialog" aria-modal="true" aria-labelledby="account-settings-title" onMouseDown={(event) => event.stopPropagation()}>
        <header>
          <div>
            <h2 id="account-settings-title">Ustawienia konta</h2>
            <p>Zapisane loginy służą jako domyślne wartości podczas importu partii.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Zamknij ustawienia">×</button>
        </header>
        <form className="account-settings-form" onSubmit={handleSubmit}>
          <label>
            Login Chess.com
            <input
              type="text"
              value={chessComUsername}
              onChange={(event) => setChessComUsername(event.target.value.slice(0, 50))}
              maxLength={50}
              pattern="[A-Za-z0-9_-]+"
              placeholder="np. moj_login"
              autoComplete="off"
              disabled={busy}
            />
            <small>Możesz go nadal jednorazowo zmienić w oknie importu Chess.com.</small>
          </label>
          {error && <p className="account-settings-error" role="alert">{error}</p>}
          {success && <p className="account-settings-success" role="status">{success}</p>}
          <div className="account-settings-actions">
            <button type="button" onClick={onClose}>Anuluj</button>
            <button type="submit" disabled={busy}>{busy ? "Zapisywanie…" : "Zapisz"}</button>
          </div>
        </form>
      </section>
    </div>
  );
}
