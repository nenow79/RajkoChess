import { useState, type FormEvent } from "react";

import { confirmPasswordReset, getAuthErrorMessage } from "../auth/api";

export default function ResetPasswordScreen() {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState(token ? "" : "W linku brakuje tokenu zmiany hasła.");
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!token) return;
    if (password !== confirmation) {
      setError("Hasła nie są takie same.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      const result = await confirmPasswordReset(token, password);
      setMessage(result.message);
      setPassword("");
      setConfirmation("");
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się zmienić hasła."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="reset-password-title">
        <div className="auth-brand" aria-hidden="true">♞</div>
        <p className="auth-eyebrow">RAJKO CHESS</p>
        <h1 id="reset-password-title">Ustaw nowe hasło</h1>
        {message ? (
          <div className="auth-result" aria-live="polite">
            <p className="auth-success">{message}</p>
            <a className="auth-submit auth-link" href="./">Przejdź do logowania</a>
          </div>
        ) : (
          <form className="auth-form" onSubmit={submit}>
            <label>
              Nowe hasło
              <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={10} maxLength={128} autoComplete="new-password" required disabled={!token} autoFocus />
            </label>
            <label>
              Powtórz nowe hasło
              <input type="password" value={confirmation} onChange={(event) => setConfirmation(event.target.value)} minLength={10} maxLength={128} autoComplete="new-password" required disabled={!token} />
            </label>
            <p className="auth-hint">Hasło musi mieć co najmniej 10 znaków i nie może należeć do najczęściej używanych.</p>
            {error && <p className="auth-error" role="alert">{error}</p>}
            <button className="auth-submit" type="submit" disabled={busy || !token}>{busy ? "Zmieniamy hasło…" : "Zmień hasło"}</button>
          </form>
        )}
      </section>
    </main>
  );
}
