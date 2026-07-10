import { useEffect, useState } from "react";
import axios from "axios";
import { API_URL } from "../config";

const EMPTY = {
  name: "", description: "", avatar: "🤖", target_elo: 1400,
  style: { aggression: 50, tacticality: 50, risk: 50, materialism: 50, simplification: 50 },
  openings: [], phrases: {},
};
const LABELS = { aggression: "Agresja", tacticality: "Taktyka", risk: "Ryzyko", materialism: "Materializm", simplification: "Uproszczenia" };

export default function BotCreator({ editingBot, onSaved, onClose }) {
  const [description, setDescription] = useState("");
  const [draft, setDraft] = useState(editingBot || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [warnings, setWarnings] = useState([]);
  const [openingQuery, setOpeningQuery] = useState("");
  const [openingColor, setOpeningColor] = useState("white");
  const [openingResults, setOpeningResults] = useState([]);

  useEffect(() => {
    if (openingQuery.trim().length < 2) return undefined;
    const timer = setTimeout(() => axios.get(`${API_URL}/openings`, { params: { q: openingQuery, limit: 8 } })
      .then(res => setOpeningResults(res.data.openings)), 250);
    return () => clearTimeout(timer);
  }, [openingQuery]);

  const generate = async () => {
    if (!description.trim()) return;
    setLoading(true); setError("");
    try {
      const res = await axios.post(`${API_URL}/bots/draft`, { description });
      setDraft(res.data.draft); setWarnings(res.data.warnings || []);
    } catch (err) {
      setError(err.response?.data?.detail || "Nie udało się przygotować profilu.");
    } finally { setLoading(false); }
  };

  const save = async () => {
    setLoading(true); setError("");
    try {
      const res = editingBot
        ? await axios.put(`${API_URL}/bots/${editingBot.id}`, draft)
        : await axios.post(`${API_URL}/bots`, draft);
      onSaved(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || "Nie udało się zapisać bota.");
    } finally { setLoading(false); }
  };

  const addOpening = (opening) => {
    if (draft.openings.some(item => item.opening_id === opening.id && item.color === openingColor)) return;
    setDraft({ ...draft, openings: [...draft.openings, { opening_id: opening.id, color: openingColor, weight: 100, name: opening.name, eco: opening.eco }] });
    setOpeningQuery(""); setOpeningResults([]);
  };

  return (
    <div className="creator-overlay" role="dialog" aria-modal="true">
      <div className="bot-creator">
        <div className="creator-heading"><h2>{editingBot ? "Edytuj bota" : "Create bot"}</h2><button onClick={onClose}>×</button></div>
        {!draft && <>
          <label>Opisz siłę, charakter, styl gry i ulubione otwarcia
            <textarea value={description} onChange={e => setDescription(e.target.value)} rows={6} placeholder="Np. waleczny pirat około 1500 Elo, lubi gambity i niechętnie wymienia hetmany..." />
          </label>
          <div className="creator-actions">
            <button className="secondary-action" onClick={() => setDraft(structuredClone(EMPTY))}>Utwórz ręcznie</button>
            <button onClick={generate} disabled={loading || !description.trim()}>{loading ? "RajkoAI tworzy..." : "Wygeneruj z RajkoAI"}</button>
          </div>
        </>}
        {draft && <div className="creator-form">
          <div className="profile-row">
            <input className="avatar-input" value={draft.avatar} onChange={e => setDraft({ ...draft, avatar: e.target.value })} />
            <label>Nazwa<input value={draft.name} onChange={e => setDraft({ ...draft, name: e.target.value })} /></label>
            <label>Orientacyjne Elo<input type="number" min="800" max="2800" value={draft.target_elo} onChange={e => setDraft({ ...draft, target_elo: Number(e.target.value) })} /></label>
          </div>
          <label>Opis<textarea rows={3} value={draft.description} onChange={e => setDraft({ ...draft, description: e.target.value })} /></label>
          <div className="style-grid">{Object.entries(draft.style).map(([key, value]) => <label key={key}>{LABELS[key]}: {value}<input type="range" min="0" max="100" value={value} onChange={e => setDraft({ ...draft, style: { ...draft.style, [key]: Number(e.target.value) } })} /></label>)}</div>
          <h3>Ulubione otwarcia</h3>
          <div className="opening-search"><select value={openingColor} onChange={e => setOpeningColor(e.target.value)}><option value="white">Białymi</option><option value="black">Czarnymi</option></select><input value={openingQuery} onChange={e => { setOpeningQuery(e.target.value); if (e.target.value.trim().length < 2) setOpeningResults([]); }} placeholder="Szukaj po nazwie lub ECO" /></div>
          {openingResults.length > 0 && <div className="opening-results">{openingResults.map(item => <button key={item.id} onClick={() => addOpening(item)}>{item.eco} · {item.name}</button>)}</div>}
          <div className="opening-chips">{draft.openings.map((item, index) => <span key={`${item.opening_id}-${item.color}`}>{item.color === "white" ? "Białe" : "Czarne"}: {item.name || item.opening_id}<button onClick={() => setDraft({ ...draft, openings: draft.openings.filter((_, i) => i !== index) })}>×</button></span>)}</div>
          <div className="creator-actions"><button className="secondary-action" onClick={onClose}>Anuluj</button><button onClick={save} disabled={loading || !draft.name || !draft.description}>{loading ? "Zapisuję..." : "Zapisz bota"}</button></div>
        </div>}
        {warnings.map(item => <p className="form-warning" key={item}>{item}</p>)}
        {error && <p className="form-error">{error}</p>}
      </div>
    </div>
  );
}
