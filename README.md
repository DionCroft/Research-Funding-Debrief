# Research Funding Debrief

Research Funding Debrief is a local command-line Python project that checks research funding sources, stores opportunities in SQLite, scores them for relevance, and prints a daily email-style debrief in the terminal.

The current local version checks UKRI, Innovate UK, and GOV.UK Find a Grant by default. The code is structured so additional sources such as EU Funding & Tenders, charity funders, university pages, or permitted Research Professional feeds can be added later.

## Install

```bash
cd research-funding-debrief
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

On macOS or Linux, activate the virtual environment with:

```bash
source .venv/bin/activate
```

## Run locally

```bash
python run.py
```

The run will:

- load configuration from defaults, environment variables, and optional `.env`
- create `data/research_funding_debrief.db` if it does not exist
- fetch configured funding sources
- parse opportunities into a standard model
- score them using configured keywords
- categorise them into useful themes
- create a deterministic bid-fit summary for each opportunity
- insert new opportunities and update `last_seen_at` for known ones
- flag changed opportunities when important details change
- print a Daily Research Funding Debrief in the terminal
- log activity to `logs/research_funding_debrief.log`

Useful CLI options:

```bash
python run.py --sources ukri
python run.py --sources ukri,innovate_uk
python run.py --min-score 5
python run.py --new-only
python run.py --send-discord
python run.py --no-discord
python run.py --dry-run
```

## Configuration

Copy `.env.example` to `.env` if you want local overrides:

```bash
copy .env.example .env
```

The default relevance keywords live in `app/config.py`. You can edit `DEFAULT_KEYWORDS` directly, or set `RELEVANCE_KEYWORDS` in `.env` as a comma-separated list to replace the defaults.

Configured sources are controlled by `ENABLED_SOURCES`:

```env
ENABLED_SOURCES=ukri,innovate_uk,find_a_grant
```

Available source keys:

- `ukri`
- `innovate_uk`
- `find_a_grant`

Scoring currently uses:

- +3 for a keyword match in the title
- +1 for a keyword match in the summary
- +2 for open or upcoming opportunities
- +2 for university, academic, research organisation, or collaboration language
- +1 when a funding amount is detected

Opportunities are also assigned categories such as:

- AI / Data
- Electronics / Sensors / Embedded
- Robotics / Automation
- Digital Health / Assistive Tech / SEND
- Energy / Sustainability
- Cybersecurity
- KTP / University-Business Collaboration
- Fellowships / Academic Career
- Capital / Infrastructure
- General / Low Match

## Database deduplication

SQLite stores opportunities in the `opportunities` table. Each opportunity is unique by `(source, external_id)`.

When a new opportunity appears, it is inserted with `first_seen_at` and `last_seen_at`. When the same source and external ID appear again, the record is updated, `last_seen_at` changes, and the opportunity is treated as previously seen so it is not repeatedly re-alerted as new.

The database also stores a content hash for important fields. If status, amount, opening date, closing date, type, eligibility, title, or URL changes on a future run, the opportunity is reported as changed.

## Email and Discord

Email and Discord are scaffolded but disabled by default.

The placeholder functions are:

- `send_email_report(subject: str, body: str)`
- `send_discord_report(body: str)`

They read these environment variables:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `EMAIL_FROM`
- `EMAIL_TO`
- `DISCORD_WEBHOOK_URL`
- `DISCORD_BOT_TOKEN`
- `DISCORD_CHANNEL_ID`
- `ENABLE_EMAIL`
- `ENABLE_DISCORD`

Nothing is sent unless `ENABLE_EMAIL=true` or `ENABLE_DISCORD=true`. If credentials are missing, the app logs a warning and skips sending.

Discord supports two delivery methods:

- Webhook: set `ENABLE_DISCORD=true` and `DISCORD_WEBHOOK_URL`
- Bot token: set `ENABLE_DISCORD=true`, `DISCORD_BOT_TOKEN`, and `DISCORD_CHANNEL_ID`

Bot tokens should only live in `.env` or another secret store. Do not commit them.

Discord receives a compact report by default: summary counts plus relevant new or changed opportunities. It does not dump the full previously seen list unless `DISCORD_INCLUDE_KNOWN=true`.

## Tests

```bash
pytest
```

The initial tests cover keyword scoring, model creation, and database duplicate detection.

## Future deployment

After local testing, this can be run on a Raspberry Pi, mini PC, or server using cron. A simple daily cron entry might look like:

```cron
0 7 * * * cd /path/to/research-funding-debrief && /path/to/venv/bin/python run.py
```

Future versions can add more source modules under `app/sources/`, plus SMTP email delivery and Discord webhook summaries.
