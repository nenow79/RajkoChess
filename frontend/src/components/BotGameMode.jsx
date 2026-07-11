import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Chess } from "chess.js";
import { Chessboard } from "react-chessboard";
import { API_URL } from "../config";
import BotCreator from "./BotCreator";

export default function BotGameMode({ onModeChange, onAnalyze }) {
  const [bots, setBots] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [playerColor, setPlayerColor] = useState("random");
  const [game, setGame] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [creator, setCreator] = useState(null);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [boardOrientation, setBoardOrientation] = useState(null);
  const [pendingPromotion, setPendingPromotion] = useState(null);

  const loadBots = () => axios.get(`${API_URL}/bots`).then(res => {
    setBots(res.data.bots);
    setSelectedId(current => current || res.data.bots[0]?.id || "");
  });

  useEffect(() => {
    loadBots().catch(() => setError("Nie udało się pobrać botów."));
    axios.get(`${API_URL}/bot-games/current`).then(res => {
      if (res.data.status !== "none") setGame(res.data);
    }).catch(() => {});
  }, []);

  const selectedBot = bots.find(bot => bot.id === selectedId);
  const board = useMemo(() => {
    try { return new Chess(game?.fen); } catch { return new Chess(); }
  }, [game?.fen]);
  const moveHistory = useMemo(() => {
    const replay = new Chess();
    const moves = [];
    for (const uci of game?.history || []) {
      try {
        const result = replay.move({
          from: uci.slice(0, 2),
          to: uci.slice(2, 4),
          promotion: uci.slice(4, 5) || undefined,
        });
        if (!result) break;
        moves.push(result.san);
      } catch {
        break;
      }
    }
    return moves;
  }, [game?.history]);
  const isPlayerTurn = game?.status === "active" && game.turn === game.player_color && !busy;
  const orientation = boardOrientation || game?.player_color || "white";
  const activeSelectedSquare = selectedSquare && selectedSquare.fen === game?.fen && !busy ? selectedSquare.square : null;

  const legalTargets = useMemo(() => {
    if (!activeSelectedSquare || !isPlayerTurn) return [];
    return board.moves({ square: activeSelectedSquare, verbose: true }).map(item => item.to);
  }, [activeSelectedSquare, board, isPlayerTurn]);

  const squareStyles = useMemo(() => {
    const styles = {};
    const lastMove = game?.last_move_uci;
    if (lastMove) {
      for (const square of [lastMove.slice(0, 2), lastMove.slice(2, 4)]) {
        styles[square] = { background: "rgba(255, 193, 7, .62)", boxShadow: "inset 0 0 0 3px rgba(145, 96, 0, .45)" };
      }
    }
    if (activeSelectedSquare) {
      styles[activeSelectedSquare] = { background: "rgba(46, 204, 113, .68)", boxShadow: "inset 0 0 0 4px rgba(21, 105, 56, .65)" };
      for (const square of legalTargets) {
        styles[square] = { background: "radial-gradient(circle, rgba(46, 204, 113, .65) 0 18%, transparent 22%)" };
      }
    }
    if (board.inCheck()) {
      const king = board.findPiece({ type: "k", color: board.turn() })?.[0];
      if (king) styles[king] = { background: "radial-gradient(circle, rgba(231, 76, 60, .9), rgba(192, 57, 43, .45))" };
    }
    return styles;
  }, [activeSelectedSquare, board, game?.last_move_uci, legalTargets]);

  const start = async () => {
    if (!selectedId) return;
    setBusy(true); setError("");
    try {
      const res = await axios.post(`${API_URL}/bot-games/start`, { bot_id: selectedId, player_color: playerColor });
      setGame(res.data);
    } catch (err) { setError(err.response?.data?.detail || "Nie udało się rozpocząć partii."); }
    finally { setBusy(false); }
  };

  const submitMove = (from, to, promotion) => {
    if (!isPlayerTurn) return false;
    let result;
    try { result = board.move({ from, to, promotion }); } catch { return false; }
    if (!result) return false;
    const uci = `${from}${to}${result.promotion || ""}`;
    setBusy(true); setError("");
    axios.post(`${API_URL}/bot-games/move`, { uci })
      .then(res => setGame(res.data))
      .catch(err => setError(err.response?.data?.detail || "Ruch został odrzucony."))
      .finally(() => setBusy(false));
    return true;
  };

  const move = (from, to) => {
    const piece = board.get(from);
    const isPromotion = piece?.type === "p" && (to.endsWith("8") || to.endsWith("1"));
    if (isPromotion) {
      setPendingPromotion({ from, to });
      return false;
    }
    return submitMove(from, to);
  };

  const handleSquareClick = (square) => {
    if (!isPlayerTurn) return;
    const piece = board.get(square);
    const ownPiece = piece?.color === board.turn();
    if (!activeSelectedSquare) {
      if (ownPiece) setSelectedSquare({ square, fen: game.fen });
    } else if (square === activeSelectedSquare) {
      setSelectedSquare(null);
    } else if (ownPiece) {
      setSelectedSquare({ square, fen: game.fen });
    } else if (move(activeSelectedSquare, square)) {
      setSelectedSquare(null);
    }
  };

  const action = async (path) => {
    setBusy(true); setError("");
    try { const res = await axios.post(`${API_URL}/bot-games/${path}`); setGame(res.data); }
    catch (err) { setError(err.response?.data?.detail || "Operacja nie powiodła się."); }
    finally { setBusy(false); }
  };

  const removeBot = async (bot) => {
    if (!window.confirm(`Usunąć bota „${bot.name}”?`)) return;
    await axios.delete(`${API_URL}/bots/${bot.id}`);
    setSelectedId("");
    loadBots();
  };

  const switchToAnalysis = () => {
    if (game?.status === "active" && !window.confirm("Porzucić aktywną partię i przejść do analizy?")) return;
    onModeChange("analysis");
  };

  const analyze = async () => {
    setBusy(true);
    try {
      await axios.post(`${API_URL}/bot-games/to-analysis`);
      onAnalyze(game);
    } catch (err) { setError(err.response?.data?.detail || "Nie udało się przekazać partii do analizy."); setBusy(false); }
  };

  return (
    <div className="app-container game-mode-container">
      <header className="app-header">
        <h1>♞ Rajko Chess</h1>
        <div className="mode-switch"><button type="button" onClick={switchToAnalysis}>Analiza</button><button type="button" className="active">Gra z botem</button></div>
      </header>
      {!game ? <main className="bot-lobby">
        <div className="lobby-heading"><div><h2>Wybierz przeciwnika</h2><p>Każdy bot ma własną siłę, repertuar i sposób podejmowania ryzyka.</p></div><button className="create-bot-btn" onClick={() => setCreator({ mode: "create" })}>＋ Create bot</button></div>
        <div className="bot-grid">{bots.map(bot => <article key={bot.id} className={`bot-card ${selectedId === bot.id ? "selected" : ""}`} onClick={() => setSelectedId(bot.id)}>
          <div className="bot-avatar">{bot.avatar}</div><div className="bot-card-title"><h3>{bot.name}</h3><strong>≈ {bot.target_elo} Elo</strong></div><p>{bot.description}</p>
          <div className="bot-style-summary"><span>Agresja {bot.style.aggression}</span><span>Taktyka {bot.style.tacticality}</span><span>Ryzyko {bot.style.risk}</span></div>
          <div className="bot-card-actions"><button onClick={event => { event.stopPropagation(); setCreator({ mode: "edit", bot }); }}>Edytuj</button><button onClick={event => { event.stopPropagation(); removeBot(bot); }}>Usuń</button></div>
        </article>)}</div>
        {selectedBot && <section className="start-game-panel"><div><strong>Zagrasz przeciwko: {selectedBot.avatar} {selectedBot.name}</strong><span>Siła jest orientacyjna i zależy od pozycji.</span></div><label>Twój kolor<select value={playerColor} onChange={e => setPlayerColor(e.target.value)}><option value="random">Losowy</option><option value="white">Białe</option><option value="black">Czarne</option></select></label><button onClick={start} disabled={busy}>{busy ? "Bot przygotowuje ruch..." : "Rozpocznij partię"}</button></section>}
      </main> : <main className="bot-game-layout">
        <section className="bot-board-column">
          <div className="bot-game-status"><div className="bot-avatar small">{game.bot.avatar}</div><div><strong>{game.bot.name} · ≈ {game.bot.target_elo} Elo</strong><span>{game.status === "active" ? (busy ? "Bot myśli..." : isPlayerTurn ? "Twój ruch" : "Ruch bota") : `Koniec partii · ${game.result}`}</span></div></div>
          <div className="board-wrapper"><Chessboard position={game.fen} onPieceDrop={move} onSquareClick={handleSquareClick} customSquareStyles={squareStyles} arePiecesDraggable={isPlayerTurn} boardOrientation={orientation} animationDuration={400} /></div>
          <button type="button" className="flip-board-btn" onClick={() => setBoardOrientation(current => (current || game.player_color) === "white" ? "black" : "white")}>Obróć szachownicę · na dole: {orientation === "white" ? "białe" : "czarne"}</button>
          {game.bot_message && <div className="bot-speech">{game.bot.avatar} „{game.bot_message}”</div>}
          {error && <p className="form-error">{error}</p>}
          {game.status === "active" ? <div className="game-action-row"><button onClick={() => action("draw-offer")} disabled={busy}>Zaproponuj remis</button><button className="danger-action" onClick={() => action("resign")} disabled={busy}>Poddaj partię</button></div> : <div className="game-action-row"><button onClick={() => setGame(null)}>Nowa partia</button><button className="primary-action" onClick={analyze} disabled={busy}>Przeanalizuj partię</button></div>}
        </section>
        <aside className="game-side-card"><h2>{game.bot.avatar} {game.bot.name}</h2><p>{game.bot.description}</p><h3>Charakter gry</h3>{Object.entries(game.bot.style).map(([key, value]) => <div className="style-meter" key={key}><span>{key}</span><i><b style={{ width: `${value}%` }} /></i></div>)}<h3>Ulubione otwarcia</h3>{game.bot.openings?.length ? <div className="favorite-openings">{game.bot.openings.map(opening => <div key={`${opening.color}-${opening.opening_id}`}><span>{opening.color === "white" ? "Białymi" : "Czarnymi"}</span><strong>{opening.name || opening.opening_id}</strong>{opening.eco && <small>{opening.eco}</small>}</div>)}</div> : <p className="empty-side-section">Brak przypisanego repertuaru.</p>}<h3>Historia</h3><div className="move-history">{moveHistory.length ? moveHistory.map((san, i) => <span key={i}>{i % 2 === 0 ? `${Math.floor(i / 2) + 1}. ` : ""}{san}</span>) : <span className="empty-side-section">Partia jeszcze się nie rozpoczęła.</span>}</div></aside>
      </main>}
      {error && !game && <p className="global-error">{error}</p>}
      {creator && <BotCreator editingBot={creator.bot} onClose={() => setCreator(null)} onSaved={() => { setCreator(null); loadBots(); }} />}
      {pendingPromotion && <div className="promotion-overlay" role="dialog" aria-modal="true" aria-label="Wybierz figurę promocji"><div className="promotion-picker"><strong>Wybierz figurę</strong><div>{[["q", "Hetman", "♛"], ["r", "Wieża", "♜"], ["b", "Goniec", "♝"], ["n", "Skoczek", "♞"]].map(([piece, label, symbol]) => <button key={piece} type="button" title={label} onClick={() => { const pending = pendingPromotion; setPendingPromotion(null); setSelectedSquare(null); submitMove(pending.from, pending.to, piece); }}>{symbol}<span>{label}</span></button>)}</div><button type="button" className="promotion-cancel" onClick={() => setPendingPromotion(null)}>Anuluj</button></div></div>}
    </div>
  );
}
