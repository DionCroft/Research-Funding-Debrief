# Research Funding Debrief

Research Funding Debrief is a public GitHub Pages funding radar backed by a local Python refresh script. It checks research funding sources, stores opportunities in SQLite, scores and categorises them, publishes static JSON/RSS snapshots for the website and Power Automate, and can send compact Discord debriefs.

The current version checks UKRI, Innovate UK, GOV.UK Find a Grant, NIHR, Wellcome, Royal Society, and Royal Academy of Engineering sources by default. Microsoft Forms captures signup and unsubscribe requests, Microsoft Lists stores subscriber preferences, and Power Automate sends onboarding, test, and future briefing emails.

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
- refresh `web/data/live-updates.json` and `web/data/live-updates.xml` when requested
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

## Scheduled refresh, RSS, and Discord alerts

Use the included cron wrapper to refresh the website data files and send the Discord debrief from one fetch cycle:

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
- refreshes `web/data/live-updates.xml`
- sends the compact Discord debrief when Discord is configured
- writes normal app logs to `logs/research_funding_debrief.log`

The published GitHub Pages data endpoints are:

```text
https://dioncroft.github.io/Research-Funding-Debrief/data/live-updates.json
https://dioncroft.github.io/Research-Funding-Debrief/data/live-updates.xml
```

The website uses the JSON file. Power Automate can use the RSS file with the standard RSS connector, which avoids the Premium licence requirement for the generic HTTP action.

Funding call status labels are generated during the refresh:

- `New`: first seen in the local opportunity database within the last 7 days
- `Seen`: first seen more than 7 days ago
- `Closing soon`: deadline is within the configured 30-day window
- `Ongoing`: source status includes open or upcoming

## Signup front page

The project includes a static front page for the public funding radar. For local backend testing,
`web/server.py` can still run a SQLite-backed signup endpoint:

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

Submissions to the local server are stored in `data/signup_subscribers.db`. The production GitHub
Pages site uses Microsoft Forms instead of this local SQLite signup flow.

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

GitHub Pages is static, so it cannot run `web/server.py` or write to SQLite. The public site embeds
or links to the Microsoft Forms signup flow, and the local SQLite signup flow remains available only
when running `python web/server.py`.

The deployment workflow runs `python web/live_updates.py` before publishing, which writes
`web/data/live-updates.json` for the live funding radar and `web/data/live-updates.xml` for
Power Automate/RSS-based briefing flows.

If you later deploy a hosted signup API, set this before `web/app.js` loads:

```html
<script>
  window.RESEARCH_FUNDING_SIGNUP_API = "https://example.com/api/signup";
</script>
```

### Microsoft Forms and Lists backend

The production signup backend uses Microsoft Forms, Microsoft Lists, and Power Automate.

Current forms:

- Signup: `https://forms.cloud.microsoft/e/6HiR44VDU7`
- Unsubscribe: `https://forms.cloud.microsoft/e/tv8P5mEVAH`

Recommended signup flow:

1. Microsoft Forms trigger: `When a new response is submitted`.
2. Microsoft Forms action: `Get response details`.
3. SharePoint/Microsoft Lists action: create an item in `Research Funding Debrief Signups`.
4. Store first name, last name, email, frequency, topics, funders, opportunity types, relevance level, notes, consent, created timestamp, and `Active`.
5. Send an onboarding email with a website button and the unsubscribe form link.

Recommended unsubscribe flow:

1. Microsoft Forms trigger on the unsubscribe form.
2. Get response details.
3. Get matching Microsoft List items by email.
4. Mark matching active subscribers inactive or delete already inactive entries.
5. Send an unsubscribe confirmation email.

Recommended daily/weekly briefing source:

1. Recurrence trigger for daily or weekly delivery.
2. RSS action: list feed items from `https://dioncroft.github.io/Research-Funding-Debrief/data/live-updates.xml`.
3. SharePoint/Microsoft Lists action: get active subscribers with `Active eq 1`.
4. Filter subscribers by `Frequency`.
5. For each subscriber, filter RSS items using their Topics, Funders, OpportunityTypes, and RelevanceLevel preferences.
6. Send an email only when matching items exist.

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

Opportunities are assigned categories that match the Microsoft Forms topic choices, including:

- AI / Data
- Machine Learning
- Robotics / Automation
- Electronics / IoT
- Embedded Systems
- Sensors / Instrumentation
- Cybersecurity
- Wireless / Telecoms
- Digital Health
- Assistive Technology / SEND
- Clinical Evidence / Trials
- Public Health
- Social Care
- Mental Health
- Education / Skills
- Policy / Social Sciences
- Energy / Sustainability
- Climate / Environment
- Manufacturing / Industry 4.0
- Space / Aerospace
- Defence / Security
- Creative / Media Tech
- KTP / Collaboration
- Fellowships
- Early Career
- Capital / Infrastructure
- International / Horizon Europe
- Commercialisation / Translation

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
