import { useState } from "react";
import { Chessboard } from "react-chessboard";
import EvaluationChart from "./EvaluationChart";

export default function ChessBoardContainer({
  boardKey,
  fen,
  onPieceDrop,
  onUndo,
  onReset,
  navigation,
  navigationMove,
  onNavigate,
  evaluationSeries,
}) {
  const [boardOrientation, setBoardOrientation] = useState("white");
  const sourceSquare = navigationMove?.slice(0, 2);
  const targetSquare = navigationMove?.slice(2, 4);
  const navigationSquareStyles = navigationMove ? {
    [sourceSquare]: {
      background: "radial-gradient(circle, rgba(255, 193, 7, 0.88) 0%, rgba(255, 193, 7, 0.58) 72%, rgba(255, 193, 7, 0.35) 100%)",
      boxShadow: "inset 0 0 0 4px rgba(145, 96, 0, 0.62)",
    },
    [targetSquare]: {
      background: "radial-gradient(circle, rgba(255, 235, 59, 0.92) 0%, rgba(255, 193, 7, 0.68) 72%, rgba(255, 152, 0, 0.42) 100%)",
      boxShadow: "inset 0 0 0 4px rgba(145, 96, 0, 0.78)",
    },
  } : {};

  return (
    <div className="board-section">
      <div className="board-wrapper">
        <Chessboard
          key={boardKey}
          position={fen}
          onPieceDrop={onPieceDrop}
          animationDuration={400}
          arePiecesDraggable={!navigation}
          boardOrientation={boardOrientation}
          customSquareStyles={navigationSquareStyles}
        />
      </div>
      <button
        type="button"
        className="flip-board-btn"
        onClick={() => setBoardOrientation(current => current === "white" ? "black" : "white")}
        title="Obróć szachownicę"
      >
        Obróć szachownicę · na dole: {boardOrientation === "white" ? "białe" : "czarne"}
      </button>
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
              className="navigation-btn navigation-jump-btn"
              onClick={() => onNavigate(0)}
              disabled={navigation.currentPly === 0}
              title="Początek partii"
              aria-label="Przejdź do początku partii"
            >
              |&lt;
            </button>
            <button
              type="button"
              className="navigation-btn"
              onClick={() => onNavigate(navigation.currentPly - 1)}
              disabled={navigation.currentPly === 0}
              title="Poprzedni ruch"
            >
              &lt;
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
              &gt;
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
