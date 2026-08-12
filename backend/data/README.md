# Opening data

`openings.json` is generated from the public-domain
[`lichess-org/chess-openings`](https://github.com/lichess-org/chess-openings)
dataset (CC0) with `backend/scripts/update_openings.py`.

Legacy SQLite bot databases in this directory are ignored by Git. Bot profiles
are now stored in PostgreSQL; `python -m scripts.migrate_bots_to_postgres`
imports a legacy catalog idempotently as public system bots.
