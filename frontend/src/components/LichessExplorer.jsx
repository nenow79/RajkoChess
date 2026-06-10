import WinrateBar from "./WinrateBar";

export default function LichessExplorer({ data }) {
  if (!data) {
    return (
      <div className="side-panel">
        <h3 className="panel-title">Lichess Explorer</h3>
        <p className="loading-text">Ładowanie statystyk...</p>
      </div>
    );
  }

  return (
    <div className="side-panel">
      <h3 className="panel-title">Lichess Explorer</h3>

      <div className="opening-box">
        <div className="opening-name">
          {data.opening_eco ? `[${data.opening_eco}] ` : ''}
          {data.opening_name || "Nieznane otwarcie"}
        </div>
        <div className="opening-stats">
          Partie w bazie: {data.total_games_analyzed.toLocaleString()}
        </div>
      </div>

      <table className="moves-table">
        <thead>
          <tr>
            <th>Ruch</th>
            <th>Częstość</th>
            <th>Wyniki</th>
          </tr>
        </thead>
        <tbody>
          {data.top_moves.map((move) => (
            <tr key={move.uci}>
              <td className="move-san">{move.san}</td>
              <td>{move.play_rate_pct}%</td>
              <td style={{ width: '50%' }}>
                <div className="winrate-labels">
                  <span>{move.white_win_pct}%</span>
                  <span>{move.black_win_pct}%</span>
                </div>
                <WinrateBar white={move.white_win_pct} draw={move.draw_pct} black={move.black_win_pct} />
              </td>
            </tr>
          ))}
          {data.top_moves.length === 0 && (
            <tr>
              <td colSpan="3" className="empty-table">Brak danych dla tej pozycji.</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}