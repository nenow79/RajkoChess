# Chess App

Aplikacja webowa do analizy szachowej. Frontend działa w React/Vite, backend w FastAPI, a analiza pozycji i partii korzysta ze Stockfisha. Panel LLM używa OpenRouter API.

## Funkcje

- interaktywna szachownica z historią ruchów,
- analiza pozycji przez Stockfish z wariantami MultiPV,
- statystyki debiutowe z Lichess Opening Explorer,
- import ostatnich partii z Chess.com,
- import i analiza zakończonej partii PGN,
- czat trenerski LLM oparty o dane z pozycji, Lichess i Stockfisha.

## Wymagania

- Python 3.11+,
- Node.js 20+ i npm,
- Stockfish zainstalowany lokalnie,
- klucz OpenRouter API, jeśli chcesz używać panelu LLM.

## Konfiguracja

Utwórz plik `backend/.env` na podstawie `backend/.env.example`:

```bash
cp backend/.env.example backend/.env
```

Ustaw ścieżkę do binarki Stockfisha:

```env
STOCKFISH_PATH=/usr/games/stockfish
```

Dla funkcji LLM dodaj:

```env
OPENROUTER_API_KEY=sk-or-...
LLM_MODEL=openai/gpt-5.4-mini
```

`LLM_MODEL` jest opcjonalny. Jeśli go nie ustawisz, backend użyje modelu domyślnego z kodu.

## Szybkie uruchomienie

Najprościej uruchomić oba serwery skryptem:

```bash
chmod +x start.sh
./start.sh
```

Skrypt utworzy `.venv`, zainstaluje zależności Pythona i npm, uruchomi backend oraz frontend.

Domyślne adresy:

- frontend: `http://127.0.0.1:5173`,
- backend API: `http://127.0.0.1:8000`.

## Uruchomienie ręczne

Backend:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
cd backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Vite proxy domyślnie kieruje zapytania `/api` do `http://127.0.0.1:8000`.

## Przydatne komendy

```bash
cd frontend && npm run lint
cd frontend && npm run build
```

## Struktura projektu

```text
backend/   FastAPI, logika gry, integracje Stockfish/Lichess/Chess.com/OpenRouter
frontend/  React + Vite
start.sh   lokalne uruchomienie frontendu i backendu
```

## Uwagi przed publikacją

Pliki `.env` są ignorowane przez Git. Nie commituj kluczy API ani lokalnych ścieżek do Stockfisha. Do repo powinien trafić tylko `backend/.env.example`.
