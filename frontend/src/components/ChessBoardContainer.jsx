import { Chessboard } from "react-chessboard";

export default function ChessBoardContainer({ boardKey, fen, onPieceDrop, onUndo, onReset }) {
  return (
    <div className="board-section">
      <div className="board-wrapper">
        <Chessboard
          key={boardKey}
          position={fen}
          onPieceDrop={onPieceDrop}
          animationDuration={200}
        />
      </div>
      <div className="controls-container">
        <button className="control-btn" onClick={onUndo}>↩️ Cofnij</button>
        <button className="control-btn reset-btn" onClick={onReset}>🔄 Od nowa</button>
      </div>
    </div>
  );
}