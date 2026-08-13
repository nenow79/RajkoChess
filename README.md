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
- opcjonalne komentarze LLM botów przy najważniejszych momentach partii,
- kreator botów wspierany przez LLM oraz trwały katalog profili w PostgreSQL,
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
- PostgreSQL i Redis,
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
BOT_COMMENTARY_MODEL=sao10k/l3-lunaris-8b
LICHESS_API_TOKEN=
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=chess_app
POSTGRES_USER=chess_app
POSTGRES_PASSWORD=
POSTGRES_SSLMODE=prefer
```

`LLM_MODEL` jest opcjonalny. Jeśli go nie ustawisz, backend użyje modelu domyślnego z kodu.
`BOT_COMMENTARY_MODEL` wybiera model krótkich komentarzy w trybie gry z botem.
Jeśli masz token Lichess, dodaj też `LICHESS_API_TOKEN`; Explorer działa bez niego, ale token pozwala autoryzować zapytania.

Profile botów są przechowywane w PostgreSQL. Zwykły użytkownik widzi boty
publiczne i własne prywatne; może tworzyć, edytować i usuwać wyłącznie własne
boty prywatne. Botami publicznymi zarządza administrator. Aktywne partie nadal
są trzymane w pamięci i kończą się przy restarcie backendu.

Pola `POSTGRES_*` konfigurują docelową bazę danych kont i danych użytkowników.
Po uzupełnieniu danych połączenie można sprawdzić bez modyfikowania bazy:

```bash
cd backend
../.venv/bin/python -m scripts.check_database
```

Migracje PostgreSQL są obsługiwane przez Alembic:

```bash
cd backend
../.venv/bin/alembic current
../.venv/bin/alembic upgrade head
```

Przy przejściu ze starszej wersji można idempotentnie przenieść dotychczasowy
katalog SQLite. Ze względu na brak historycznych danych właściciela wszystkie
takie profile zostaną publicznymi botami systemowymi:

```bash
cd backend
../.venv/bin/python -m scripts.migrate_bots_to_postgres
```

### Test logowania w Swagger UI

Po uruchomieniu backendu otwórz `http://127.0.0.1:8000/docs` i rozwiń sekcję
`Authentication`:

1. Skonfiguruj SMTP zgodnie z sekcją „Weryfikacja e-maila” poniżej.
2. Wywołaj `POST /api/auth/register`. Hasło musi mieć co najmniej 10 znaków.
3. Otwórz link otrzymany w wiadomości. Frontend wywoła
   `POST /api/auth/email-verification/confirm` i jednorazowo zużyje token.
4. Wywołaj `POST /api/auth/login` tym samym adresem i hasłem. Odpowiedź zawiera
   `csrf_token`, a przeglądarka automatycznie zapisuje bezpieczne cookie sesji.
5. Wywołaj `GET /api/auth/me`. Powinien zwrócić dane zalogowanego użytkownika.
6. Aby sprawdzić wylogowanie, wywołaj `POST /api/auth/logout` i w polu
   `X-CSRF-Token` wklej wartość `csrf_token` zwróconą przez logowanie.
7. Ponowne `GET /api/auth/me` powinno zwrócić `401`.

W razie utraty tokenu CSRF zalogowany użytkownik może go odczytać przez
`GET /api/auth/csrf`. Swagger działa na tym samym originie co API, dlatego cookie
`HttpOnly` jest przesyłane automatycznie i nie trzeba wpisywać go w formularzu.
Przycisk `Authorize` nie służy do tego przepływu: Swagger UI nie potrafi ustawić
cookie uwierzytelniającego przez „Try it out” z powodu ograniczeń przeglądarki.

### Weryfikacja e-maila

Backend wysyła wiadomości przez uwierzytelnione SMTP z SSL/TLS. W lokalnym
`backend/.env` lub w `/etc/rajko-chess/backend.env` ustaw:

```dotenv
PUBLIC_APP_URL=https://twoj-publiczny-adres.example
SMTP_HOST=smtp.mail.ovh.net
SMTP_PORT=465
SMTP_USERNAME=noreply@rajko.pl
SMTP_PASSWORD=uzupelnij-wylacznie-w-sekretnym-pliku-env
SMTP_FROM_EMAIL=noreply@rajko.pl
SMTP_FROM_NAME=Rajko Chess
EMAIL_VERIFICATION_HOURS=24
PASSWORD_RESET_MINUTES=60
REDIS_URL=redis://127.0.0.1:6379/0
RATE_LIMIT_KEY_SECRET=ustaw-długi-losowy-sekret
```

Nie wpisuj hasła SMTP do repozytorium. Nowe konto nie może się zalogować przed
potwierdzeniem adresu. Link jest jednorazowy; wygasa domyślnie po 24 godzinach.
Nowy link można zamówić przez `POST /api/auth/email-verification/resend`.
Odpowiedź tego endpointu jest jednakowa niezależnie od tego, czy konto istnieje.

Migracja `20260812_0004` oznacza konta istniejące przed wdrożeniem jako
zweryfikowane, dzięki czemu aktualni użytkownicy nie tracą dostępu.

### Reset hasła

Na ekranie logowania wybierz „Nie pamiętasz hasła?” i podaj adres e-mail.
Odpowiedź jest jednakowa niezależnie od tego, czy aktywne i zweryfikowane konto
istnieje. Jeśli konto kwalifikuje się do resetu, backend wysyła przez SMTP
jednorazowy link do ekranu `/reset-password`.

Token jest przechowywany wyłącznie jako hash i domyślnie wygasa po 60 minutach.
Udane ustawienie nowego hasła zużywa wszystkie aktywne tokeny resetu danego
użytkownika oraz unieważnia wszystkie jego sesje. Nowe hasło podlega tym samym
regułom co podczas rejestracji: ma od 10 do 128 znaków i nie może znajdować się
na lokalnej liście najczęściej używanych haseł. Czas ważności można ustawić
zmienną `PASSWORD_RESET_MINUTES` w zakresie od 1 do 1440 minut.

Do ręcznego testu pełnego przepływu:

1. Na ekranie logowania wybierz „Nie pamiętasz hasła?”.
2. Podaj adres istniejącego, zweryfikowanego konta.
3. Otwórz dostarczony link i ustaw nowe hasło.
4. Sprawdź, że stare hasło nie działa, a nowe pozwala się zalogować.
5. Jeśli konto miało sesję w innej przeglądarce, sprawdź, że została
   unieważniona.

### Nadanie pierwszej roli administratora

Konto należy najpierw utworzyć zwykłym endpointem rejestracji. Następnie rolę
można nadać bezpośrednio w PostgreSQL:

```sql
UPDATE users
SET system_role = 'admin', updated_at = now()
WHERE email = lower('twoj-email@example.com');
```

Wynik można sprawdzić przez `GET /api/auth/me` albo zapytaniem:

```sql
SELECT id, email, system_role, status
FROM users
WHERE email = lower('twoj-email@example.com');
```

Roli administratora nie wolno przyjmować z publicznego formularza rejestracji.
Rola jest już egzekwowana przy zarządzaniu publicznymi botami. Pełne polityki
administracyjne są dostępne pod `/api/admin`:

- `GET /api/admin/users` — lista użytkowników,
- `PATCH /api/admin/users/{id}` — zmiana roli lub statusu z obowiązkowym powodem,
- `GET /api/admin/users/{id}/entitlements` oraz
  `PUT /api/admin/users/{id}/entitlements/{key}` — podgląd i ręczne nadawanie
  uprawnień produktowych,
- `POST /api/admin/bots/{id}/inspect` — jawny, audytowany dostęp do prywatnego
  bota z obowiązkowym powodem,
- `GET /api/admin/audit-log` — dziennik operacji administracyjnych.

Operacje zmieniające stan wymagają cookie sesji oraz `X-CSRF-Token`. Nie można
zmienić własnej roli ani zablokować własnego konta przez API administratora.
Zablokowanie użytkownika unieważnia jego aktywne sesje.

Uprawnienia produktowe są niezależne od nazw planów. Początkowy rejestr obejmuje
`basic_analysis`, `ai_game_review`, `custom_bot`, `training_plan` i
`priority_analysis`. Administrator omija ograniczenia produktowe, ale nadal
podlega kontrolom sesji, CSRF i audytowi.

### Free, Premium i limity bety

Każdy użytkownik bez aktywnego grantu Premium korzysta automatycznie z Free.
Administrator może w panelu „Administracja” przyznać Premium na wybraną liczbę
dni, przedłużyć aktywny okres albo go odwołać. Po terminie konto automatycznie
wraca do Free. Wszystkie te operacje wymagają powodu i trafiają do `audit_log`.

| Funkcja | Free | Premium |
|---|---:|---:|
| Pełna analiza partii AI | 3/miesiąc | 30/miesiąc |
| Pytania do trenera AI | 10/miesiąc | 100/miesiąc |
| Generowanie bota przez AI | 1/miesiąc | 10/miesiąc |
| Własne prywatne boty | 1 łącznie | 10 łącznie |
| Komentarze AI podczas gry | wyłączone | 100/miesiąc |

Zużycie jest zapisywane w PostgreSQL w `usage_events` i odnawia się pierwszego
dnia miesiąca według UTC. Administrator omija miesięczne limity produktu, ale
nadal podlega limitom bezpieczeństwa i blokadom współbieżności.
Liczniki Free i Premium są rozdzielone: przejście na Premium udostępnia pełny
limit Premium, a późniejszy powrót do Free przywraca wcześniejsze zużycie Free z
tego samego miesiąca.

### Redis i rate limiting

Redis przechowuje wyłącznie krótkotrwałe liczniki i blokady współbieżności. Nie
przechowuje haseł, sesji ani treści partii. Na Ubuntu lub Linux Mint zainstaluj:

```bash
sudo apt update
sudo apt install redis-server
sudo systemctl enable --now redis-server
redis-cli ping
```

Ostatnia komenda powinna zwrócić `PONG`. Redis powinien nasłuchiwać wyłącznie na
`127.0.0.1`; nie otwieraj portu 6379 w firewallu ani routerze. Połączenie
aplikacji można sprawdzić poleceniem:

```bash
cd backend
../.venv/bin/python -m scripts.check_redis
```

Backend ogranicza próby logowania, rejestracji, ponownej weryfikacji i resetu
hasła per IP oraz per konto. Stockfish i LLM mają limity per użytkownik oraz
rozproszoną blokadę jednej równoległej operacji. Odpowiedź `429` zawiera
`Retry-After`. Przy awarii Redis logowanie pozostaje chronione przez nginx,
natomiast rejestracja, poczta oraz kosztowne operacje zwracają bezpieczne `503`.

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

Po jednorazowym skonfigurowaniu systemd i Nginx kolejne wersje można wdrażać
automatycznie:

```bash
./deploy/deploy.sh
```

Skrypt pobiera i scala zmiany z Git, aktualizuje zależności Pythona i Node.js,
buduje frontend, synchronizuje go do `/var/www/rajko-chess/chess`, restartuje
API oraz sprawdza i przeładowuje Nginx. Aby wdrożyć bieżący lokalny kod bez
wykonywania `git pull`, użyj `./deploy/deploy.sh --no-pull`.

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

Uzupełnij `/etc/rajko-chess/backend.env`, szczególnie `STOCKFISH_PATH`,
`POSTGRES_*`, `REDIS_URL` i `RATE_LIMIT_KEY_SECRET` oraz opcjonalnie
`OPENROUTER_API_KEY` i `LICHESS_API_TOKEN`. Profile botów, plany oraz zdarzenia
użycia są przechowywane w PostgreSQL. Redis obsługuje tylko krótkotrwałe
liczniki i blokady.
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

## Strona demo na `rajko.cloud`

Publiczny landing page znajduje się w `deploy/www-demo/`. Nie wymaga Node.js
ani backendu i prowadzi do aplikacji pod `https://rajko.pl/chess/`.

Przed wdrożeniem rekordy DNS `A` (oraz opcjonalnie `AAAA`) dla `rajko.cloud`
i `www.rajko.cloud` muszą wskazywać serwer nginx. Następnie:

```bash
sudo mkdir -p /var/www/rajko-cloud /var/www/letsencrypt
sudo rsync -a --delete deploy/www-demo/ /var/www/rajko-cloud/
sudo cp deploy/nginx/rajko-cloud-http-acme.conf \
  /etc/nginx/sites-available/rajko-cloud.conf
sudo ln -s /etc/nginx/sites-available/rajko-cloud.conf \
  /etc/nginx/sites-enabled/rajko-cloud.conf
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt \
  -d rajko.cloud -d www.rajko.cloud
sudo cp deploy/nginx/rajko-cloud.conf /etc/nginx/sites-available/
sudo nginx -t
sudo systemctl reload nginx
```

## Struktura projektu

```text
backend/              FastAPI, logika gry, boty i integracje z usługami
backend/chess_logic/  Stockfish, partie, profile botów, Lichess i OpenRouter
backend/data/         wersjonowany katalog otwarć
backend/tests/        testy profili i przebiegu gry z botem
frontend/             React + Vite oraz ekrany analizy i gry
deploy/               przykładowa konfiguracja nginx i systemd
start.sh              lokalne uruchomienie frontendu i backendu
```

## Uwagi przed publikacją

Pliki `.env`, bazy SQLite i ich pliki WAL są ignorowane przez Git. Nie commituj kluczy API, lokalnych ścieżek do Stockfisha ani produkcyjnej bazy botów. Do repo powinny trafiać wyłącznie pliki przykładowej konfiguracji.
