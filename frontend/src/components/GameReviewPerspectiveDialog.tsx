import { useState } from "react";

import type { PlayerColor } from "../types";

export type GameReviewFocus = PlayerColor | "both";
export type GameReviewStyle = "freestyle" | "grounded";

interface GameReviewPerspectiveDialogProps {
  defaultFocus?: PlayerColor;
  whitePlayerName?: string;
  blackPlayerName?: string;
  onClose: () => void;
  onConfirm: (focus: GameReviewFocus, style: GameReviewStyle) => void;
}

export default function GameReviewPerspectiveDialog({
  defaultFocus,
  whitePlayerName,
  blackPlayerName,
  onClose,
  onConfirm,
}: GameReviewPerspectiveDialogProps) {
  const [focus, setFocus] = useState<GameReviewFocus | null>(defaultFocus ?? null);
  const [style, setStyle] = useState<GameReviewStyle>("grounded");
  const options: Array<{ value: GameReviewFocus; title: string; description: string }> = [
    {
      value: "white",
      title: `Białych${whitePlayerName ? ` (${whitePlayerName})` : ""}`,
      description: "Błędy i dobre decyzje białych.",
    },
    {
      value: "black",
      title: `Czarnych${blackPlayerName ? ` (${blackPlayerName})` : ""}`,
      description: "Błędy i dobre decyzje czarnych.",
    },
    { value: "both", title: "Obu stron", description: "Neutralny opis najważniejszych zwrotów." },
  ];

  return (
    <div className="game-review-focus-overlay" onMouseDown={onClose}>
      <section
        className="game-review-focus-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="game-review-focus-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header>
          <div>
            <p className="auth-eyebrow">RAJKOAI</p>
            <h2 id="game-review-focus-title">Jak analizujemy partię?</h2>
            <p>Wybierz perspektywę i styl analizy trenera.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="Zamknij">×</button>
        </header>
        <fieldset>
          <legend>Perspektywa analizy</legend>
          {options.map((option) => (
            <label key={option.value} className={focus === option.value ? "selected" : ""}>
              <input
                type="radio"
                name="game-review-focus"
                value={option.value}
                checked={focus === option.value}
                onChange={() => setFocus(option.value)}
              />
              <span><strong>{option.title}</strong><small>{option.description}</small></span>
            </label>
          ))}
        </fieldset>
        {!defaultFocus && <p className="game-review-focus-note">Kolor gracza nie był dostępny — wybór jest wymagany.</p>}
        <fieldset>
          <legend>Styl analizy</legend>
          <label className={style === "freestyle" ? "selected" : ""}>
            <input type="radio" name="game-review-style" value="freestyle" checked={style === "freestyle"} onChange={() => setStyle("freestyle")} />
            <span>
              <strong>Epicka — freestyle</strong>
              <small>Swobodna opowieść o partii, jej zwrotach i pomysłach graczy.</small>
              <small><em>AI może czasem błędnie opisać pozycję lub wariant — mogą pojawić się halucynacje.</em></small>
            </span>
          </label>
          <label className={style === "grounded" ? "selected" : ""}>
            <input type="radio" name="game-review-style" value="grounded" checked={style === "grounded"} onChange={() => setStyle("grounded")} />
            <span>
              <strong>Uporządkowana — oparta na danych silnika</strong>
              <small>Kluczowe momenty, komentarze i warianty sprawdzane przez Stockfisha.</small>
            </span>
          </label>
        </fieldset>
        <footer>
          <button type="button" onClick={onClose}>Anuluj</button>
          <button type="button" disabled={!focus} onClick={() => focus && onConfirm(focus, style)}>
            Analizuj partię
          </button>
        </footer>
      </section>
    </div>
  );
}
