# Event-related Trade Explorer

The daily page: today's news-based event studies (a scrolling ticker and one card per story), search over the
archive of past studies, and a box to commission a new study by email. History only, not investment advice.
Hosted like Blackbird (`sharadar/search_site`): it reads only `data/` in this folder, with no market data or tester.

| file | what it does |
|---|---|
| `app.py` | The page (dark theme in `.streamlit/config.toml`). |
| `export.py` | Run locally after the morning study: writes `data/today.json` and `data/archive.json.gz`. |
| `data/` | What the host reads. |
| `requirements.txt` | What the host installs. |

The morning run (`sharadar/playbook/daily_run.sh`): Sharadar price top-up, S&P 500 membership, extra market series,
the library scan, the news call (Claude with web search, capped at $3 a day), the free event studies, then `export.py`.

Host secrets (`.streamlit/secrets.toml`): `password` (no password means no gate) and `request_email` (without it the
request button says coming soon).
