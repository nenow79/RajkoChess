# Rajko Chess — procedura operacyjna zamkniętej bety

Dokument dotyczy bezpłatnej, zamkniętej bety na 30–50 zaproszonych kont. Nie
jest checklistą uruchomienia publicznej sprzedaży.

Pierwszą instalację serwera i kolejne aktualizacje wykonuje się według
[runbooka wdrożenia dla Codexa](DEPLOYMENT_CODEX.md). Ten dokument opisuje
warunki dopuszczenia testerów oraz późniejszą obsługę działającej bety.

## Warunki rozpoczęcia

- repozytorium na serwerze jest czyste, a wdrażany commit przeszedł CI,
- PostgreSQL, Redis, Stockfish, SMTP i opcjonalnie OpenRouter mają produkcyjną
  konfigurację; plik `/etc/rajko-chess/backend.env` ma tryb `0600`,
- dodatkowe hasło nginx Basic Auth jest obecnie wyłączone; wejście na stronę
  i formularz rejestracji jest publiczne (przywrócenie ochrony opisuje runbook),
- administrator uzupełnił wszystkie pola `[UZUPEŁNIJ]` w dokumentach dla
  testerów i udostępnił je przed utworzeniem konta,
- wskazana osoba odbiera zgłoszenia testerów oraz alarmy infrastruktury,
- klucz OpenRouter ma ustawiony w panelu dostawcy twardy limit kredytów właściwy
  dla budżetu bety; limit aplikacji nie zastępuje limitu na koncie dostawcy,
- wykonano próbny backup i odtworzono go do osobnej bazy testowej.

## Pierwsza instalacja monitoringu i backupu

Pliki systemd zawierają ścieżkę repozytorium
`/home/ubuntu/Projekty/aplikacje/RajkoChess`. Jeżeli serwer używa innej ścieżki,
należy ją poprawić przed skopiowaniem jednostek.

```bash
sudo cp deploy/systemd/rajko-chess-{backup,health}.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rajko-chess-backup.timer rajko-chess-health.timer
sudo systemctl start rajko-chess-backup.service rajko-chess-health.service
sudo systemctl status rajko-chess-backup.timer rajko-chess-health.timer
sudo journalctl -u rajko-chess-backup.service -u rajko-chess-health.service --since today
```

Backup jest tworzony codziennie w `/var/backups/rajko-chess`, ma prawa dostępne
wyłącznie administratorowi, sumę SHA-256 i domyślnie 14 dni retencji. Każde
wdrożenie uruchamia dodatkowy backup przed migracją Alembic. Redis przechowuje
wyłącznie krótkotrwałe limity i blokady, więc nie jest backupowany.

Kopia na tym samym serwerze nie chroni przed awarią dysku. Raz dziennie należy
replikować katalog backupu do szyfrowanego magazynu poza serwerem, z osobnymi
danymi dostępowymi i retencją. Dane testerów nie powinny trafiać do prywatnych,
niezarządzanych usług synchronizacji.

## Wdrożenie

```bash
cd /home/ubuntu/Projekty/aplikacje/RajkoChess
deploy/deploy.sh
```

Skrypt należy uruchamiać jako użytkownik repozytorium, nie jako root. Ładuje on
konfigurację z chronionego `/etc/rajko-chess/backend.env` przez `sudo`; nie
tworzymy drugiej kopii produkcyjnych sekretów w `backend/.env`. Pełna procedura
pierwszej instalacji, TLS, PostgreSQL, nginx i systemd znajduje się w
`DEPLOYMENT_CODEX.md`.

Skrypt przerywa pracę przy niezapisanych zmianach, nieudanych testach,
niedostępnej bazie lub Redisie, błędnej konfiguracji nginx, nieudanym backupie,
migracji albo healthchecku. Po wdrożeniu należy ręcznie sprawdzić:

1. rejestrację, odbiór wiadomości weryfikacyjnej i logowanie kontem testowym;
   jeśli Google OAuth jest włączone, także utworzenie nowego konta Google oraz
   jawne podłączenie Google do istniejącego konta hasłowego,
2. import PGN i FEN, pełną analizę, znacznik analizy, odtworzenie rozmowy po
   odświeżeniu oraz ponowne otwarcie partii z historii,
3. zapis domyślnego loginu Chess.com w ustawieniach konta i jego automatyczne
   wypełnienie w formularzu importu,
4. limit Free oraz podgląd użycia, bez przyznawania Premium kontu testowemu,
5. grę z botem i przejście zakończonej partii do analizy,
6. panel administratora i wpis audytowy po kontrolnej operacji,
7. brak sekretów oraz danych osobowych w logach aplikacji i nginx.

## Kontrola codzienna i alarmy

Cykliczna jednostka sprawdza co pięć minut `/api/health`, który zwraca `200`
tylko wtedy, gdy odpowiadają PostgreSQL i Redis. Wynik jest dostępny w journald:

```bash
systemctl list-timers 'rajko-chess-*'
journalctl -u rajko-chess-health.service --since today
journalctl -u rajko-chess-backend.service --since today
```

Sam wpis w journald nie wysyła powiadomienia. Przed zaproszeniem testerów trzeba
podłączyć zewnętrzny monitoring HTTPS do publicznego `/chess/api/health` i alarm
e-mail/SMS po dwóch kolejnych błędach. Monitor powinien sprawdzać również
ważność certyfikatu TLS. Nie należy umieszczać w nim danych logowania testera.

Codziennie sprawdzamy ostatni udany backup i wolne miejsce:

```bash
systemctl status rajko-chess-backup.service
sudo find /var/backups/rajko-chess -maxdepth 1 -type f -name '*.dump' -printf '%TY-%Tm-%Td %TH:%TM %s %p\n'
df -h /var/backups/rajko-chess
```

## Próba odtworzenia

Odtworzenia nie wykonujemy nad działającą bazą. Najpierw tworzymy osobną, pustą
bazę testową i weryfikujemy sumę oraz katalog archiwum:

```bash
sudo -u postgres createdb rajko_chess_restore_test
sudo sha256sum --check /var/backups/rajko-chess/rajko-chess-YYYYMMDDTHHMMSSZ.dump.sha256
sudo -u postgres pg_restore --list /var/backups/rajko-chess/rajko-chess-YYYYMMDDTHHMMSSZ.dump
sudo -u postgres pg_restore --exit-on-error --no-owner --no-privileges \
  --dbname rajko_chess_restore_test \
  /var/backups/rajko-chess/rajko-chess-YYYYMMDDTHHMMSSZ.dump
```

Następnie uruchamiamy `alembic current`, diagnostykę bazy i kontrolujemy liczbę
rekordów w kluczowych tabelach. Bazę testową usuwamy dopiero po zapisaniu wyniku
próby. Pierwszą próbę wykonujemy przed betą, kolejne co najmniej raz w miesiącu
i po zmianie mechanizmu backupu.

## Incydent

1. Wstrzymaj nowe zaproszenia; przy ryzyku utraty lub ujawnienia danych wyłącz
   dostęp do aplikacji w nginx, zachowując serwer i logi do analizy.
2. Zapisz czas, objawy, ostatni poprawny healthcheck, wdrożony commit i osoby
   mające dostęp. Nie wklejaj sekretów ani pełnych danych użytkowników do issue.
3. Zabezpiecz logi i ostatni backup. Nie wykonuj migracji ani naprawy bez kopii.
4. Ustal zakres: dostępność, utrata danych, ujawnienie danych lub niekontrolowane
   koszty OpenRouter/Stockfisha.
5. Po naprawie wykonaj pełną checklistę wdrożeniową i opisz działania
   zapobiegawcze. Jeżeli incydent dotyczy danych osobowych, właściciel produktu
   powinien ocenić obowiązki prawne z kompetentnym doradcą.
