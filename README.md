# Research Funding Debrief

Research Funding Debrief is a local command-line Python project that checks research funding sources, stores opportunities in SQLite, scores them for relevance, and prints a daily email-style debrief in the terminal.

The current local version checks UKRI, Innovate UK, GOV.UK Find a Grant, NIHR, Wellcome, Royal Society, and Royal Academy of Engineering sources by default. The code is structured so additional sources such as EU Funding & Tenders, charity funders, university pages, or permitted Research Professional feeds can be added later.

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
python run.py --refresh-live-json --send-discord
python run.py --no-discord
python run.py --dry-run
```

## Scheduled refresh and Discord alerts

Use the included cron wrapper to refresh the website JSON and send the Discord debrief from one
fetch cycle:

```bash
scripts/run_scheduled_debrief.sh
```

Before scheduling it, make sure `.env` has Discord enabled, using either a webhook or bot token:

```env
ENABLE_DISCORD=true
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

Then edit the crontab:

```bash
crontab -e
```

Add these lines to run the job at 09:00 and 21:00 every day:

```cron
0 9 * * * /home/cadmus/Projects/Debrief/research-funding-debrief/scripts/run_scheduled_debrief.sh >> /home/cadmus/Projects/Debrief/research-funding-debrief/logs/cron.log 2>&1
0 21 * * * /home/cadmus/Projects/Debrief/research-funding-debrief/scripts/run_scheduled_debrief.sh >> /home/cadmus/Projects/Debrief/research-funding-debrief/logs/cron.log 2>&1
```

The scheduled job:

- fetches the configured funding sources
- updates `data/research_funding_debrief.db`
- refreshes `web/data/live-updates.json`
- sends the compact Discord debrief when Discord is configured
- writes normal app logs to `logs/research_funding_debrief.log`

## Signup front page

The project includes a static front page with a local signup endpoint for daily or weekly funding
briefing preferences:

```bash
python web/server.py
```

If port `8080` is already in use, choose another port:

```bash
python web/server.py --port 8081
```

Then open:

```text
http://127.0.0.1:8080
```

Submissions are stored in `data/signup_subscribers.db`. If the HTML file is opened directly without
the local server, the form falls back to an email signup draft.

### Run the signup server 24/7 on a Raspberry Pi

For a Raspberry Pi, install the signup page as a user-level `systemd` service:

```bash
python scripts/install_signup_service.py
```

By default this binds to all network interfaces on port `8080`, so another device on the same
network can open:

```text
http://<raspberry-pi-ip-address>:8080
```

Use a different port if needed:

```bash
python scripts/install_signup_service.py --port 8081
```

Useful service commands:

```bash
systemctl --user status research-funding-signup.service
systemctl --user restart research-funding-signup.service
journalctl --user -u research-funding-signup.service -f
```

If the Pi is rebooted, the service will start again automatically. The installer also attempts to
enable lingering for the current user so the service can run even when you are not logged in.

## GitHub Pages

The signup page can be published as a static GitHub Pages site using the included workflow:

```text
.github/workflows/deploy-pages.yml
```

To enable it:

1. Push the repository to GitHub.
2. In the repository, go to Settings > Pages.
3. Set Build and deployment > Source to GitHub Actions.
4. Push to the `main` branch, or run the `Deploy signup page` workflow manually.

The public URL is:

```text
https://dioncroft.github.io/Research-Funding-Debrief/
```

GitHub Pages is static, so it cannot run `web/server.py` or write to SQLite. On GitHub Pages the
signup form opens a prefilled email to `d.mariyanayagam@londonmet.ac.uk`. The local SQLite signup
flow still works when running `python web/server.py`.

The deployment workflow runs `python web/live_updates.py` before publishing, which writes
`web/data/live-updates.json` for the live funding radar on the front page.

If you later deploy a hosted signup API, set this before `web/app.js` loads:

```html
<script>
  window.RESEARCH_FUNDING_SIGNUP_API = "https://example.com/api/signup";
</script>
```

### Microsoft Forms signup backend option

For a public GitHub Pages version, Microsoft Forms is a low-maintenance way to capture newsletter
preferences without running a custom public backend.

Recommended flow:

1. Create a Microsoft Form with first name, last name, email, frequency, and topic checkboxes.
2. Set the form to allow responses from the intended audience.
3. Embed the form in the GitHub Pages site or link to it from the signup button.
4. Create a Power Automate flow using the Microsoft Forms trigger `When a new response is submitted`.
5. Add the Microsoft Forms action `Get response details`.
6. Save each response to an Excel workbook or SharePoint List.
7. Optionally add a final step that posts the response to the Raspberry Pi signup API if the Pi is
   reachable from the internet.

This keeps the user-facing signup simple while giving an automated, structured backend. The local
SQLite database remains useful for the Raspberry Pi service; Microsoft Forms or SharePoint can act
as the public collection point.

## Configuration

Copy `.env.example` to `.env` if you want local overrides:

```bash
copy .env.example .env
```

The default relevance keywords live in `app/config.py`. You can edit `DEFAULT_KEYWORDS` directly, or set `RELEVANCE_KEYWORDS` in `.env` as a comma-separated list to replace the defaults.

Configured sources are controlled by `ENABLED_SOURCES`:

```env
ENABLED_SOURCES=ukri,innovate_uk,find_a_grant,nihr,wellcome,royal_society,raeng
```

Available source keys:

- `ukri`
- `innovate_uk`
- `find_a_grant`
- `nihr`
- `wellcome`
- `royal_society`
- `raeng`

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
