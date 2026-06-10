export default function StockfishPanel({ data, isAnalyzing }) {
  return (
    <div className="side-panel engine-panel">
      <h3 className="panel-title">
        ⚙️ Analiza Stockfish
      </h3>

      {isAnalyzing ? (
        <div className="engine-loading">
          Silnik przelicza pozycję... ⏳
        </div>
      ) : !data ? (
        <p className="loading-text">Brak danych z silnika.</p>
      ) : (
        <div>
          {/* Główna ocena pozycji */}
          <div className="evaluation-box">
            <div className="evaluation-label">
              Ocena silnika (Głębokość: {data.variations[0]?.depth || '?'})
            </div>
            <div className="evaluation-score">
              {data.variations[0]?.evaluation > 0 ? '+' : ''}{data.variations[0]?.evaluation}
            </div>
          </div>

          {/* Najlepsze warianty (MultiPV) */}
          <div className="variations-container">
            <div className="variations-title">
              Najlepsze kontynuacje:
            </div>
            {data.variations.map((variant, index) => (
              <div key={index} className="variation-card">
                <div className="variation-header">
                  <span className="variation-score">
                    {variant.evaluation > 0 ? '+' : ''}{variant.evaluation}
                  </span>
                  <span className="variation-depth">
                    Głębokość: {variant.depth}
                  </span>
                </div>
                <div className="variation-line">
                  {variant.line_san.join(" ➔ ")}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}