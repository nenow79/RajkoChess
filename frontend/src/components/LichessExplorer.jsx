import WinrateBar from "./WinrateBar";

const RATING_BUCKETS = [400, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500];

export default function LichessExplorer({ data, ratingRange, onRatingRangeChange }) {
  const updateRange = (key, value) => {
    const nextRange = { ...ratingRange, [key]: Number(value) };
    if (key === "min" && nextRange.min > nextRange.max) nextRange.max = nextRange.min;
    if (key === "max" && nextRange.max < nextRange.min) nextRange.min = nextRange.max;
    onRatingRangeChange(nextRange);
  };

  return (
    <div className="side-panel">
      <h3 className="panel-title">Lichess Explorer</h3>

      <div className="lichess-rating-filter">
        <label>
          <span>Ranking od</span>
          <select value={ratingRange.min} onChange={(event) => updateRange("min", event.target.value)}>
            {RATING_BUCKETS.map((rating) => (
              <option key={rating} value={rating}>{rating}</option>
            ))}
          </select>
        </label>
        <label>
          <span>Ranking do</span>
          <select value={ratingRange.max} onChange={(event) => updateRange("max", event.target.value)}>
            {RATING_BUCKETS.map((rating, index) => {
              const label = rating === 2500 ? "2500+" : RATING_BUCKETS[index + 1] - 1;
              return <option key={rating} value={rating}>{label}</option>;
            })}
          </select>
        </label>
      </div>

      {!data ? (
        <p className="loading-text">Ładowanie statystyk...</p>
      ) : (
        <>
          <div className="opening-box">
            <div className="opening-name">
              {data.opening_eco ? `[${data.opening_eco}] ` : ''}
              {data.opening_name || "Nieznane otwarcie"}
              {data.opening_is_fallback && <span className="opening-fallback-label">ostatnie znane</span>}
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
        </>
      )}
    </div>
  );
}
