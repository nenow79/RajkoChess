import { useState, useEffect, useRef } from "react";
import { Chess, type Square } from "chess.js";
import axios from "axios";

import "./App.css";
import ChessBoardContainer from "./components/ChessBoardContainer";
import LichessExplorer from "./components/LichessExplorer";
import StockfishPanel from "./components/StockfishPanel";
import LLMChatPanel from "./components/LLMChatPanel"; // Import czatu
import ChessComPanel from "./components/ChessComPanel";
import { API_URL } from "./config";
import BotGameMode from "./components/BotGameMode";
import AuthScreen from "./components/AuthScreen";
import UserMenu from "./components/UserMenu";
import GameHistoryPanel from "./components/GameHistoryPanel";
import ManualImportPanel from "./components/ManualImportPanel";
import VerifyEmailScreen from "./components/VerifyEmailScreen";
import ResetPasswordScreen from "./components/ResetPasswordScreen";
import { useAuth } from "./auth/useAuth";
import { getAuthErrorMessage } from "./auth/api";
import type {
  AppMode,
  BotGame,
  ChessComGame,
  ExplorerData,
  GameAnalysis,
  GameNavigation,
  HistoricalGameOpen,
  ImportedGame,
  PositionAnalysis,
  RatingRange,
} from "./types";

const LICHESS_RATING_BUCKETS = [400, 1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500];

axios.defaults.withCredentials = true;

interface AnalysisWorkspaceProps {
  onModeChange: (mode: AppMode) => void;
  initialBotGame: BotGame | null;
  onInitialBotGameConsumed: () => void;
}

function AnalysisWorkspace({ onModeChange, initialBotGame, onInitialBotGameConsumed }: AnalysisWorkspaceProps) {
  const { platformAccounts } = useAuth();
  const savedChessComUsername = platformAccounts.find((account) => account.provider === "chesscom")?.username || "";
  const previousSavedChessComRef = useRef(savedChessComUsername);
  const initialBotGameRef = useRef(initialBotGame);
  const consumeInitialGameRef = useRef(onInitialBotGameConsumed);
  const gameRef = useRef(new Chess());
  const [fen, setFen] = useState("start");
  const [boardKey, setBoardKey] = useState(0);

  const [explorerData, setExplorerData] = useState<ExplorerData | null>(null);
  const [explorerError, setExplorerError] = useState("");
  const [explorerRatingRange, setExplorerRatingRange] = useState({ min: 400, max: 2500 });
  const [analysisData, setAnalysisData] = useState<PositionAnalysis | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [chessComUsername, setChessComUsername] = useState(savedChessComUsername);
  const [chessComGames, setChessComGames] = useState<ChessComGame[]>([]);
  const [isLoadingChessCom, setIsLoadingChessCom] = useState(false);
  const [error, setError] = useState("");
  const [importedGame, setImportedGame] = useState<ImportedGame | null>(null);
  const [gameNavigation, setGameNavigation] = useState<GameNavigation | null>(null);
  const [gameAnalysis, setGameAnalysis] = useState<GameAnalysis | null>(null);
  const [navigationMove, setNavigationMove] = useState<string | null>(null);
  const [isVariationMode, setIsVariationMode] = useState(false);
  const [historyRevision, setHistoryRevision] = useState(0);

  useEffect(() => {
    setChessComUsername((current) => (
      !current || current === previousSavedChessComRef.current
        ? savedChessComUsername
        : current
    ));
    previousSavedChessComRef.current = savedChessComUsername;
  }, [savedChessComUsername]);

  const fetchExplorerData = (ratingRange: RatingRange = explorerRatingRange) => {
    const ratings = LICHESS_RATING_BUCKETS
      .filter((rating) => rating >= ratingRange.min && rating <= ratingRange.max)
      .join(",");

    setExplorerError("");
    axios.get(`${API_URL}/explorer`, { params: { ratings } })
      .then((res) => setExplorerData(res.data))
      .catch((err) => setExplorerError(getAuthErrorMessage(err, "Nie udało się pobrać statystyk Lichess.")));
  };

  const handleExplorerRatingRangeChange = (range: RatingRange) => {
    setExplorerRatingRange(range);
    setExplorerData(null);
    fetchExplorerData(range);
  };

  const fetchAnalysis = () => {
    setError("");
    setIsAnalyzing(true);
    axios.get(`${API_URL}/analyze?time_limit=1.0&lines=3`)
      .then((res) => setAnalysisData(res.data))
      .catch((err) => setError(getAuthErrorMessage(err, "Nie udało się przeanalizować pozycji.")))
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

  const fetchChessComGames = (username: string = chessComUsername) => {
    const normalizedUsername = username.trim();
    if (!normalizedUsername) {
      setIsLoadingChessCom(false);
      return;
    }

    setError("");
    setIsLoadingChessCom(true);
    axios.get(`${API_URL}/chesscom/${encodeURIComponent(normalizedUsername)}/recent?limit=12`)
      .then((res) => setChessComGames(res.data.games))
      .catch((err) => setError(getAuthErrorMessage(err, "Nie udało się pobrać partii Chess.com.")))
      .finally(() => setIsLoadingChessCom(false));
  };

  const handleChessComUsernameChange = (username: string) => {
    const normalizedUsername = username.trim();
    setChessComUsername(normalizedUsername);
    setChessComGames([]);
    clearImportedGameContext();
    if (normalizedUsername) fetchChessComGames(normalizedUsername);
  };

  useEffect(() => {
    const initialGame = initialBotGameRef.current;
    const positionRequest = initialGame?.pgn
      ? axios.post(`${API_URL}/import-game`, {
          pgn: initialGame.pgn,
          metadata: { opponent: initialGame.bot?.name, result: initialGame.result, source: "bot" },
        })
      : axios.get(`${API_URL}/position`);
    void positionRequest
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setBoardKey(prev => prev + 1);
        if (initialGame?.pgn) {
          setImportedGame({
            ...initialGame,
            pgn: initialGame.pgn,
            opponent: initialGame.bot?.name,
            storedGameId: res.data.game_id,
          });
          setGameNavigation({
            currentPly: res.data.current_ply,
            totalPlies: res.data.total_plies,
            moveLabel: res.data.move_label,
          });
          consumeInitialGameRef.current?.();
          setHistoryRevision(prev => prev + 1);
        }
        return Promise.allSettled([
          axios.get(`${API_URL}/explorer`)
            .then((explorerResponse) => setExplorerData(explorerResponse.data))
            .catch((err) => setExplorerError(getAuthErrorMessage(err, "Nie udało się pobrać statystyk Lichess."))),
          axios.get(`${API_URL}/analyze?time_limit=1.0&lines=3`)
            .then((analysisResponse) => setAnalysisData(analysisResponse.data))
            .catch((err) => setError(getAuthErrorMessage(err, "Nie udało się przeanalizować pozycji."))),
        ]);
      })
      .catch((err) => setError(getAuthErrorMessage(err, "Nie udało się odtworzyć pozycji.")));
  }, []); // The workspace is remounted when entering analysis mode.

  const handleImportGame = (selectedGame: ChessComGame) => {
    axios.post(`${API_URL}/import-game`, {
      pgn: selectedGame.pgn,
      metadata: selectedGame,
    })
      .then((res) => {
        gameRef.current = new Chess(res.data.fen);
        setFen(res.data.fen);
        setBoardKey(prev => prev + 1);
        setImportedGame({ ...selectedGame, storedGameId: res.data.game_id });
        setGameAnalysis(null);
        setNavigationMove(null);
        setIsVariationMode(false);
        setGameNavigation({
          currentPly: res.data.current_ply,
          totalPlies: res.data.total_plies,
          moveLabel: res.data.move_label,
        });
        fetchAllData();
        setHistoryRevision(prev => prev + 1);
      })
      .catch((err) => setError(getAuthErrorMessage(err, "Nie udało się zaimportować partii.")));
  };

  function onPieceDrop(sourceSquare: Square, targetSquare: Square) {
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
          setError(getAuthErrorMessage(err, "Serwer odrzucił ruch."));
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
          const variationStillActive = gameRef.current.history().length > gameNavigation!.currentPly;
          setIsVariationMode(variationStillActive);
        } else {
          setImportedGame(null);
          setGameNavigation(null);
          setGameAnalysis(null);
          setIsVariationMode(false);
        }
        fetchAllData();
      })
      .catch(err => setError(getAuthErrorMessage(err, "Nie udało się cofnąć ruchu.")));
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
      .catch(err => setError(getAuthErrorMessage(err, "Nie udało się zresetować pozycji.")));
  };

  const handleNavigate = (ply: number) => {
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
      .catch((err) => setError(getAuthErrorMessage(err, "Nie udało się przejść do wybranego ruchu.")));
  };

  const handleOpenHistoricalGame = (stored: HistoricalGameOpen) => {
    gameRef.current = new Chess(stored.fen);
    setFen(stored.fen);
    setBoardKey(prev => prev + 1);
    setImportedGame({
      ...stored.metadata,
      pgn: stored.pgn,
      storedGameId: stored.game_id,
    });
    setGameAnalysis(null);
    setNavigationMove(null);
    setIsVariationMode(false);
    setGameNavigation({
      currentPly: stored.current_ply,
      totalPlies: stored.total_plies,
      moveLabel: stored.move_label,
    });
    fetchAllData();
  };

  const handleManualImport = async (format: "pgn" | "fen", value: string) => {
    setError("");
    try {
      if (format === "fen") {
        const response = await axios.post<{ fen: string }>(`${API_URL}/import-position`, { fen: value });
        gameRef.current = new Chess(response.data.fen);
        setFen(response.data.fen);
        setBoardKey(prev => prev + 1);
        clearImportedGameContext();
      } else {
        const response = await axios.post(`${API_URL}/import-game`, {
          pgn: value,
          metadata: { source: "pgn" },
        });
        gameRef.current = new Chess(response.data.fen);
        setFen(response.data.fen);
        setBoardKey(prev => prev + 1);
        const white = response.data.metadata?.white;
        const black = response.data.metadata?.black;
        setImportedGame({
          ...response.data.metadata,
          source: "pgn",
          pgn: value,
          opponent: white || black ? `${white || "?"} – ${black || "?"}` : undefined,
          storedGameId: response.data.game_id,
        });
        setGameAnalysis(null);
        setNavigationMove(null);
        setIsVariationMode(false);
        setGameNavigation({
          currentPly: response.data.current_ply,
          totalPlies: response.data.total_plies,
          moveLabel: response.data.move_label,
        });
        setHistoryRevision(prev => prev + 1);
      }
      fetchAllData();
    } catch (error) {
      setError(getAuthErrorMessage(error, `Nie udało się zaimportować ${format.toUpperCase()}.`));
      throw error;
    }
  };

  const handleAnalysisMarkerChange = (hasAnalysis: boolean) => {
    const externalId = importedGame?.id;
    if (externalId) {
      setChessComGames(current => current.map(game => (
        game.id === externalId ? { ...game, has_analysis: hasAnalysis } : game
      )));
    }
    setHistoryRevision(prev => prev + 1);
  };

  return (
    <div className="app-container">

      <div className="workspace-top">
        {/* Globalny Nagłówek */}
        <header className="app-header">
          <h1>♞ Rajko Chess</h1>
          <div className="header-actions">
            <div className="mode-switch" aria-label="Tryb aplikacji">
              <button className="active" type="button">Analiza</button>
              <button type="button" onClick={() => onModeChange("game")}>Gra z botem</button>
            </div>
            <UserMenu />
          </div>
        </header>

        {error && (
          <div className="workspace-error" role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => setError("")} aria-label="Zamknij komunikat">×</button>
          </div>
        )}
      </div>

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
            onReturnToGame={() => gameNavigation && handleNavigate(gameNavigation.currentPly)}
            evaluationSeries={gameAnalysis?.evaluation_series}
            pgn={importedGame?.pgn}
          />
          <ChessComPanel
            key={savedChessComUsername}
            username={chessComUsername}
            games={chessComGames}
            isLoading={isLoadingChessCom}
            importedGame={importedGame}
            onImport={handleImportGame}
            onRefresh={fetchChessComGames}
            onUsernameChange={handleChessComUsernameChange}
          />
          <ManualImportPanel onImport={handleManualImport} />
          <GameHistoryPanel
            activeGameId={importedGame?.storedGameId}
            refreshKey={historyRevision}
            onOpen={handleOpenHistoricalGame}
            onError={setError}
          />
          <GameHistoryPanel
            activeGameId={importedGame?.storedGameId}
            refreshKey={historyRevision}
            source="pgn"
            title="Moje importy PGN"
            emptyMessage="Ręcznie importowane partie PGN pojawią się tutaj."
            onOpen={handleOpenHistoricalGame}
            onError={setError}
          />
        </div>

        {/* Kolumna 2: Panele Lichess + Stockfish */}
        <div className="stats-col">
          <LichessExplorer
            data={explorerData}
            error={explorerError}
            ratingRange={explorerRatingRange}
            onRatingRangeChange={handleExplorerRatingRangeChange}
            onRetry={() => fetchExplorerData()}
          />
          <StockfishPanel data={analysisData} isAnalyzing={isAnalyzing} />
        </div>

        {/* Kolumna 3: Czat LLM */}
        <div className="chat-col">
          <LLMChatPanel
            importedGame={importedGame}
            playerUsername={chessComUsername}
            onGameAnalyzed={(analysis) => {
              setGameAnalysis(analysis);
              handleAnalysisMarkerChange(true);
            }}
            onChatChanged={handleAnalysisMarkerChange}
          />
        </div>

      </div>
    </div>
  );
}

export default function App() {
  const { status } = useAuth();
  const [mode, setMode] = useState<AppMode>("analysis");
  const [finishedBotGame, setFinishedBotGame] = useState<BotGame | null>(null);

  const openAnalysis = (game: BotGame | null = null) => {
    setFinishedBotGame(game);
    setMode("analysis");
  };

  const routePath = window.location.pathname.replace(/\/+$/, "");

  if (routePath.endsWith("/verify-email")) {
    return <VerifyEmailScreen />;
  }

  if (routePath.endsWith("/reset-password")) {
    return <ResetPasswordScreen />;
  }

  if (status === "loading") {
    return <main className="auth-page"><div className="auth-loading" role="status">♞<span>Sprawdzamy sesję…</span></div></main>;
  }

  if (status === "anonymous") return <AuthScreen />;

  return mode === "game" ? (
    <BotGameMode onModeChange={setMode} onAnalyze={openAnalysis} />
  ) : (
    <AnalysisWorkspace
      onModeChange={setMode}
      initialBotGame={finishedBotGame}
      onInitialBotGameConsumed={() => setFinishedBotGame(null)}
    />
  );
}
