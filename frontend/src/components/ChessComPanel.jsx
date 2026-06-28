import { useEffect, useRef, useState } from "react";

export default function ChessComPanel({
  username,
  games,
  isLoading,
  importedGame,
  onImport,
  onRefresh,
  onUsernameChange,
}) {
  const [draftUsername, setDraftUsername] = useState(username);
  const [isOpen, setIsOpen] = useState(false);
  const closeButtonRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return undefined;

    const handleKeyDown = (event) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    closeButtonRef.current?.focus();

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const formatDate = (value) => value
    ? new Intl.DateTimeFormat("pl-PL", { dateStyle: "short", timeStyle: "short" }).format(new Date(value))
    : "brak daty";

  const formatMoveCount = (count) => {
    if (count == null) return "";
    const lastTwoDigits = count % 100;
    const lastDigit = count % 10;
    const suffix = count === 1 ? "ruch" : lastDigit >= 2 && lastDigit <= 4
      && (lastTwoDigits < 12 || lastTwoDigits > 14) ? "ruchy" : "ruchów";
    return ` · ${count} ${suffix}`;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const normalizedUsername = draftUsername.trim();
    setDraftUsername(normalizedUsername);
    onUsernameChange(normalizedUsername);
  };

  const handleImport = (game) => {
    onImport(game);
    setIsOpen(false);
  };

  return (
    <div className="side-panel chesscom-panel">
      <div className="chesscom-header">
        <h3 className="panel-title">Chess.com · {username}</h3>
        <button type="button" className="chesscom-open" onClick={() => setIsOpen(true)}>
          Wybierz partię
        </button>
      </div>

      {importedGame && (
        <p className="chesscom-current-game">
          Wybrano: {importedGame.color === "white" ? "białe" : "czarne"} vs {importedGame.opponent}
        </p>
      )}

      {isOpen && (
        <div className="chesscom-modal-backdrop" onMouseDown={() => setIsOpen(false)}>
          <div
            className="chesscom-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="chesscom-modal-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="chesscom-modal-header">
              <h2 id="chesscom-modal-title">Partie Chess.com</h2>
              <button
                ref={closeButtonRef}
                type="button"
                className="chesscom-modal-close"
                onClick={() => setIsOpen(false)}
                aria-label="Zamknij okno"
              >
                ×
              </button>
            </div>

            <form className="chesscom-user-form" onSubmit={handleSubmit}>
              <label className="chesscom-user-field">
                <span>Użytkownik</span>
                <input
                  type="text"
                  value={draftUsername}
                  onChange={(e) => setDraftUsername(e.target.value)}
                  disabled={isLoading}
                  placeholder="nenow79"
                  autoComplete="username"
                />
              </label>
              <button type="submit" className="chesscom-user-submit" disabled={isLoading || !draftUsername.trim()}>
                Pobierz
              </button>
              <button type="button" className="chesscom-refresh" onClick={() => onRefresh()} disabled={isLoading}>
                Odśwież
              </button>
            </form>

            {isLoading ? (
              <p className="loading-text">Pobieram ostatnie partie...</p>
            ) : games.length === 0 ? (
              <p className="loading-text">Nie znaleziono zakończonych partii.</p>
            ) : (
              <div className="chesscom-games">
                {games.map((game) => (
                  <button
                    type="button"
                    key={game.id}
                    className={`chesscom-game ${importedGame?.id === game.id ? "selected" : ""}`}
                    onClick={() => handleImport(game)}
                  >
                    <span className="chesscom-opponent">
                      {game.color === "white" ? "Białe" : "Czarne"} vs {game.opponent}
                    </span>
                    <span>
                      {game.result} · {game.time_class} · {game.rating} / {game.opponent_rating}
                      {formatMoveCount(game.move_count)}
                    </span>
                    <span>{formatDate(game.played_at)}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
