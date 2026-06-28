import { useState, useEffect, useRef } from "react";
import { Chess } from "chess.js";
import axios from "axios";

import "./App.css";
import ChessBoardContainer from "./components/ChessBoardContainer";
import LichessExplorer from "./components/LichessExplorer";
import StockfishPanel from "./components/StockfishPanel";
import LLMChatPanel from "./components/LLMChatPanel"; // Import czatu
import ChessComPanel from "./components/ChessComPanel";
import { API_URL } from "./config";

const DEFAULT_CHESSCOM_USERNAME = "nenow79";
const SESSION_STORAGE_KEY = "rajko-session-id";
const LICHESS_RATING_BUCKETS = [400, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500];

function getSessionId() {
  const savedSessionId = localStorage.getItem(SESSION_STORAGE_KEY);
  if (savedSessionId) return savedSessionId;

  const newSessionId = crypto.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  localStorage.setItem(SESSION_STORAGE_KEY, newSessionId);
  return newSessionId;
}

axios.defaults.headers.common["X-Session-Id"] = getSessionId();

export default function App() {
  const gameRef = useRef(new Chess());
  const [fen, setFen] = useState("start");
  const [boardKey, setBoardKey] = useState(0);

  const [explorerData, setExplorerData] = useState(null);
  const [explorerRatingRange, setExplorerRatingRange] = useState({ min: 400, max: 2500 });
  const [analysisData, setAnalysisData] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [chessComUsername, setChessComUsername] = useState(DEFAULT_CHESSCOM_USERNAME);
  const [chessComGames, setChessComGames] = useState([]);
  const [isLoadingChessCom, setIsLoadingChessCom] = useState(true);
  const [importedGame, setImportedGame] = useState(null);
  const [gameNavigation, setGameNavigation] = useState(null);
  const [gameAnalysis, setGameAnalysis] = useState(null);
  const [navigationMove, setNavigationMove] = useState(null);
  const [isVariationMode, setIsVariationMode] = useState(false);

  const fetchExplorerData = (ratingRange = explorerRatingRange) => {
    const ratings = LICHESS_RATING_BUCKETS
      .filter((rating) => rating >= ratingRange.min && rating <= ratingRange.max)
      .join(",");

    axios.get(`${API_URL}/explorer`, { params: { ratings } })
      .then((res) => setExplorerData(res.data))
      .catch((err) => console.error("Błąd Lichess:", err));
  };

  const handleExplorerRatingRangeChange = (range) => {
    setExplorerRatingRange(range);
    setExplorerData(null);
    fetchExplorerData(range);
  };

  const fetchAnalysis = () => {
    setIsAnalyzing(true);
    axios.get(`${API_URL}/analyze?time_limit=1.0&lines=3`)
      .then((res) => setAnalysisData(res.data))
      .catch((err) => console.error("Błąd Stockfish:", err))
      .finally(() => setIsAnalyzing(false));
  };

  const fetchAllData = () => {
    fetchExplorerData();
    fetchAnalysis();
  };

  const clearImportedGameContext = () => {
    setImportedGame(null);
    setGameNavigation(null);
    setGameAnalysis(null);
    setNavigationMove(null);
    setIsVariationMode(false);
  };

  const fetchChessComGames = (username = chessComUsername) => {
    const normalizedUsername = username.trim();
    if (!normalizedUsername) return;

    setIsLoadingChessCom(true);
    axios.get(`${API_URL}/chesscom/${encodeURIComponent(normalizedUsername)}/recent?limit=12`)
      .then((res) => setChessComGames(res.data.games))
      .catch((err) => console.error("Błąd Chess.com:", err))
      .finally(() => setIsLoadingChessCom(false));
  };

  const handleChessComUsernameChange = (username) => {
    const normalizedUsername = username.trim() || DEFAULT_CHESSCOM_USERNAME;
    setChessComUsername(normalizedUsername);
    setChessComGames([]);
    clearImportedGameContext();
    fetchChessComGames(normalizedUsername);
  };

  useEffect(() => {
    axios.get(`${API_URL}/position`)
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setBoardKey(prev => prev + 1);
      })
      .catch((err) => console.error("Błąd backendu:", err));
    axios.get(`${API_URL}/explorer`)
      .then((res) => setExplorerData(res.data))
      .catch((err) => console.error("Błąd Lichess:", err));
    axios.get(`${API_URL}/analyze?time_limit=1.0&lines=3`)
      .then((res) => setAnalysisData(res.data))
      .catch((err) => console.error("Błąd Stockfish:", err));
    axios.get(`${API_URL}/chesscom/${encodeURIComponent(DEFAULT_CHESSCOM_USERNAME)}/recent?limit=12`)
      .then((res) => setChessComGames(res.data.games))
      .catch((err) => console.error("Błąd Chess.com:", err))
      .finally(() => setIsLoadingChessCom(false));
  }, []);

  const handleImportGame = (selectedGame) => {
    axios.post(`${API_URL}/import-game`, {
      pgn: selectedGame.pgn,
      metadata: selectedGame,
    })
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setBoardKey(prev => prev + 1);
        setImportedGame(selectedGame);
        setGameAnalysis(null);
        setNavigationMove(null);
        setIsVariationMode(false);
        setGameNavigation({
          currentPly: res.data.current_ply,
          totalPlies: res.data.total_plies,
          moveLabel: res.data.move_label,
        });
        fetchAllData();
      })
      .catch((err) => console.error("Błąd importu PGN:", err));
  };

  function onPieceDrop(sourceSquare, targetSquare) {
    try {
      const moveResult = gameRef.current.move({ from: sourceSquare, to: targetSquare, promotion: "q" });
      if (!moveResult) return false;

      setFen(gameRef.current.fen());
      const uciMove = `${sourceSquare}${targetSquare}${moveResult.promotion ? moveResult.promotion : ""}`;
      const preserveImportedContext = Boolean(gameNavigation);

      axios.post(`${API_URL}/move`, {
        uci: uciMove,
        preserve_imported_context: preserveImportedContext,
      })
        .then((res) => {
          gameRef.current = new Chess(res.data.fen);
          setFen(res.data.fen);
          setNavigationMove(null);
          if (preserveImportedContext) {
            setIsVariationMode(true);
          } else {
            setImportedGame(null);
            setGameNavigation(null);
            setGameAnalysis(null);
            setIsVariationMode(false);
          }
          fetchAllData();
        })
        .catch((err) => {
          console.error("Backend odrzucił ruch:", err);
          gameRef.current.undo();
          setFen(gameRef.current.fen());
          setBoardKey(prev => prev + 1);
        });

      return true;
    } catch { return false; }
  }

  const handleUndo = () => {
    const preserveImportedContext = Boolean(gameNavigation && isVariationMode);

    axios.post(`${API_URL}/undo`, {
      preserve_imported_context: preserveImportedContext,
    })
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setNavigationMove(null);
        if (preserveImportedContext) {
          const variationStillActive = gameRef.current.history().length > gameNavigation.currentPly;
          setIsVariationMode(variationStillActive);
        } else {
          setImportedGame(null);
          setGameNavigation(null);
          setGameAnalysis(null);
          setIsVariationMode(false);
        }
        fetchAllData();
      })
      .catch(err => console.error("Błąd cofania:", err));
  };

  const handleReset = () => {
    axios.post(`${API_URL}/reset`)
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setBoardKey(prev => prev + 1);
        setImportedGame(null);
        setGameNavigation(null);
        setGameAnalysis(null);
        setNavigationMove(null);
        setIsVariationMode(false);
        fetchAllData();
      })
      .catch(err => console.error("Błąd resetu:", err));
  };

  const handleNavigate = (ply) => {
    axios.post(`${API_URL}/imported-game/position`, { ply })
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setNavigationMove(res.data.navigation_move_uci);
        setIsVariationMode(false);
        setGameNavigation({
          currentPly: res.data.current_ply,
          totalPlies: res.data.total_plies,
          moveLabel: res.data.move_label,
        });
        fetchAllData();
      })
      .catch((err) => console.error("Błąd nawigacji po partii:", err));
  };

  return (
    <div className="app-container">

      {/* Globalny Nagłówek */}
      <header className="app-header">
        <h1>♞ Rajko Chess Analyser</h1>
      </header>

      <div className="app-layout">

        {/* Kolumna 1: Szachownica */}
        <div className="board-col">
          <ChessBoardContainer
            boardKey={boardKey}
            fen={fen}
            onPieceDrop={onPieceDrop}
            onUndo={handleUndo}
            onReset={handleReset}
            navigation={gameNavigation}
            isVariationMode={isVariationMode}
            navigationMove={navigationMove}
            onNavigate={handleNavigate}
            onReturnToGame={() => handleNavigate(gameNavigation.currentPly)}
            evaluationSeries={gameAnalysis?.evaluation_series}
          />
          <ChessComPanel
            key={chessComUsername}
            username={chessComUsername}
            games={chessComGames}
            isLoading={isLoadingChessCom}
            importedGame={importedGame}
            onImport={handleImportGame}
            onRefresh={fetchChessComGames}
            onUsernameChange={handleChessComUsernameChange}
          />
        </div>

        {/* Kolumna 2: Panele Lichess + Stockfish */}
        <div className="stats-col">
          <LichessExplorer
            data={explorerData}
            ratingRange={explorerRatingRange}
            onRatingRangeChange={handleExplorerRatingRangeChange}
          />
          <StockfishPanel data={analysisData} isAnalyzing={isAnalyzing} />
        </div>

        {/* Kolumna 3: Czat LLM */}
        <div className="chat-col">
          <LLMChatPanel
            importedGame={importedGame}
            playerUsername={chessComUsername}
            onGameAnalyzed={setGameAnalysis}
          />
        </div>

      </div>
    </div>
  );
}
