import { useState } from "react";

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

  const formatDate = (value) => value
    ? new Intl.DateTimeFormat("pl-PL", { dateStyle: "short", timeStyle: "short" }).format(new Date(value))
    : "brak daty";

  const handleSubmit = (e) => {
    e.preventDefault();
    const normalizedUsername = draftUsername.trim();
    setDraftUsername(normalizedUsername);
    onUsernameChange(normalizedUsername);
  };

  return (
    <div className="side-panel chesscom-panel">
      <div className="chesscom-header">
        <h3 className="panel-title">Chess.com · {username}</h3>
        <button type="button" className="chesscom-refresh" onClick={() => onRefresh()} disabled={isLoading}>
          Odśwież
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
              onClick={() => onImport(game)}
            >
              <span className="chesscom-opponent">
                {game.color === "white" ? "Białe" : "Czarne"} vs {game.opponent}
              </span>
              <span>{game.result} · {game.time_class} · {game.rating} / {game.opponent_rating}</span>
              <span>{formatDate(game.played_at)}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
