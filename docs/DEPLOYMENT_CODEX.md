# Rajko Chess — runbook wdrożenia dla Codexa

Ten dokument prowadzi Codexa uruchomionego na docelowym serwerze Linux przez
pierwsze wdrożenie i kolejne aktualizacje zamkniętej bety. Procedury operacyjne
po uruchomieniu aplikacji znajdują się w [BETA_OPERATIONS.md](BETA_OPERATIONS.md).

## Zasady i oczekiwany rezultat

Docelowa aplikacja działa pod `https://rajko.pl/chess/`, API nasłuchuje wyłącznie
na `127.0.0.1:8000`, a PostgreSQL i Redis nie są publicznie dostępne. Cała beta,
poza bezstanowym endpointem `/chess/api/health`, jest osłonięta nginx Basic Auth.

Codex powinien wykonywać odczytowe rozpoznanie samodzielnie, ale musi zatrzymać
się i poprosić właściciela o brakujące dane lub zgodę przed:

- zmianą DNS, reguł firewalla albo konfiguracji innych aplikacji na serwerze,
- nadpisaniem istniejących plików nginx, systemd lub `/etc/rajko-chess/backend.env`,
- utworzeniem lub zmianą produkcyjnych sekretów i kont zewnętrznych,
- usunięciem bazy, backupu, katalogu aplikacji albo wykonaniem rollbacku danych.

Nie wolno umieszczać sekretów w repozytorium, komunikatach czatu, logach ani
argumentach poleceń. Nie wyświetlaj treści pliku `backend.env`; można kontrolować
jego właściciela, tryb i nazwy ustawionych zmiennych bez pokazywania wartości.

## Założenia szablonów

Pliki w `deploy/` zakładają:

| Ustawienie | Wartość szablonu |
|---|---|
| użytkownik usługi | `ubuntu` |
| repozytorium | `/home/ubuntu/Projekty/aplikacje/RajkoChess` |
| domena | `rajko.pl` i `www.rajko.pl` |
| ścieżka aplikacji | `/chess/` |
| frontend | `/var/www/rajko-chess/chess` |
| konfiguracja sekretów | `/etc/rajko-chess/backend.env` |
| backupy | `/var/backups/rajko-chess` |

Na początku sprawdź te wartości przez `whoami`, `pwd`, `hostnamectl`, aktywne
virtual hosty nginx i jednostki systemd. Jeśli serwer ma inne wartości, popraw
kopie szablonów przed ich instalacją. Nie zmieniaj w ciemno konfiguracji usług,
które nie należą do Rajko Chess.

## 1. Rozpoznanie serwera

Zapisz wynik bez sekretów:

```bash
uname -a
lsb_release -a
df -h
free -h
git --version
python3 --version
node --version
npm --version
nginx -v
psql --version
redis-cli --version
stockfish <<< quit
sudo systemctl --no-pager status nginx postgresql redis-server
sudo ss -lntup
```

Wymagane są Python 3.11+, Node.js 20+ (zalecany 22 LTS), npm, Git, nginx,
PostgreSQL 16, klient PostgreSQL zawierający `pg_dump` i `pg_restore`, Redis 7,
Stockfish, `rsync`, `curl`, `certbot` i `apache2-utils`. Instaluj pakiety zgodnie
z dystrybucją serwera; nie obniżaj istniejących wersji. Porty 5432, 6379 i 8000
mają pozostać zamknięte z Internetu.

Sprawdź, czy DNS obu nazw wskazuje na ten serwer, zanim zamówisz certyfikat:

```bash
getent ahosts rajko.pl
getent ahosts www.rajko.pl
```

## 2. Pobranie kodu i wybór wersji

Repozytorium: `git@github.com:nenow79/RajkoChess.git`, gałąź wdrożeniowa:
`main`. Użyj osobnego klucza deploy key z prawem tylko do odczytu, jeżeli serwer
nie ma jeszcze dostępu do GitHub. Nie kopiuj prywatnego klucza właściciela.

Przy pierwszej instalacji:

```bash
sudo install -d -o ubuntu -g ubuntu /home/ubuntu/Projekty/aplikacje
cd /home/ubuntu/Projekty/aplikacje
git clone git@github.com:nenow79/RajkoChess.git
cd RajkoChess
git switch main
git status --short
git log -1 --oneline
```

Repozytorium musi być czyste. Sprawdź w GitHub Actions, że dokładnie ten commit
ma zielone joby `backend` i `frontend`. Nie wdrażaj commita z trwającym lub
nieudanym CI. Na serwerze produkcyjnym nie edytuj śledzonych plików ręcznie.

## 3. PostgreSQL i Redis

Utwórz osobną rolę logowania i bazę `rajko_chess`. Hasło wygeneruj bezpiecznym
generatorem i wpisz bezpośrednio do PostgreSQL oraz pliku env; nie zapisuj go w
historii powłoki ani w tym dokumencie. Przykładowy przebieg interaktywny:

```bash
sudo -u postgres psql
```

W konsoli `psql` wykonaj, podstawiając hasło interaktywnie:

```sql
CREATE ROLE rajko_chess LOGIN PASSWORD 'WARTOŚĆ_WPROWADZONA_BEZPIECZNIE';
CREATE DATABASE rajko_chess OWNER rajko_chess;
\q
```

Jeśli rola lub baza już istnieje, nie twórz ich ponownie i nie zmieniaj hasła
bez zgody właściciela. PostgreSQL i Redis powinny słuchać wyłącznie lokalnie.

```bash
sudo systemctl enable --now postgresql redis-server
redis-cli ping
sudo -u postgres psql -d rajko_chess -c 'select current_database();'
```

## 4. Sekrety i katalogi stanu

Utwórz konfigurację z szablonu, nie nadpisując istniejącego pliku:

```bash
sudo install -d -m 0700 -o root -g root /etc/rajko-chess
sudo install -m 0600 -o root -g root deploy/backend.env.example /etc/rajko-chess/backend.env
sudoedit /etc/rajko-chess/backend.env
sudo install -d -m 0750 -o ubuntu -g ubuntu /var/lib/rajko-chess
sudo install -d -m 0700 -o root -g root /var/backups/rajko-chess
```

W `backend.env` wymagają świadomego ustawienia co najmniej:

- wszystkie `POSTGRES_*`; dla lokalnej bazy użyj `POSTGRES_HOST=127.0.0.1`,
- `RATE_LIMIT_KEY_SECRET` — losowa wartość co najmniej 32-znakowa,
- `PUBLIC_APP_URL=https://rajko.pl/chess`,
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` i dokładny
  `GOOGLE_OAUTH_REDIRECT_URI=https://rajko.pl/chess/api/auth/google/callback`;
  ten sam URI musi być wpisany w Google Cloud Console,
- prawdziwe dane SMTP i adres nadawcy,
- produkcyjny `OPENROUTER_API_KEY` z twardym limitem wydatków u dostawcy,
- `OPENROUTER_HTTP_REFERER=https://rajko.pl/chess/`,
- `AUTH_COOKIE_SECURE=true` oraz nazwy cookie z prefiksem `__Host-`,
- poprawna ścieżka `STOCKFISH_PATH`.

`LICHESS_API_TOKEN` jest opcjonalny. Dane Google OAuth można pozostawić puste,
aby ukryć logowanie Google. Nie uruchamiaj bety bez działającej poczty
weryfikacyjnej. Po edycji sprawdź wyłącznie metadane pliku:

```bash
sudo stat -c '%U %G %a %n' /etc/rajko-chess/backend.env
```

Oczekiwany wynik zaczyna się od `root root 600`.

## 5. nginx Basic Auth i TLS

Najpierw utwórz dane wejściowe zamkniętej bety. Polecenie zapyta o hasło — nie
podawaj go w linii poleceń:

```bash
sudo htpasswd -c /etc/nginx/rajko-chess.htpasswd beta
sudo chmod 0640 /etc/nginx/rajko-chess.htpasswd
sudo chown root:www-data /etc/nginx/rajko-chess.htpasswd
sudo install -d -m 0755 /var/www/letsencrypt /var/www/rajko-chess/chess
```

Jeśli certyfikat jeszcze nie istnieje, zacznij od konfiguracji HTTP:

```bash
sudo cp deploy/nginx/rajko-chess-http-acme.conf /etc/nginx/sites-available/rajko-chess.conf
sudo ln -s /etc/nginx/sites-available/rajko-chess.conf /etc/nginx/sites-enabled/rajko-chess.conf
sudo nginx -t
sudo systemctl reload nginx
sudo certbot certonly --webroot -w /var/www/letsencrypt -d rajko.pl -d www.rajko.pl
```

Istniejącego dowiązania nie twórz ponownie. Po uzyskaniu certyfikatu zainstaluj
konfigurację HTTPS, sprawdź ją przed przeładowaniem i skontroluj odnowienie:

```bash
sudo cp deploy/nginx/rajko-chess.conf /etc/nginx/sites-available/rajko-chess.conf
sudo nginx -t
sudo systemctl reload nginx
sudo certbot renew --dry-run
```

Jeżeli domena, ścieżka certyfikatu lub układ istniejących virtual hostów jest
inny, dostosuj plik po rozpoznaniu i pokaż właścicielowi różnicę przed instalacją.

## 6. systemd i pierwsze wdrożenie

Przed kopiowaniem sprawdź `User`, `Group`, `WorkingDirectory` i `ExecStart` we
wszystkich jednostkach. Po dopasowaniu zainstaluj je:

```bash
sudo cp deploy/systemd/rajko-chess-backend.service /etc/systemd/system/
sudo cp deploy/systemd/rajko-chess-{backup,health}.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rajko-chess-backend.service
sudo systemctl enable --now rajko-chess-backup.timer rajko-chess-health.timer
```

Skrypt `deploy/deploy.sh` ładuje produkcyjne zmienne bezpośrednio z chronionego
pliku przez `sudo`, uruchamia testy i diagnostykę, buduje frontend, sprawdza
nginx, wykonuje backup przed migracją, aktualizuje Alembic, publikuje frontend,
restartuje API i sprawdza healthcheck. Uruchom go jako użytkownik repozytorium,
nie jako root:

```bash
cd /home/ubuntu/Projekty/aplikacje/RajkoChess
deploy/deploy.sh --no-pull
```

`--no-pull` jest właściwe przy pierwszym wdrożeniu, bo dokładny commit został
już pobrany i sprawdzony. Przy kolejnych aktualizacjach zwykle używaj
`deploy/deploy.sh`; skrypt odmówi pracy przy brudnym repozytorium i wykona tylko
aktualizację Git typu fast-forward.

Jeśli skrypt przerwie pracę, nie omijaj pominiętego kroku. Ustal przyczynę,
popraw ją i uruchom całość ponownie. Gdy awaria nastąpi po migracji lub
publikacji, najpierw sprawdź status backendu, nginx i ostatni backup.

## 7. Kontrola po wdrożeniu

```bash
git status --short
git log -1 --oneline
sudo systemctl --no-pager --full status rajko-chess-backend.service
sudo systemctl list-timers 'rajko-chess-*'
sudo journalctl -u rajko-chess-backend.service --since '15 minutes ago' --no-pager
curl --fail --silent --show-error https://rajko.pl/chess/api/health
curl -I https://rajko.pl/chess/
```

Healthcheck ma zwrócić `200`. Wejście na aplikację bez Basic Auth ma zwrócić
`401`, a z poprawnymi danymi — frontend. Następnie wykonaj pełny ręczny smoke
test z `BETA_OPERATIONS.md`, w tym rejestrację, wiadomość e-mail, limity Free,
grant Premium, import Chess.com/PGN, pełną analizę, grę z botem, historię i wpis
audytowy administratora. W logach nie mogą występować sekrety, tokeny ani pełne
dane użytkowników.

Pierwsze konto administratora tworzy się przez zwykłą rejestrację i dopiero po
weryfikacji nadaje mu rolę bezpośrednio w PostgreSQL zgodnie z sekcją
„Nadanie pierwszej roli administratora” w głównym `README.md`. Nie dodawaj
publicznego mechanizmu samodzielnego wyboru roli.

Przed zaproszeniem testerów dodatkowo muszą istnieć:

- udany backup i próbne odtworzenie do osobnej bazy,
- szyfrowana kopia backupu poza serwerem,
- zewnętrzny monitor HTTPS z alarmem e-mail/SMS i kontrolą certyfikatu,
- uzupełnione dokumenty prywatności i warunków bety,
- osoba i kanał odbierające zgłoszenia testerów oraz alarmy.

## 8. Raport dla właściciela

Po wdrożeniu Codex powinien podać:

- wdrożony hash i tytuł commita oraz wynik CI,
- adres aplikacji i wynik publicznego healthchecku,
- status backendu, nginx, PostgreSQL, Redis i timerów,
- czas i ścieżkę ostatniego backupu oraz wynik próby odtworzenia,
- wykonane smoke testy i ich wynik,
- elementy pozostawione do decyzji właściciela.

Raport nie może zawierać haseł, kluczy API, tokenów, wartości cookie ani danych
osobowych testerów.

## Rollback i incydent

Nie wykonuj automatycznie `alembic downgrade`, nie usuwaj aktualnej bazy i nie
przywracaj backupu nad działającą bazą. Przy nieudanym wdrożeniu zachowaj logi i
backup sprzed migracji, wstrzymaj zaproszenia i ustal, czy problem dotyczy kodu,
konfiguracji czy danych. Powrót do wcześniejszego commita lub odtworzenie danych
wymaga zgody właściciela i procedury z sekcji „Incydent” w
`BETA_OPERATIONS.md`.
