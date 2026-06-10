import { useState, useRef, useEffect } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_URL = import.meta.env.VITE_API_URL;
const MODEL_STORAGE_KEY = "rajko-selected-model";
const WELCOME_MESSAGE = {
  role: "bot",
  text: "Witaj! Jestem RajkoAI. Przeanalizuję dla Ciebie obecną pozycję na szachownicy, wskażę plany oraz pułapki debiutowe. O co chcesz zapytać?"
};

export default function LLMChatPanel({ importedGame }) {
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState("");
  const messagesEndRef = useRef(null);

  // Automatyczne przewijanie czatu w dół przy nowej wiadomości
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    axios.get(`${API_URL}/models`)
      .then((res) => {
        const availableModels = res.data.models;
        const savedModel = localStorage.getItem(MODEL_STORAGE_KEY);
        const initialModel = availableModels.some((model) => model.id === savedModel)
          ? savedModel
          : res.data.default_model;

        setModels(availableModels);
        setSelectedModel(initialModel);
      })
      .catch((err) => console.error("Błąd pobierania modeli:", err));
  }, []);

  const handleModelChange = (e) => {
    const model = e.target.value;
    setSelectedModel(model);
    localStorage.setItem(MODEL_STORAGE_KEY, model);
  };

  const handleSend = async () => {
    if (!input.trim() || isLoading || !selectedModel) return;

    const userMsg = input.trim();
    setInput("");

    // Dodajemy wiadomość użytkownika do UI
    setMessages(prev => [...prev, { role: "user", text: userMsg }]);
    setIsLoading(true);

    try {
      // Endpoint domyślnie da silnikowi 2 sekundy i poprosi o 3 linie (ustawione w FastAPI)
      const res = await axios.post(`${API_URL}/chat`, {
        message: userMsg,
        model: selectedModel
      });

      // Dodajemy odpowiedź Agenta
      setMessages(prev => [...prev, { role: "bot", text: res.data.response }]);
    } catch (err) {
      console.error("Błąd czatu:", err);
      setMessages(prev => [...prev, { role: "bot", text: "❌ Błąd połączenia z Agentem LLM. Upewnij się, że klucz API w pliku .env jest poprawny." }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnalyzeGame = async () => {
    if (!importedGame || isLoading || !selectedModel) return;

    setMessages(prev => [...prev, {
      role: "user",
      text: `Przeanalizuj całą partię przeciwko ${importedGame.opponent}.`,
    }]);
    setIsLoading(true);

    try {
      const res = await axios.post(`${API_URL}/analyze-game`, {
        message: "Przeanalizuj całą partię z perspektywy gracza nenow79.",
        model: selectedModel,
      });
      setMessages(prev => [...prev, { role: "bot", text: res.data.response }]);
    } catch (err) {
      console.error("Błąd analizy partii:", err);
      setMessages(prev => [...prev, {
        role: "bot",
        text: "Nie udało się przeanalizować całej partii. Sprawdź backend, Stockfisha i konfigurację LLM.",
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleClear = () => {
    setMessages([WELCOME_MESSAGE]);
    setInput("");
  };

  return (
    <div className="side-panel chat-panel">
      <div className="chat-panel-header">
        <h3 className="panel-title">
          🤖 Agent RajkoAI
        </h3>
        <div className="chat-header-controls">
          <button
            type="button"
            className="game-analysis-btn"
            onClick={handleAnalyzeGame}
            disabled={!importedGame || isLoading || !selectedModel}
            title={importedGame ? "Analizuj zaimportowaną partię" : "Najpierw wybierz partię Chess.com"}
          >
            Analizuj całą partię
          </button>
          <label className="model-picker">
            <span>Model</span>
            <select
              value={selectedModel}
              onChange={handleModelChange}
              disabled={isLoading || models.length === 0}
            >
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.label} · {model.description} · ${model.input_price}/${model.output_price}
                </option>
              ))}
            </select>
          </label>
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
              <div style={{ marginTop: '4px' }}>
                {msg.role === "bot" ? (
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
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

        <div className="chat-input-wrapper">
          <input
            type="text"
            className="chat-input"
            placeholder="Zapytaj o tę pozycję..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
          />
          <button
            className="chat-send"
            onClick={handleSend}
            disabled={isLoading || !input.trim() || !selectedModel}
            style={{
              opacity: isLoading || !input.trim() || !selectedModel ? 0.7 : 1,
              cursor: isLoading || !input.trim() || !selectedModel ? 'not-allowed' : 'pointer'
            }}
          >
            Wyślij
          </button>
        </div>
      </div>
    </div>
  );
}
