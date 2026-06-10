import { useState, useEffect, useRef } from "react";
import { Chess } from "chess.js";
import axios from "axios";

import "./App.css";
import ChessBoardContainer from "./components/ChessBoardContainer";
import LichessExplorer from "./components/LichessExplorer";
import StockfishPanel from "./components/StockfishPanel";
import LLMChatPanel from "./components/LLMChatPanel"; // Import czatu

const API_URL = import.meta.env.VITE_API_URL;

export default function App() {
  const gameRef = useRef(new Chess());
  const [fen, setFen] = useState("start");
  const [boardKey, setBoardKey] = useState(0);

  const [explorerData, setExplorerData] = useState(null);
  const [analysisData, setAnalysisData] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

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

  useEffect(() => {
    axios.get(`${API_URL}/position`)
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setBoardKey(prev => prev + 1);
        fetchAllData();
      })
      .catch((err) => console.error("Błąd backendu:", err));
  }, []);

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
          fetchAllData();
        })
        .catch((err) => {
          console.error("Backend odrzucił ruch:", err);
          gameRef.current.undo();
          setFen(gameRef.current.fen());
          setBoardKey(prev => prev + 1);
        });

      return true;
    } catch (err) { return false; }
  }

  const handleUndo = () => {
    axios.post(`${API_URL}/undo`)
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
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
        fetchAllData();
      })
      .catch(err => console.error("Błąd resetu:", err));
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
          />
        </div>

        {/* Kolumna 2: Panele Lichess + Stockfish */}
        <div className="stats-col">
          <LichessExplorer data={explorerData} />
          <StockfishPanel data={analysisData} isAnalyzing={isAnalyzing} />
        </div>

        {/* Kolumna 3: Czat LLM */}
        <div className="chat-col">
          <LLMChatPanel />
        </div>

      </div>
    </div>
  );
}