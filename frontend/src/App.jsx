import { useState, useEffect, useRef } from "react";
import { Chess } from "chess.js";
import axios from "axios";

import "./App.css";
import ChessBoardContainer from "./components/ChessBoardContainer";
import LichessExplorer from "./components/LichessExplorer";
import StockfishPanel from "./components/StockfishPanel";
import LLMChatPanel from "./components/LLMChatPanel"; // Import czatu
import ChessComPanel from "./components/ChessComPanel";

const API_URL = import.meta.env.VITE_API_URL;

export default function App() {
  const gameRef = useRef(new Chess());
  const [fen, setFen] = useState("start");
  const [boardKey, setBoardKey] = useState(0);

  const [explorerData, setExplorerData] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [chessComGames, setChessComGames] = useState([]);
  const [isLoadingChessCom, setIsLoadingChessCom] = useState(true);
  const [importedGame, setImportedGame] = useState(null);
  const [gameNavigation, setGameNavigation] = useState(null);
  const [gameAnalysis, setGameAnalysis] = useState(null);
  const [navigationMove, setNavigationMove] = useState(null);

  const fetchExplorerData = () => {
    axios.get(`${API_URL}/explorer`)
      .then((res) => setExplorerData(res.data))
      .catch((err) => console.error("Błąd Lichess:", err));
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

  const fetchChessComGames = () => {
    setIsLoadingChessCom(true);
    axios.get(`${API_URL}/chesscom/nenow79/recent?limit=12`)
      .then((res) => setChessComGames(res.data.games))
      .catch((err) => console.error("Błąd Chess.com:", err))
      .finally(() => setIsLoadingChessCom(false));
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
    axios.get(`${API_URL}/chesscom/nenow79/recent?limit=12`)
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

      axios.post(`${API_URL}/move`, { uci: uciMove })
        .then((res) => {
          gameRef.current = new Chess(res.data.fen);
          setFen(res.data.fen);
          setImportedGame(null);
          setGameNavigation(null);
          setGameAnalysis(null);
          setNavigationMove(null);
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
    axios.post(`${API_URL}/undo`)
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setImportedGame(null);
        setGameNavigation(null);
        setGameAnalysis(null);
        setNavigationMove(null);
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
            navigationMove={navigationMove}
            onNavigate={handleNavigate}
            evaluationSeries={gameAnalysis?.evaluation_series}
          />
          <ChessComPanel
            games={chessComGames}
            isLoading={isLoadingChessCom}
            importedGame={importedGame}
            onImport={handleImportGame}
            onRefresh={fetchChessComGames}
          />
        </div>

        {/* Kolumna 2: Panele Lichess + Stockfish */}
        <div className="stats-col">
          <LichessExplorer data={explorerData} />
          <StockfishPanel data={analysisData} isAnalyzing={isAnalyzing} />
        </div>

        {/* Kolumna 3: Czat LLM */}
        <div className="chat-col">
          <LLMChatPanel importedGame={importedGame} onGameAnalyzed={setGameAnalysis} />
        </div>

      </div>
    </div>
  );
}
