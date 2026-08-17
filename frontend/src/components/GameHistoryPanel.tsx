import { useEffect, useRef, useState, type MouseEvent } from "react";
import axios from "axios";

import { getAuthErrorMessage } from "../auth/api";
import { API_URL } from "../config";
import type { HistoricalGameOpen, StoredGameSummary } from "../types";

interface GameHistoryPanelProps {
  activeGameId?: string;
  refreshKey: number;
  onOpen: (game: HistoricalGameOpen) => void;
  onError: (message: string) => void;
  source?: StoredGameSummary["source"];
  title?: string;
  emptyMessage?: string;
}

function formatDate(value: string | null, fallback: string) {
  const parsed = value ? new Date(value) : null;
  if (!parsed || Number.isNaN(parsed.getTime())) return fallback;
  return new Intl.DateTimeFormat("pl-PL", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(parsed);
}

export default function GameHistoryPanel({
  activeGameId,
  refreshKey,
  onOpen,
  onError,
  source = "bot",
  title = "Moje partie z botami",
  emptyMessage = "Zakończone partie z botami pojawią się tutaj.",
}: GameHistoryPanelProps) {
  const [games, setGames] = useState<StoredGameSummary[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [openingId, setOpeningId] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let active = true;
    axios.get<{ games: StoredGameSummary[] }>(`${API_URL}/games`, {
      params: { limit: 30, source },
    })
      .then((response) => {
        if (active) setGames(response.data.games);
      })
      .catch((error) => {
        if (active) onError(getAuthErrorMessage(error, "Nie udało się pobrać historii partii."));
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, [refreshKey, onError, source]);

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

  const openGame = async (gameId: string) => {
    setOpeningId(gameId);
    try {
      const response = await axios.post<HistoricalGameOpen>(`${API_URL}/games/${gameId}/open`);
      onOpen(response.data);
      setIsOpen(false);
    } catch (error) {
      onError(getAuthErrorMessage(error, "Nie udało się otworzyć zapisanej partii."));
    } finally {
      setOpeningId(null);
    }
  };

  const activeGame = games.find((game) => game.id === activeGameId);

  return (
    <section className="side-panel game-history-panel">
      <div className="chesscom-header">
        <h3 className="panel-title">{title}</h3>
        <button type="button" className="chesscom-open" onClick={() => setIsOpen(true)}>
          Wybierz partię
        </button>
      </div>

      {activeGame && (
        <p className="chesscom-current-game">
          Wybrano: {activeGame.opponent || (source === "bot" ? "partia z botem" : "import PGN")}
        </p>
      )}

      {isOpen && (
        <div className="chesscom-modal-backdrop" onMouseDown={() => setIsOpen(false)}>
          <div
            className="chesscom-modal game-history-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby={`${source}-history-modal-title`}
            onMouseDown={(event: MouseEvent<HTMLDivElement>) => event.stopPropagation()}
          >
            <div className="chesscom-modal-header">
              <h2 id={`${source}-history-modal-title`}>{title}</h2>
              <button
                ref={closeButtonRef}
                type="button"
                className="chesscom-modal-close"
                onClick={() => setIsOpen(false)}
                aria-label="Zamknij okno"
              >
                ×
              </button>
            </div>

            {isLoading ? (
              <p className="loading-text">Pobieram zapisane partie…</p>
            ) : games.length === 0 ? (
              <p className="loading-text">{emptyMessage}</p>
            ) : (
              <div className="game-history-list">
                {games.map((game) => (
                  <button
                    type="button"
                    key={game.id}
                    className={game.id === activeGameId ? "active" : ""}
                    disabled={openingId !== null}
                    onClick={() => openGame(game.id)}
                  >
                    <span>
                      <strong>{game.opponent || (source === "bot" ? "Partia z botem" : "Import PGN")}</strong>
                      <small>{game.result || (source === "bot" ? "Bot" : "PGN")}</small>
                      {game.has_analysis && <em className="analysis-badge">✦ Analiza</em>}
                    </span>
                    <time>{formatDate(game.played_at, formatDate(game.created_at, ""))}</time>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
