# Rajko Chess

Aplikacja webowa do analizy szachowej i gry ze spersonalizowanymi botami. Frontend działa w React/Vite, backend w FastAPI, ruchy i analizy oblicza lokalny Stockfish, a funkcje LLM korzystają z OpenRouter API.

## Funkcje

- interaktywna szachownica z historią ruchów,
- analiza pozycji przez Stockfish z wariantami MultiPV,
- statystyki debiutowe z Lichess Opening Explorer,
- import ostatnich partii z Chess.com,
- import i analiza zakończonej partii PGN,
- czat trenerski LLM oparty o dane z pozycji, Lichess i Stockfisha,
- osobny tryb gry ze spersonalizowanymi botami o regulowanej sile, stylu i repertuarze,
- kreator botów wspierany przez LLM oraz trwały katalog profili w SQLite,
- lokalny katalog 3790 linii debiutowych z projektu `lichess-org/chess-openings`,
- przekazanie zakończonej partii z botem bezpośrednio do trybu analizy.

## Tryby aplikacji

### Analiza

Udostępnia obecną szachownicę analityczną, MultiPV Stockfisha, Lichess Opening Explorer, import partii Chess.com i trenera RajkoAI. Zaimportowane partie można przewijać, analizować w całości i rozgrywać od nich własne warianty.

### Gra z botem

Pozwala wybrać bota oraz kolor gracza (`białe`, `czarne` lub `losowo`). W tym trybie nie są wyświetlane ani odpytywane panele analizy, Lichess Explorer i Chess.com. Stockfish działa wyłącznie po stronie backendu i nie ujawnia ocen ani wariantów.

Każdy bot ma:

- orientacyjną siłę 800–2800 Elo,
- parametry agresji, taktyki, ryzyka, materializmu i skłonności do uproszczeń,
- osobny repertuar dla białych i czarnych,
- krótkie kwestie dopasowane do osobowości.

Przycisk `Create bot` pozwala opisać bota naturalnym językiem. RajkoAI przygotowuje nazwę, siłę, styl, kwestie i repertuar, po czym użytkownik może poprawić wszystkie ustawienia przed zapisem. Bez klucza OpenRouter boty można nadal tworzyć ręcznie.

## Wymagania

- Python 3.11+,
- Node.js 20+ i npm,
- Stockfish zainstalowany lokalnie,
- klucz OpenRouter API, jeśli chcesz używać panelu LLM lub automatycznego kreatora botów.

## Konfiguracja

Utwórz plik `backend/.env` na podstawie `backend/.env.example`:

```bash
cp backend/.env.example backend/.env
```

Ustaw ścieżkę do binarki Stockfisha:

```env
STOCKFISH_PATH=/usr/games/stockfish
```

Pełna konfiguracja może wyglądać tak:

```env
OPENROUTER_API_KEY=sk-or-...
LLM_MODEL=google/gemini-3-flash-preview
BOT_DB_PATH=./data/bots.sqlite3
LICHESS_API_TOKEN=
```

`LLM_MODEL` jest opcjonalny. Jeśli go nie ustawisz, backend użyje modelu domyślnego z kodu.
Jeśli masz token Lichess, dodaj też `LICHESS_API_TOKEN`; Explorer działa bez niego, ale token pozwala autoryzować zapytania.

`BOT_DB_PATH` wskazuje bazę SQLite ze wspólnymi profilami botów. Przy pierwszym uruchomieniu backend automatycznie tworzy schemat oraz trzy profile startowe. Aktywne partie są trzymane w pamięci i kończą się przy restarcie backendu, natomiast profile botów pozostają zapisane.

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
cd backend && ../.venv/bin/python -m unittest discover -s tests -v
```

Opcjonalnie można zainstalować zależności developerskie i uruchomić testy przez pytest:

```bash
. .venv/bin/activate
pip install -r backend/requirements-dev.txt
cd backend && pytest
```

### Aktualizacja katalogu otwarć

Plik `backend/data/openings.json` jest wersjonowaną kopią danych CC0 z projektu [`lichess-org/chess-openings`](https://github.com/lichess-org/chess-openings). Aby go odtworzyć, pobierz pliki `a.tsv`–`e.tsv` do jednego katalogu i uruchom:

```bash
.venv/bin/python backend/scripts/update_openings.py /ścieżka/do/plików-tsv backend/data/openings.json
```

## Wdrożenie pod `/chess/`

Rekomendowany układ produkcyjny:

- frontend: statyczny build Vite pod `https://rajko.pl/chess/`,
- backend: FastAPI jako usługa `systemd` na `127.0.0.1:8000`,
- nginx: reverse proxy z `/chess/api/` do backendowego `/api/`.

Build frontendu:

```bash
cd frontend
cp env.production.example .env.production
npm ci
npm run build
sudo mkdir -p /var/www/rajko-chess/chess
sudo rsync -a --delete dist/ /var/www/rajko-chess/chess/
```

Backend:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
sudo mkdir -p /etc/rajko-chess
sudo cp deploy/backend.env.example /etc/rajko-chess/backend.env
```

Uzupełnij `/etc/rajko-chess/backend.env`, szczególnie `STOCKFISH_PATH` oraz opcjonalnie `OPENROUTER_API_KEY` i `LICHESS_API_TOKEN`. Profile botów są przechowywane w SQLite. Przykładowa usługa systemd tworzy trwały katalog `/var/lib/rajko-chess`, zgodny z `BOT_DB_PATH` z pliku przykładowego. Bazę warto dołączyć do regularnych kopii zapasowych.
Jeśli używasz LLM, ustaw też `OPENROUTER_HTTP_REFERER` na publiczny adres aplikacji, np. `https://rajko.pl/chess/`.

Przykładowe pliki produkcyjne są w:

- `deploy/nginx/rajko-chess.conf`,
- `deploy/systemd/rajko-chess-backend.service`.

Konfiguracja nginx zakłada HTTPS przez certyfikat Let’s Encrypt dla `rajko.pl` i `www.rajko.pl`. Certyfikat możesz wystawić np. tak:

```bash
sudo mkdir -p /var/www/letsencrypt
sudo certbot certonly --webroot -w /var/www/letsencrypt -d rajko.pl -d www.rajko.pl
sudo cp deploy/nginx/rajko-chess.conf /etc/nginx/sites-available/rajko-chess.conf
sudo ln -s /etc/nginx/sites-available/rajko-chess.conf /etc/nginx/sites-enabled/rajko-chess.conf
sudo nginx -t
sudo systemctl reload nginx
```

Port 80 pozostaje aktywny dla odnowień certyfikatu i przekierowuje ruch aplikacji na `https://`.

Przed użyciem usługi `systemd` dostosuj w niej `User`, `Group`, `WorkingDirectory` i ścieżkę do `.venv`, jeśli aplikacja leży gdzie indziej niż w tym repozytorium.

## Struktura projektu

```text
backend/              FastAPI, logika gry, boty i integracje z usługami
backend/chess_logic/  Stockfish, partie, profile botów, Lichess i OpenRouter
backend/data/         wersjonowany katalog otwarć i lokalna baza SQLite
backend/tests/        testy profili i przebiegu gry z botem
frontend/             React + Vite oraz ekrany analizy i gry
deploy/               przykładowa konfiguracja nginx i systemd
start.sh              lokalne uruchomienie frontendu i backendu
```

## Uwagi przed publikacją

Pliki `.env`, bazy SQLite i ich pliki WAL są ignorowane przez Git. Nie commituj kluczy API, lokalnych ścieżek do Stockfisha ani produkcyjnej bazy botów. Do repo powinny trafiać wyłącznie pliki przykładowej konfiguracji.
