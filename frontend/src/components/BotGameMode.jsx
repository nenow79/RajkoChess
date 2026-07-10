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
  const isPlayerTurn = game?.status === "active" && game.turn === game.player_color && !busy;

  const start = async () => {
    if (!selectedId) return;
    setBusy(true); setError("");
    try {
      const res = await axios.post(`${API_URL}/bot-games/start`, { bot_id: selectedId, player_color: playerColor });
      setGame(res.data);
    } catch (err) { setError(err.response?.data?.detail || "Nie udało się rozpocząć partii."); }
    finally { setBusy(false); }
  };

  const move = (from, to) => {
    if (!isPlayerTurn) return false;
    let result;
    try { result = board.move({ from, to, promotion: "q" }); } catch { return false; }
    if (!result) return false;
    const uci = `${from}${to}${result.promotion || ""}`;
    setBusy(true); setError("");
    axios.post(`${API_URL}/bot-games/move`, { uci })
      .then(res => setGame(res.data))
      .catch(err => setError(err.response?.data?.detail || "Ruch został odrzucony."))
      .finally(() => setBusy(false));
    return true;
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
          <div className="board-wrapper"><Chessboard position={game.fen} onPieceDrop={move} arePiecesDraggable={isPlayerTurn} boardOrientation={game.player_color} animationDuration={400} /></div>
          {game.bot_message && <div className="bot-speech">{game.bot.avatar} „{game.bot_message}”</div>}
          {error && <p className="form-error">{error}</p>}
          {game.status === "active" ? <div className="game-action-row"><button onClick={() => action("draw-offer")} disabled={busy}>Zaproponuj remis</button><button className="danger-action" onClick={() => action("resign")} disabled={busy}>Poddaj partię</button></div> : <div className="game-action-row"><button onClick={() => setGame(null)}>Nowa partia</button><button className="primary-action" onClick={analyze} disabled={busy}>Przeanalizuj partię</button></div>}
        </section>
        <aside className="game-side-card"><h2>{game.bot.avatar} {game.bot.name}</h2><p>{game.bot.description}</p><h3>Charakter gry</h3>{Object.entries(game.bot.style).map(([key, value]) => <div className="style-meter" key={key}><span>{key}</span><i><b style={{ width: `${value}%` }} /></i></div>)}<h3>Historia</h3><div className="move-history">{board.history().map((san, i) => <span key={i}>{i % 2 === 0 ? `${Math.floor(i / 2) + 1}. ` : ""}{san}</span>)}</div></aside>
      </main>}
      {error && !game && <p className="global-error">{error}</p>}
      {creator && <BotCreator editingBot={creator.bot} onClose={() => setCreator(null)} onSaved={() => { setCreator(null); loadBots(); }} />}
    </div>
  );
}
