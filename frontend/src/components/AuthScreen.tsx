import { useState, type FormEvent } from "react";
import axios from "axios";

import { getAuthErrorMessage, resendVerificationEmail } from "../auth/api";
import { useAuth } from "../auth/useAuth";

type AuthMode = "login" | "register";

export default function AuthScreen() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [verificationEmail, setVerificationEmail] = useState("");
  const [resendMessage, setResendMessage] = useState("");

  const changeMode = (nextMode: AuthMode) => {
    setMode(nextMode);
    setError("");
    setPassword("");
    setPasswordConfirmation("");
    setVerificationEmail("");
    setResendMessage("");
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (mode === "register" && password !== passwordConfirmation) {
      setError("Hasła nie są takie same.");
      return;
    }

    setBusy(true);
    setError("");
    try {
      if (mode === "login") {
        await login({ email: email.trim(), password });
      } else {
        await register({ email: email.trim(), password, displayName });
        setVerificationEmail(email.trim());
      }
    } catch (requestError) {
      const detail = axios.isAxiosError(requestError) ? requestError.response?.data?.detail : null;
      if (mode === "register" && requestError && axios.isAxiosError(requestError) && requestError.response?.status === 503) {
        setVerificationEmail(email.trim());
      } else if (mode === "login" && requestError && axios.isAxiosError(requestError) && requestError.response?.status === 403 && typeof detail === "string" && detail.includes("Potwierdź adres e-mail")) {
        setVerificationEmail(email.trim());
      }
      setError(getAuthErrorMessage(
        requestError,
        mode === "login" ? "Nie udało się zalogować." : "Nie udało się utworzyć konta.",
      ));
    } finally {
      setBusy(false);
    }
  };

  const resend = async () => {
    setBusy(true);
    setError("");
    setResendMessage("");
    try {
      const result = await resendVerificationEmail(verificationEmail);
      setResendMessage(result.message);
    } catch (requestError) {
      setError(getAuthErrorMessage(requestError, "Nie udało się wysłać nowego linku."));
    } finally {
      setBusy(false);
    }
  };

  if (verificationEmail) {
    return (
      <main className="auth-page">
        <section className="auth-card auth-result" aria-live="polite">
          <div className="auth-brand" aria-hidden="true">♞</div>
          <p className="auth-eyebrow">RAJKO CHESS</p>
          <h1>Sprawdź swoją pocztę</h1>
          <p className="auth-intro">Wysłaliśmy link potwierdzający na <strong>{verificationEmail}</strong>. Po potwierdzeniu wróć tutaj i zaloguj się.</p>
          {resendMessage && <p className="auth-success">{resendMessage}</p>}
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="button" disabled={busy} onClick={resend}>{busy ? "Wysyłamy…" : "Wyślij link ponownie"}</button>
          <button className="auth-secondary" type="button" onClick={() => changeMode("login")}>Wróć do logowania</button>
        </section>
      </main>
    );
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-brand" aria-hidden="true">♞</div>
        <p className="auth-eyebrow">RAJKO CHESS</p>
        <h1 id="auth-title">{mode === "login" ? "Witaj ponownie" : "Utwórz konto"}</h1>
        <p className="auth-intro">
          {mode === "login"
            ? "Zaloguj się, aby przejść do swojej szachownicy i treningu."
            : "Załóż konto, aby zachować ciągłość swojej pracy z trenerem."}
        </p>

        <div className="auth-tabs" role="tablist" aria-label="Dostęp do konta">
          <button type="button" role="tab" aria-selected={mode === "login"} className={mode === "login" ? "active" : ""} onClick={() => changeMode("login")}>Logowanie</button>
          <button type="button" role="tab" aria-selected={mode === "register"} className={mode === "register" ? "active" : ""} onClick={() => changeMode("register")}>Rejestracja</button>
        </div>

        <form className="auth-form" onSubmit={submit}>
          {mode === "register" && (
            <label>
              Nazwa wyświetlana <span>opcjonalnie</span>
              <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} maxLength={80} autoComplete="nickname" />
            </label>
          )}
          <label>
            Adres e-mail
            <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required autoFocus />
          </label>
          <label>
            Hasło
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} minLength={mode === "register" ? 10 : 1} maxLength={128} autoComplete={mode === "login" ? "current-password" : "new-password"} required />
          </label>
          {mode === "register" && (
            <label>
              Powtórz hasło
              <input type="password" value={passwordConfirmation} onChange={(event) => setPasswordConfirmation(event.target.value)} minLength={10} maxLength={128} autoComplete="new-password" required />
            </label>
          )}
          {mode === "register" && <p className="auth-hint">Hasło musi mieć co najmniej 10 znaków i nie może należeć do najczęściej używanych.</p>}
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="auth-submit" type="submit" disabled={busy}>
            {busy ? "Proszę czekać…" : mode === "login" ? "Zaloguj się" : "Utwórz konto"}
          </button>
        </form>
      </section>
    </main>
  );
}
