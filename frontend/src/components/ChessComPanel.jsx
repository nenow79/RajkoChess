export default function ChessComPanel({ games, isLoading, importedGame, onImport, onRefresh }) {
  const formatDate = (value) => value
    ? new Intl.DateTimeFormat("pl-PL", { dateStyle: "short", timeStyle: "short" }).format(new Date(value))
    : "brak daty";

  return (
    <div className="side-panel chesscom-panel">
      <div className="chesscom-header">
        <h3 className="panel-title">Chess.com · nenow79</h3>
        <button type="button" className="chesscom-refresh" onClick={onRefresh} disabled={isLoading}>
          Odśwież
        </button>
      </div>

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
