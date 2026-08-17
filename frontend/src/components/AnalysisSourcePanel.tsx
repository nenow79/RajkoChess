import { useCallback, useEffect, useRef, useState, type FormEvent, type MouseEvent } from "react";
import axios from "axios";

import { getAuthErrorMessage } from "../auth/api";
import { API_URL } from "../config";
import type { ChessComGame, HistoricalGameOpen, ImportedGame, StoredGameSummary } from "../types";

type SourceTab = "online" | "library" | "import";
type LibraryFilter = "all" | StoredGameSummary["source"];
type ImportFormat = "pgn" | "fen";

interface AnalysisSourcePanelProps {
  username: string;
  chessComGames: ChessComGame[];
  isLoadingChessCom: boolean;
  importedGame: ImportedGame | null;
  isFenPosition: boolean;
  activeGameId?: string;
  onChessComImport: (game: ChessComGame) => void;
  onChessComRefresh: (username?: string) => void;
  onUsernameChange: (username: string) => void;
  onManualImport: (format: ImportFormat, value: string) => Promise<void>;
  onOpenStoredGame: (game: HistoricalGameOpen) => void;
  onError: (message: string) => void;
}

const SOURCE_LABELS: Record<StoredGameSummary["source"], string> = {
  chesscom: "Chess.com",
  bot: "Bot Rajko",
  pgn: "Import PGN",
};

function formatDate(value: string | null, fallback = "") {
  const parsed = value ? new Date(value) : null;
  if (!parsed || Number.isNaN(parsed.getTime())) return fallback;
  return new Intl.DateTimeFormat("pl-PL", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

function formatMoveCount(count: number | null) {
  if (count == null) return "";
  const lastTwoDigits = count % 100;
  const lastDigit = count % 10;
  const suffix = count === 1 ? "ruch" : lastDigit >= 2 && lastDigit <= 4
    && (lastTwoDigits < 12 || lastTwoDigits > 14) ? "ruchy" : "ruchów";
  return ` · ${count} ${suffix}`;
}

export default function AnalysisSourcePanel({
  username,
  chessComGames,
  isLoadingChessCom,
  importedGame,
  isFenPosition,
  activeGameId,
  onChessComImport,
  onChessComRefresh,
  onUsernameChange,
  onManualImport,
  onOpenStoredGame,
  onError,
}: AnalysisSourcePanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [tab, setTab] = useState<SourceTab>("online");
  const [draftUsername, setDraftUsername] = useState(username);
  const [libraryFilter, setLibraryFilter] = useState<LibraryFilter>("all");
  const [storedGames, setStoredGames] = useState<StoredGameSummary[]>([]);
  const [isLoadingLibrary, setIsLoadingLibrary] = useState(false);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [importFormat, setImportFormat] = useState<ImportFormat>("pgn");
  const [importValue, setImportValue] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const loadLibrary = useCallback((filter: LibraryFilter = libraryFilter) => {
    setIsLoadingLibrary(true);
    axios.get<{ games: StoredGameSummary[] }>(`${API_URL}/games`, {
      params: {
        limit: 100,
        ...(filter === "all" ? {} : { source: filter }),
      },
    })
      .then((response) => setStoredGames(response.data.games))
      .catch((error) => onError(getAuthErrorMessage(error, "Nie udało się pobrać zapisanych partii.")))
      .finally(() => setIsLoadingLibrary(false));
  }, [libraryFilter, onError]);

  useEffect(() => {
    if (!isOpen) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    document.addEventListener("keydown", handleKeyDown);
    closeButtonRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const openModal = () => {
    setDraftUsername(username);
    setIsOpen(true);
    if (tab === "library") loadLibrary();
  };

  const selectTab = (nextTab: SourceTab) => {
    setTab(nextTab);
    if (nextTab === "library") loadLibrary();
  };

  const selectLibraryFilter = (filter: LibraryFilter) => {
    setLibraryFilter(filter);
    loadLibrary(filter);
  };

  const handleChessComSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = draftUsername.trim();
    setDraftUsername(normalized);
    onUsernameChange(normalized);
  };

  const selectChessComGame = (game: ChessComGame) => {
    onChessComImport(game);
    setIsOpen(false);
  };

  const openStoredGame = async (gameId: string) => {
    setOpeningId(gameId);
    try {
      const response = await axios.post<HistoricalGameOpen>(`${API_URL}/games/${gameId}/open`);
      onOpenStoredGame(response.data);
      setIsOpen(false);
    } catch (error) {
      onError(getAuthErrorMessage(error, "Nie udało się otworzyć zapisanej partii."));
    } finally {
      setOpeningId(null);
    }
  };

  const handleManualImport = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = importValue.trim();
    if (!normalized || isImporting) return;
    setIsImporting(true);
    try {
      await onManualImport(importFormat, normalized);
      setImportValue("");
      setIsOpen(false);
    } catch {
      // Błąd jest prezentowany przez nadrzędny obszar roboczy.
    } finally {
      setIsImporting(false);
    }
  };

  const activeSource = importedGame?.source === "pgn"
    ? "Import PGN"
    : importedGame?.source === "bot" || importedGame?.bot
      ? "Bot Rajko"
      : importedGame
        ? "Chess.com"
        : isFenPosition
          ? "Pozycja FEN"
          : null;
  const activeDescription = importedGame
    ? `${importedGame.color === "white" ? "Białe · " : importedGame.color === "black" ? "Czarne · " : ""}${importedGame.opponent || "zapisana partia"}${importedGame.result ? ` · ${importedGame.result}` : ""}`
    : isFenPosition
      ? "Jednorazowa pozycja na szachownicy"
      : "Nie wybrano partii — analizujesz bieżącą pozycję";

  return (
    <section className="side-panel analysis-source-panel">
      <div className="analysis-source-summary">
        <div>
          <h3>Partia do analizy</h3>
          {activeSource && <strong>{activeSource}</strong>}
          <span>{activeDescription}</span>
        </div>
        <button type="button" onClick={openModal}>{activeSource ? "Zmień" : "Wybierz partię"}</button>
      </div>

      {isOpen && (
        <div className="analysis-source-backdrop" onMouseDown={() => setIsOpen(false)}>
          <div className="analysis-source-modal" role="dialog" aria-modal="true" aria-labelledby="analysis-source-title" onMouseDown={(event: MouseEvent<HTMLDivElement>) => event.stopPropagation()}>
            <header>
              <div>
                <h2 id="analysis-source-title">Wybierz partię lub pozycję</h2>
                <p>Otwórz partię z serwisu, własnej biblioteki albo wklej PGN/FEN.</p>
              </div>
              <button ref={closeButtonRef} type="button" onClick={() => setIsOpen(false)} aria-label="Zamknij okno">×</button>
            </header>

            <nav className="analysis-source-tabs" aria-label="Źródło materiału">
              <button type="button" className={tab === "online" ? "active" : ""} onClick={() => selectTab("online")}>Serwis online</button>
              <button type="button" className={tab === "library" ? "active" : ""} onClick={() => selectTab("library")}>Moje zapisane</button>
              <button type="button" className={tab === "import" ? "active" : ""} onClick={() => selectTab("import")}>Wklej PGN / FEN</button>
            </nav>

            <div className="analysis-source-content">
              {tab === "online" && (
                <div className="online-source-view">
                  <div className="online-provider-row">
                    <label>
                      Serwis
                      <select value="chesscom" disabled><option value="chesscom">Chess.com</option></select>
                    </label>
                    <small>Kolejne serwisy pojawią się w tym miejscu.</small>
                  </div>
                  <form className="online-username-form" onSubmit={handleChessComSubmit}>
                    <label>
                      Użytkownik Chess.com
                      <input
                        type="text"
                        value={draftUsername}
                        onChange={(event) => setDraftUsername(event.target.value.slice(0, 50))}
                        maxLength={50}
                        pattern="[A-Za-z0-9_-]+"
                        placeholder="Login Chess.com"
                        autoComplete="off"
                        disabled={isLoadingChessCom}
                      />
                    </label>
                    <button type="submit" disabled={!draftUsername.trim() || isLoadingChessCom}>Pobierz partie</button>
                    {username && <button type="button" className="secondary" onClick={() => onChessComRefresh()} disabled={isLoadingChessCom}>Odśwież</button>}
                  </form>
                  {isLoadingChessCom ? (
                    <p className="source-empty">Pobieram ostatnie partie…</p>
                  ) : chessComGames.length === 0 ? (
                    <p className="source-empty">Wpisz dowolny login i pobierz ostatnie partie. Login z ustawień jest tylko wartością domyślną.</p>
                  ) : (
                    <div className="analysis-game-list">
                      {chessComGames.map((game) => (
                        <button type="button" key={game.id} onClick={() => selectChessComGame(game)}>
                          <span className="game-list-main">
                            <strong>{game.color === "white" ? "Białe" : "Czarne"} vs {game.opponent}</strong>
                            <small>{game.result} · {game.time_class} · {game.rating} / {game.opponent_rating}{formatMoveCount(game.move_count)}</small>
                          </span>
                          <span className="game-list-meta">
                            {game.has_analysis && <em className="analysis-badge">✦ Analiza</em>}
                            <time>{formatDate(game.played_at, "Brak daty")}</time>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {tab === "library" && (
                <div className="library-source-view">
                  <div className="library-filters" aria-label="Filtr zapisanych partii">
                    {(["all", "chesscom", "bot", "pgn"] as LibraryFilter[]).map((filter) => (
                      <button type="button" key={filter} className={libraryFilter === filter ? "active" : ""} onClick={() => selectLibraryFilter(filter)}>
                        {filter === "all" ? "Wszystkie" : SOURCE_LABELS[filter]}
                      </button>
                    ))}
                  </div>
                  {isLoadingLibrary ? (
                    <p className="source-empty">Pobieram bibliotekę…</p>
                  ) : storedGames.length === 0 ? (
                    <p className="source-empty">Nie masz jeszcze zapisanych partii w tej kategorii.</p>
                  ) : (
                    <div className="analysis-game-list">
                      {storedGames.map((game) => (
                        <button type="button" key={game.id} className={game.id === activeGameId ? "active" : ""} disabled={openingId !== null} onClick={() => openStoredGame(game.id)}>
                          <span className="game-source-icon" aria-hidden="true">{game.source === "chesscom" ? "♟" : game.source === "bot" ? "🤖" : "↥"}</span>
                          <span className="game-list-main">
                            <strong>{game.opponent || SOURCE_LABELS[game.source]}</strong>
                            <small>{SOURCE_LABELS[game.source]}{game.result ? ` · ${game.result}` : ""}</small>
                          </span>
                          <span className="game-list-meta">
                            {game.has_analysis && <em className="analysis-badge">✦ Analiza</em>}
                            <time>{formatDate(game.played_at, formatDate(game.created_at))}</time>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {tab === "import" && (
                <form className="unified-import-form" onSubmit={handleManualImport}>
                  <div className="import-format-tabs" aria-label="Format importu">
                    <button type="button" className={importFormat === "pgn" ? "active" : ""} onClick={() => setImportFormat("pgn")}>Cała partia PGN</button>
                    <button type="button" className={importFormat === "fen" ? "active" : ""} onClick={() => setImportFormat("fen")}>Pozycja FEN</button>
                  </div>
                  <label>
                    {importFormat === "pgn" ? "Zapis partii" : "Pozycja szachowa"}
                    <textarea
                      value={importValue}
                      onChange={(event) => setImportValue(event.target.value)}
                      maxLength={importFormat === "pgn" ? 200_000 : 128}
                      rows={importFormat === "pgn" ? 12 : 4}
                      placeholder={importFormat === "pgn" ? "[Event \"...\"]\n\n1. e4 e5 2. Nf3 ..." : "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}
                      disabled={isImporting}
                    />
                  </label>
                  <div className="unified-import-footer">
                    <p>{importFormat === "pgn" ? "PGN zostanie zapisany w Twojej bibliotece wraz z rozmową RajkoAI." : "FEN otworzy jednorazową pozycję i nie będzie zapisany jako pełna partia."}</p>
                    <button type="submit" disabled={!importValue.trim() || isImporting}>{isImporting ? "Importuję…" : "Otwórz na szachownicy"}</button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
