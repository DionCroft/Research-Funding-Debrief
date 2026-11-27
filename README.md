# Research Funding Debrief

A UK research funding radar and briefing for academics, researchers, and innovation teams. Browse current calls and deadlines, filter by your interests, or subscribe to a daily or weekly briefing.

[Open the funding radar](https://dioncroft.github.io/Research-Funding-Debrief/) · [Subscribe](https://forms.cloud.microsoft/e/6HiR44VDU7) · [Unsubscribe](https://forms.cloud.microsoft/e/tv8P5mEVAH)

## Coverage and freshness

The project supports seven sources. The radar’s **Source health** panel shows which sources are enabled, the outcome of each check, when each source was last verified, and how many calls are shown.

| Source | Configuration key |
| --- | --- |
| UK Research and Innovation (UKRI) | `ukri` |
| Innovate UK | `innovate_uk` |
| GOV.UK Find a Grant | `find_a_grant` |
| National Institute for Health and Care Research (NIHR) | `nihr` |
| Wellcome | `wellcome` |
| Royal Society | `royal_society` |
| Royal Academy of Engineering | `raeng` |

A failed check or a listing that returns zero records keeps that source’s last verified calls where available. The radar labels retained records and removes them once a known deadline has passed. A successful check replaces the retained records for that source. If no source can be verified and there is no previous snapshot, the refresh fails. The site flags snapshots more than 26 hours old.

Check the official funder listing for eligibility and deadline changes before applying.

## Run locally

Requires Python 3.10 or newer and Git. From the repository root, create a virtual environment and install the dependencies.

```bash
python -m venv .venv
```

Activate it with `.venv\Scripts\Activate.ps1` in PowerShell or `source .venv/bin/activate` on macOS or Linux.

```bash
python -m pip install -r requirements.txt
python run.py --dry-run
python -m pytest
```

| Task | Command |
| --- | --- |
| Preview one source without updating SQLite or sending notifications | `python run.py --sources ukri --dry-run` |
| Run a debrief and hide previously seen calls | `python run.py --new-only` |
| Change the reporting score threshold for one run | `python run.py --min-score 5` |
| Regenerate the local radar and RSS files | `python run.py --refresh-live-json --no-discord` |
| Preview the website locally | `python web/server.py`, then open `http://127.0.0.1:8080` |

Copy [`.env.example`](.env.example) to `.env` to override settings. Keep credentials in `.env` or your host’s environment.

| Setting | Purpose |
| --- | --- |
| `ENABLED_SOURCES` | Comma-separated source keys. Defaults to all seven. |
| `RELEVANCE_KEYWORDS`, `RELEVANT_SCORE_THRESHOLD` | Override the default keywords and adjust the daily report’s relevance threshold. |
| `DATABASE_PATH`, `LOG_PATH` | Override the SQLite database and rotating application log paths. |
| `ENABLE_DISCORD`, `DISCORD_WEBHOOK_URL` | Enable regular Discord reports through a webhook. A bot token and channel ID are also supported. |
| `ENABLE_EMAIL`, `SMTP_*`, `EMAIL_FROM`, `EMAIL_TO` | Optional SMTP delivery for the terminal debrief. Public briefings use Microsoft Power Automate. |

## Publish and monitor

The refresh host checks the funders, records first-seen and changed calls in SQLite, and generates two static feeds. GitHub Pages publishes those files from `main`. Keep the SQLite database and the previous JSON snapshot available between runs so the radar can preserve history and recover from source failures.

- [JSON snapshot](https://dioncroft.github.io/Research-Funding-Debrief/data/live-updates.json) powers the public radar and includes source health.
- [RSS feed](https://dioncroft.github.io/Research-Funding-Debrief/data/live-updates.xml) contains all tracked calls and can feed Power Automate through its standard RSS connector.
- [Pages workflow](.github/workflows/deploy-pages.yml) deploys when `main` changes. In GitHub’s Pages settings, select **GitHub Actions** as the deployment source.

Run [`scripts/run_scheduled_debrief.sh`](scripts/run_scheduled_debrief.sh) from a persistent Linux host with Bash, `flock`, the repository’s `.venv`, and a Git credential that can push to `main`. For a twice-daily refresh, use a crontab entry like this and replace the example path.

```cron
0 9,21 * * * bash /path/to/research-funding-debrief/scripts/run_scheduled_debrief.sh >> /path/to/research-funding-debrief/logs/cron.log 2>&1
```

The job commits the generated feeds, pushes them, and waits up to 10 minutes for Pages to serve both files. Failures during sync, generation, commit, push, or public verification exit with an error and send an alert to the same Discord destination used for scheduled debriefs. Configure `DISCORD_WEBHOOK_URL` or both `DISCORD_BOT_TOKEN` and `DISCORD_CHANNEL_ID` on the refresh host.

Start with `logs/cron.log` and `logs/research_funding_debrief.log` when an alert arrives. If the push succeeded, check the [Pages deployment runs](https://github.com/DionCroft/Research-Funding-Debrief/actions/workflows/deploy-pages.yml). An alert delivery failure is recorded in the job output.

## Briefings and subscriptions

The public site uses **Microsoft Forms** for signup and unsubscribe, **Microsoft Lists** for subscription preferences, and **Power Automate** for email delivery.

1. On signup, read the Form response and store the subscriber’s email, frequency, topics, preferred sources, opportunity types, relevance preference, consent, and active status. Send an onboarding email with the unsubscribe link.
2. On a daily or weekly recurrence, retrieve the RSS items and active subscribers for that frequency. Apply each subscriber’s preferences and send when matching items exist.
3. On unsubscribe, match the submitted email to the subscriber record, mark it inactive, and send a confirmation.

RSS item dates use the original publication date when supplied by the funder and fall back to the first-seen timestamp. Each item also exposes the first-seen date for briefing rules.

For local signup testing, `web/server.py` provides a SQLite-backed endpoint. It supports `--port 8081` if the default port is busy. On a Raspberry Pi, `python scripts/install_signup_service.py` installs the server as a user-level systemd service.

## Project structure

| Path | Purpose |
| --- | --- |
| [`app/`](app/) | Collector, relevance scoring, SQLite history, and notifications |
| [`app/sources/`](app/sources/) | Funder adapters and source checks |
| [`web/`](web/) | Static radar, JSON and RSS generation, and local signup server |
| [`scripts/`](scripts/) | Scheduled publication, verification, and local service setup |
| [`tests/`](tests/) | Parser, snapshot, reporting, and delivery tests |
