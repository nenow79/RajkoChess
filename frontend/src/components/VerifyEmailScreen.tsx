import { useEffect, useState } from "react";

import { confirmEmail, getAuthErrorMessage } from "../auth/api";

type VerificationState = "verifying" | "success" | "error";

export default function VerifyEmailScreen() {
  const token = new URLSearchParams(window.location.search).get("token") || "";
  const [state, setState] = useState<VerificationState>(token ? "verifying" : "error");
  const [message, setMessage] = useState(
    token ? "Potwierdzamy Twój adres e-mail…" : "W linku brakuje tokenu potwierdzającego.",
  );

  useEffect(() => {
    if (!token) return;

    let active = true;
    confirmEmail(token)
      .then((result) => {
        if (!active) return;
        setState("success");
        setMessage(result.message);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState("error");
        setMessage(getAuthErrorMessage(error, "Nie udało się potwierdzić adresu e-mail."));
      });
    return () => { active = false; };
  }, [token]);

  return (
    <main className="auth-page">
      <section className="auth-card auth-result" aria-live="polite">
        <div className="auth-brand" aria-hidden="true">♞</div>
        <p className="auth-eyebrow">RAJKO CHESS</p>
        <h1>{state === "success" ? "E-mail potwierdzony" : state === "error" ? "Nie udało się potwierdzić" : "Chwila…"}</h1>
        <p className={state === "error" ? "auth-error" : "auth-intro"}>{message}</p>
        {state !== "verifying" && <a className="auth-submit auth-link" href="./">Przejdź do logowania</a>}
      </section>
    </main>
  );
}
