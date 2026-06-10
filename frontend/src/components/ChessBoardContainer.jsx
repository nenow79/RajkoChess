import { Chessboard } from "react-chessboard";
import EvaluationChart from "./EvaluationChart";

export default function ChessBoardContainer({
  boardKey,
  fen,
  onPieceDrop,
  onUndo,
  onReset,
  navigation,
  onNavigate,
  evaluationSeries,
}) {
  return (
    <div className="board-section">
      <div className="board-wrapper">
        <Chessboard
          key={boardKey}
          position={fen}
          onPieceDrop={onPieceDrop}
          animationDuration={200}
          arePiecesDraggable={!navigation}
        />
      </div>
      {navigation ? (
        <div className="review-controls">
          <EvaluationChart
            data={evaluationSeries}
            currentPly={navigation.currentPly}
            onNavigate={onNavigate}
          />
          <div className="game-navigation" aria-label="Nawigacja po partii">
            <button
              type="button"
              className="navigation-btn"
              onClick={() => onNavigate(navigation.currentPly - 1)}
              disabled={navigation.currentPly === 0}
              title="Poprzedni ruch"
            >
              &lt;&lt;
            </button>
            <div className="move-counter">
              <strong>{navigation.moveLabel}</strong>
              <span>{navigation.currentPly} / {navigation.totalPlies}</span>
            </div>
            <button
              type="button"
              className="navigation-btn"
              onClick={() => onNavigate(navigation.currentPly + 1)}
              disabled={navigation.currentPly === navigation.totalPlies}
              title="Następny ruch"
            >
              &gt;&gt;
            </button>
          </div>
          <button
            type="button"
            className="end-review-btn"
            onClick={onReset}
          >
            Zakończ analizę
          </button>
        </div>
      ) : (
        <div className="controls-container">
          <button className="control-btn" onClick={onUndo}>↩️ Cofnij</button>
          <button className="control-btn reset-btn" onClick={onReset}>🔄 Od nowa</button>
        </div>
      )}
    </div>
  );
}
