import { useRef, useState, type FormEvent, type MouseEvent } from "react";

type ImportFormat = "pgn" | "fen";

interface ManualImportPanelProps {
  onImport: (format: ImportFormat, value: string) => Promise<void>;
}

export default function ManualImportPanel({ onImport }: ManualImportPanelProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [format, setFormat] = useState<ImportFormat>("pgn");
  const [value, setValue] = useState("");
  const [isImporting, setIsImporting] = useState(false);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = value.trim();
    if (!normalized || isImporting) return;
    setIsImporting(true);
    try {
      await onImport(format, normalized);
      setValue("");
      setIsOpen(false);
    } catch {
      // The workspace displays the normalized backend error above the board.
    } finally {
      setIsImporting(false);
    }
  };

  return (
    <section className="side-panel manual-import-panel">
      <div className="chesscom-header">
        <div>
          <h3 className="panel-title">Własna partia lub pozycja</h3>
          <small>Wklej PGN z dowolnego serwisu albo pojedynczą pozycję FEN.</small>
        </div>
        <button type="button" className="chesscom-open" onClick={() => setIsOpen(true)}>
          Importuj
        </button>
      </div>

      {isOpen && (
        <div className="chesscom-modal-backdrop" onMouseDown={() => setIsOpen(false)}>
          <div
            className="chesscom-modal manual-import-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="manual-import-title"
            onMouseDown={(event: MouseEvent<HTMLDivElement>) => event.stopPropagation()}
          >
            <div className="chesscom-modal-header">
              <h2 id="manual-import-title">Importuj PGN lub FEN</h2>
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
            <form className="manual-import-form" onSubmit={handleSubmit}>
              <div className="auth-tabs" aria-label="Format importu">
                <button type="button" className={format === "pgn" ? "active" : ""} onClick={() => setFormat("pgn")}>Cała partia PGN</button>
                <button type="button" className={format === "fen" ? "active" : ""} onClick={() => setFormat("fen")}>Pozycja FEN</button>
              </div>
              <label>
                {format === "pgn" ? "Zapis partii" : "Pozycja szachowa"}
                <textarea
                  value={value}
                  onChange={(event) => setValue(event.target.value)}
                  maxLength={format === "pgn" ? 200_000 : 128}
                  rows={format === "pgn" ? 12 : 4}
                  placeholder={format === "pgn"
                    ? "[Event \"...\"]\n\n1. e4 e5 2. Nf3 ..."
                    : "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"}
                  disabled={isImporting}
                  autoFocus
                />
              </label>
              <p>
                {format === "pgn"
                  ? "Partia zostanie zapisana w Twojej historii i może mieć trwałą rozmowę z RajkoAI."
                  : "FEN ustawi szachownicę do analizy, ale nie będzie zapisany jako pełna partia."}
              </p>
              <button type="submit" className="chesscom-user-submit" disabled={!value.trim() || isImporting}>
                {isImporting ? "Importuję…" : "Otwórz na szachownicy"}
              </button>
            </form>
          </div>
        </div>
      )}
    </section>
  );
}
