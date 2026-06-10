import { useState, useRef, useEffect } from "react";
import axios from "axios";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const API_URL = import.meta.env.VITE_API_URL;
const WELCOME_MESSAGE = {
  role: "bot",
  text: "Witaj! Jestem RajkoAI. Przeanalizuję dla Ciebie obecną pozycję na szachownicy, wskażę plany oraz pułapki debiutowe. O co chcesz zapytać?"
};

export default function LLMChatPanel() {
  const [messages, setMessages] = useState([WELCOME_MESSAGE]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

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
    setInput("");

    // Dodajemy wiadomość użytkownika do UI
    setMessages(prev => [...prev, { role: "user", text: userMsg }]);
    setIsLoading(true);

    try {
      // Endpoint domyślnie da silnikowi 2 sekundy i poprosi o 3 linie (ustawione w FastAPI)
      const res = await axios.post(`${API_URL}/chat`, { message: userMsg });

      // Dodajemy odpowiedź Agenta
      setMessages(prev => [...prev, { role: "bot", text: res.data.response }]);
    } catch (err) {
      console.error("Błąd czatu:", err);
      setMessages(prev => [...prev, { role: "bot", text: "❌ Błąd połączenia z Agentem LLM. Upewnij się, że klucz API w pliku .env jest poprawny." }]);
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
            disabled={isLoading || !input.trim()}
            style={{
              opacity: isLoading || !input.trim() ? 0.7 : 1,
              cursor: isLoading || !input.trim() ? 'not-allowed' : 'pointer'
            }}
          >
            Wyślij
          </button>
        </div>
      </div>
    </div>
  );
}
