import { useMemo, useState } from "react";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import EvaluationChart from "./EvaluationChart";

export default function ChessBoardContainer({
  boardKey,
  fen,
  onPieceDrop,
  onUndo,
  onReset,
  navigation,
  isVariationMode,
  navigationMove,
  onNavigate,
  onReturnToGame,
  evaluationSeries,
  pgn,
}) {
  const [boardOrientation, setBoardOrientation] = useState("white");
  const [selectedSquareState, setSelectedSquareState] = useState(null);
  const [copyStatus, setCopyStatus] = useState("");
  const sourceSquare = navigationMove?.slice(0, 2);
  const targetSquare = navigationMove?.slice(2, 4);
  const selectedSquare = selectedSquareState?.fen === fen ? selectedSquareState.square : null;

  const chess = useMemo(() => {
    try {
      return new Chess(fen === "start" ? undefined : fen);
    } catch {
      return null;
    }
  }, [fen]);

  const selectedMoveTargets = useMemo(() => {
    if (!chess || !selectedSquare) return [];

    return chess.moves({ square: selectedSquare, verbose: true }).map((move) => move.to);
  }, [chess, selectedSquare]);

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

  const selectedSquareStyles = selectedSquare ? {
    [selectedSquare]: {
      background: "radial-gradient(circle, rgba(46, 204, 113, 0.9) 0%, rgba(46, 204, 113, 0.58) 72%, rgba(39, 174, 96, 0.38) 100%)",
      boxShadow: "inset 0 0 0 4px rgba(21, 105, 56, 0.72)",
    },
    ...Object.fromEntries(selectedMoveTargets.map((square) => [
      square,
      {
        background: "radial-gradient(circle, rgba(46, 204, 113, 0.58) 0%, rgba(46, 204, 113, 0.28) 38%, transparent 42%)",
      },
    ])),
  } : {};

  const handleSquareClick = (square) => {
    if (!chess) return;

    const piece = chess.get(square);
    const isOwnPiece = piece?.color === chess.turn();

    if (!selectedSquare) {
      if (isOwnPiece) setSelectedSquareState({ square, fen });
      return;
    }

    if (square === selectedSquare) {
      setSelectedSquareState(null);
      return;
    }

    if (isOwnPiece) {
      setSelectedSquareState({ square, fen });
      return;
    }

    const wasMoveAccepted = onPieceDrop(selectedSquare, square);
    if (wasMoveAccepted) {
      setSelectedSquareState(null);
    }
  };

  const copyToClipboard = async (value, label) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopyStatus(`${label} skopiowany`);
    } catch {
      setCopyStatus(`Nie udało się skopiować ${label}`);
    }
    window.setTimeout(() => setCopyStatus(""), 2200);
  };

  return (
    <div className="board-section">
      <div className="board-wrapper">
        <Chessboard
          key={boardKey}
          position={fen}
          onPieceDrop={onPieceDrop}
          animationDuration={400}
          arePiecesDraggable
          boardOrientation={boardOrientation}
          onSquareClick={handleSquareClick}
          customSquareStyles={{ ...navigationSquareStyles, ...selectedSquareStyles }}
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
      <div className="position-export" aria-label="Eksport pozycji i partii">
        <button type="button" aria-label="Kopiuj FEN" title="Kopiuj FEN aktualnej pozycji" onClick={() => copyToClipboard(fen === "start" ? new Chess().fen() : fen, "FEN")}>⧉ FEN</button>
        <button type="button" aria-label="Kopiuj PGN" onClick={() => copyToClipboard(pgn, "PGN")} disabled={!pgn} title={pgn ? "Kopiuj PGN całej partii" : "PGN jest dostępny po zaimportowaniu partii"}>⧉ PGN</button>
        <span role="status" aria-live="polite">{copyStatus}</span>
      </div>
      {navigation ? (
        <div className="review-controls">
          {isVariationMode && (
            <div className="variation-banner">
              <div>
                <strong>Wariant</strong>
                <span>Analizujesz własną linię od: {navigation.moveLabel}</span>
              </div>
              <button
                type="button"
                className="return-game-btn secondary"
                onClick={onUndo}
              >
                Cofnij wariant
              </button>
              <button
                type="button"
                className="return-game-btn"
                onClick={onReturnToGame}
              >
                Wróć do partii
              </button>
            </div>
          )}
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
