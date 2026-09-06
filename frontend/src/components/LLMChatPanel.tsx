import { useState, useRef, useEffect, useCallback, useMemo, type KeyboardEvent } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { API_URL } from "../config";
import type { GameAnalysis, GameNavigation, ImportedGame, StoredChatMessage } from "../types";
import { getAuthErrorMessage } from "../auth/api";
import { getMyPlan } from "../admin/api";
import { buildChessMoveOptions, remarkChessMoveLinks } from "../chessMoveReferences";

interface ChatMessage {
  role: "bot" | "user";
  text: string;
  kind?: StoredChatMessage["kind"];
  positionPly?: number | null;
}

interface RemainingQuota {
  remaining: number | null;
  limit: number | null;
}

const WELCOME_MESSAGE: ChatMessage = {
  role: "bot",
  text: "Witaj! Jestem RajkoAI. Odpowiadam na pytania o widoczną pozycję, szachy i trening. Gotową analizę mogę też przetłumaczyć na angielski."
};

const MAX_CHAT_LENGTH = 1000;

const formatRemainingQuota = (quota: RemainingQuota) => quota.limit === null
  ? "bez limitu"
  : `${quota.remaining} z ${quota.limit}`;

interface LLMChatPanelProps {
  importedGame: ImportedGame | null;
  playerUsername: string;
  onGameAnalyzed: (analysis: GameAnalysis) => void;
  onChatChanged: (hasAnalysis: boolean) => void;
  navigation: GameNavigation | null;
  onNavigate: (ply: number) => void;
}

export default function LLMChatPanel({ importedGame, playerUsername, onGameAnalyzed, onChatChanged, navigation, onNavigate }: LLMChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastPolishAnalysis, setLastPolishAnalysis] = useState<string | null>(null);
  const [aiQuotas, setAiQuotas] = useState<{
    chat: RemainingQuota;
    gameReview: RemainingQuota;
  } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const analysisControllerRef = useRef<AbortController | null>(null);
  const activeGameId = importedGame?.storedGameId;
  const moveOptions = useMemo(() => buildChessMoveOptions(importedGame?.pgn), [importedGame?.pgn]);
  const [selectedPositionPly, setSelectedPositionPly] = useState<number | null>(null);
  const selectedPosition = moveOptions.find((move) => move.ply === selectedPositionPly);
  const markdownPlugins = useMemo(() => [
    remarkGfm,
    [remarkChessMoveLinks, { moves: moveOptions }] as [
      typeof remarkChessMoveLinks,
      { moves: typeof moveOptions },
    ],
  ], [moveOptions]);

  useEffect(() => {
    setSelectedPositionPly(moveOptions.length ? (navigation?.currentPly ?? 0) : null);
  }, [activeGameId, moveOptions, navigation?.currentPly]);

  const loadAiQuotas = useCallback(() => {
    void getMyPlan()
      .then((plan) => {
        const chat = plan.usage.ai_chat;
        const gameReview = plan.usage.ai_game_review;
        if (!chat || !gameReview) {
          setAiQuotas(null);
          return;
        }
        setAiQuotas({
          chat: {
            remaining: chat.limit === null ? null : Math.max(chat.limit - chat.used, 0),
            limit: chat.limit,
          },
          gameReview: {
            remaining: gameReview.limit === null ? null : Math.max(gameReview.limit - gameReview.used, 0),
            limit: gameReview.limit,
          },
        });
      })
      .catch(() => setAiQuotas(null));
  }, []);

  useEffect(() => {
    loadAiQuotas();
  }, [loadAiQuotas]);

  useEffect(() => {
    let active = true;
    setMessages([WELCOME_MESSAGE]);
    setLastPolishAnalysis(null);
    if (!activeGameId) return () => { active = false; };

    void axios.get<{ messages: StoredChatMessage[] }>(`${API_URL}/games/${activeGameId}/chat`)
      .then((response) => {
        if (!active) return;
        const stored = response.data.messages;
        setMessages(stored.length ? stored.map((message) => ({
          role: message.role === "assistant" ? "bot" : "user",
          kind: message.kind,
          positionPly: message.position_ply,
          text: message.kind === "translation"
            ? `**English translation**\n\n${message.content}`
            : message.content,
        })) : [WELCOME_MESSAGE]);
        const lastAnalysis = [...stored].reverse().find((message) => (
          message.role === "assistant" && message.kind !== "translation"
        ));
        setLastPolishAnalysis(lastAnalysis?.content || null);
      })
      .catch((error) => {
        if (active) setMessages([WELCOME_MESSAGE, {
          role: "bot",
          text: `❌ ${getAuthErrorMessage(error, "Nie udało się odtworzyć historii rozmowy.")}`,
        }]);
      });
    return () => { active = false; };
  }, [activeGameId]);

  // Automatyczne przewijanie czatu w dół przy nowej wiadomości
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg = input.trim();
    const questionPly = selectedPosition?.ply ?? null;
    setInput("");

    // Dodajemy wiadomość użytkownika do UI
    setMessages(prev => [...prev, { role: "user", text: userMsg, kind: "position", positionPly: questionPly }]);
    setIsLoading(true);
    const controller = new AbortController();
    analysisControllerRef.current = controller;

    try {
      // Endpoint domyślnie da silnikowi 2 sekundy i poprosi o 3 linie (ustawione w FastAPI)
      const res = await axios.post<{ response: string; action?: "use_game_review"; position_ply: number | null; position_label: string | null }>(`${API_URL}/chat`, {
        message: userMsg,
        position_ply: questionPly,
      }, {
        signal: controller.signal,
      });

      // Dodajemy odpowiedź Agenta
      setMessages(prev => [...prev, {
        role: "bot",
        text: res.data.response,
        kind: res.data.action ? undefined : "position",
        positionPly: res.data.position_ply,
      }]);
      if (!res.data.action) {
        setLastPolishAnalysis(res.data.response);
        loadAiQuotas();
        if (activeGameId) onChatChanged(true);
      }
    } catch (err) {
      if (axios.isCancel(err)) return;
      console.error("Błąd czatu:", err);
      setMessages(prev => [...prev, { role: "bot", text: `❌ ${getAuthErrorMessage(err, "Nie udało się uzyskać odpowiedzi trenera AI.")}` }]);
      loadAiQuotas();
    } finally {
      if (analysisControllerRef.current === controller) {
        analysisControllerRef.current = null;
        setIsLoading(false);
      }
    }
  };

  const handleAnalyzeGame = async () => {
    if (!importedGame || isLoading) return;

    const isChessComGame = Boolean(importedGame.id && importedGame.source !== "pgn" && !importedGame.bot);
    const gameLabel = importedGame.source === "pgn"
      ? `zaimportowaną partię${importedGame.opponent ? ` ${importedGame.opponent}` : ""}`
      : `partię przeciwko ${importedGame.opponent || "przeciwnikowi"}`;
    const reviewPrompt = `Przeanalizuj całą ${gameLabel}${isChessComGame && playerUsername ? ` z perspektywy gracza ${playerUsername}` : ""}.`;
    setMessages(prev => [...prev, {
      role: "user",
      text: reviewPrompt,
      kind: "game_review",
    }]);
    setIsLoading(true);
    const controller = new AbortController();
    analysisControllerRef.current = controller;

    try {
      const res = await axios.post<{ response: string; engine_analysis: GameAnalysis }>(`${API_URL}/analyze-game`, {
        message: reviewPrompt,
      }, {
        signal: controller.signal,
      });
      setMessages(prev => [...prev, { role: "bot", text: res.data.response, kind: "game_review" }]);
      setLastPolishAnalysis(res.data.response);
      onGameAnalyzed(res.data.engine_analysis);
      loadAiQuotas();
    } catch (err) {
      if (axios.isCancel(err)) return;
      console.error("Błąd analizy partii:", err);
      setMessages(prev => [...prev, {
        role: "bot",
        text: getAuthErrorMessage(err, "Nie udało się przeanalizować całej partii."),
      }]);
      loadAiQuotas();
    } finally {
      if (analysisControllerRef.current === controller) {
        analysisControllerRef.current = null;
        setIsLoading(false);
      }
    }
  };

  const handleTranslate = async () => {
    if (!lastPolishAnalysis || isLoading) return;
    setIsLoading(true);
    const controller = new AbortController();
    analysisControllerRef.current = controller;
    try {
      const res = await axios.post<{ response: string }>(`${API_URL}/chat/translate`, {}, {
        signal: controller.signal,
      });
      setMessages(prev => [...prev, {
        role: "bot",
        text: `**English translation**\n\n${res.data.response}`,
      }]);
      if (activeGameId) onChatChanged(true);
      loadAiQuotas();
    } catch (err) {
      if (axios.isCancel(err)) return;
      setMessages(prev => [...prev, {
        role: "bot",
        text: `❌ ${getAuthErrorMessage(err, "Nie udało się przetłumaczyć analizy.")}`,
      }]);
      loadAiQuotas();
    } finally {
      if (analysisControllerRef.current === controller) {
        analysisControllerRef.current = null;
        setIsLoading(false);
      }
    }
  };

  const handleCancelAnalysis = () => {
    analysisControllerRef.current?.abort();
    analysisControllerRef.current = null;
    setIsLoading(false);
    setMessages(prev => [...prev, {
      role: "bot",
      text: "Analiza została przerwana.",
    }]);
    axios.post(`${API_URL}/cancel-analysis`)
      .catch((err) => console.error("Nie udało się przerwać analizy na backendzie:", err));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClear = async () => {
    if (isLoading) return;
    if (!activeGameId) {
      setMessages([WELCOME_MESSAGE]);
      setInput("");
      setLastPolishAnalysis(null);
      return;
    }
    setIsLoading(true);
    try {
      const response = await axios.delete<{ cleared: boolean; has_analysis: boolean }>(`${API_URL}/games/${activeGameId}/chat`);
      setMessages([WELCOME_MESSAGE]);
      setInput("");
      setLastPolishAnalysis(null);
      onChatChanged(response.data.has_analysis);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: "bot",
        text: `❌ ${getAuthErrorMessage(error, "Nie udało się wyczyścić historii rozmowy.")}`,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMoveReference = (ply: number) => {
    if (!moveOptions.some((move) => move.ply === ply)) return;
    setSelectedPositionPly(ply);
    onNavigate(ply);
  };

  const changeSelectedPosition = (ply: number) => {
    if (moveOptions.some((move) => move.ply === ply)) setSelectedPositionPly(ply);
  };

  return (
    <div className="side-panel chat-panel">
      <div className="chat-panel-header">
        <h3 className="panel-title">
          🤖 Agent RajkoAI
          <span className="chat-quota" aria-live="polite">
            {aiQuotas === null
              ? "Limity AI: niedostępne"
              : `Pozostało — pytania: ${formatRemainingQuota(aiQuotas.chat)} · analizy partii: ${formatRemainingQuota(aiQuotas.gameReview)}`}
          </span>
        </h3>
        <div className="chat-header-controls">
          <button
            type="button"
            className="game-analysis-btn"
            onClick={handleTranslate}
            disabled={!lastPolishAnalysis || isLoading}
            title={lastPolishAnalysis ? "Przetłumacz ostatnią analizę na angielski" : "Najpierw wykonaj analizę"}
          >
            Translate EN
          </button>
          <button
            type="button"
            className="game-analysis-btn"
            onClick={handleAnalyzeGame}
            disabled={!importedGame || isLoading}
            title={importedGame ? "Analizuj zaimportowaną partię" : "Najpierw wybierz partię Chess.com"}
          >
            Analizuj całą partię
          </button>
          {isLoading && (
            <button
              type="button"
              className="cancel-analysis-btn"
              onClick={handleCancelAnalysis}
              title="Przerwij trwającą analizę"
            >
              Przerwij analizę
            </button>
          )}
          <button
            type="button"
            className="chat-clear"
            onClick={handleClear}
            disabled={isLoading}
            title="Wyczyść rozmowę"
          >
            Wyczyść czat
          </button>
        </div>
      </div>

      <div className="chat-container">
        <div className="chat-messages">
          {messages.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.role}`}>
              <strong>{msg.role === "bot" ? "RajkoAI:" : "Ty:"}</strong>
              {msg.kind === "position" && msg.positionPly !== null && msg.positionPly !== undefined && (
                <button
                  type="button"
                  className="chat-position-badge"
                  onClick={() => handleMoveReference(msg.positionPly!)}
                  title="Pokaż tę pozycję na szachownicy"
                >
                  {moveOptions.find((move) => move.ply === msg.positionPly)?.label || `Półruch ${msg.positionPly}`}
                </button>
              )}
              <div style={{ marginTop: '4px' }}>
                {msg.role === "bot" ? (
                  <ReactMarkdown
                    remarkPlugins={markdownPlugins}
                    components={{
                      a: ({ href, children }) => {
                        const match = href?.match(/^#ply-(\d+)$/);
                        if (!match) return <a href={href}>{children}</a>;
                        const ply = Number(match[1]);
                        return (
                          <button type="button" className="chat-move-link" onClick={() => handleMoveReference(ply)}>
                            {children}
                          </button>
                        );
                      },
                    }}
                  >{msg.text}</ReactMarkdown>
                ) : (
                  msg.text
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="chat-message bot">
              <strong>RajkoAI:</strong> <span style={{ color: '#7f8c8d' }}>Konsultuję dane z silnikiem... ⏳</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {moveOptions.length > 0 && selectedPosition && (
          <div className="chat-position-picker" aria-label="Pozycja analizowana przez RajkoAI">
            <span>{selectedPosition.ply === 0 ? "Pytasz o:" : "Pytasz o pozycję po:"}</span>
            <div>
              <button
                type="button"
                onClick={() => changeSelectedPosition(selectedPosition.ply - 1)}
                disabled={selectedPosition.ply === 0 || isLoading}
                aria-label="Poprzedni ruch do analizy"
              >‹</button>
              <select
                value={selectedPosition.ply}
                onChange={(event) => setSelectedPositionPly(Number(event.target.value))}
                disabled={isLoading}
                aria-label="Wybierz ruch do analizy"
              >
                {moveOptions.map((move) => <option key={move.ply} value={move.ply}>{move.label}</option>)}
              </select>
              <button
                type="button"
                onClick={() => changeSelectedPosition(selectedPosition.ply + 1)}
                disabled={selectedPosition.ply === moveOptions.length - 1 || isLoading}
                aria-label="Następny ruch do analizy"
              >›</button>
              <button
                type="button"
                className="show-chat-position"
                onClick={() => handleMoveReference(selectedPosition.ply)}
                disabled={isLoading}
              >Pokaż</button>
            </div>
          </div>
        )}
        <div className="chat-input-wrapper">
          <input
            type="text"
            className="chat-input"
            placeholder="Zapytaj o tę pozycję..."
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, MAX_CHAT_LENGTH))}
            onKeyDown={handleKeyDown}
            maxLength={MAX_CHAT_LENGTH}
            disabled={isLoading}
          />
          <button
            className="chat-send"
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            style={{
              opacity: isLoading || !input.trim() ? 0.7 : 1,
              cursor: isLoading || !input.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            Wyślij
          </button>
          <span className="chat-character-count" aria-live="polite">
            {input.length}/{MAX_CHAT_LENGTH}
          </span>
        </div>
      </div>
    </div>
  );
}
