# Codex Mac Studio Runner

This repository now has two Codex-on-Mac-Studio layers:

- a generic `codex exec` background runner
- a dedicated lazy-detail queue worker for on-demand detailed briefings

Batch English title/summary enrichment happens inside `scripts/fetch_and_send.py` through local Codex CLI. The detail page endpoint only enqueues a job; the Mac Studio worker actually generates the detailed briefing and stores it in Redis.

## Files

- `scripts/run_codex_task.sh`: single scheduled Codex run
- `ops/codex/codex-runner.env.example`: local config template
- `ops/codex/prompt.md`: task prompt used by scheduled runs
- `ops/launchd/io.tabber.itnewsletter.codex-loop.plist`: LaunchAgent template
- `scripts/process_lazy_detail_queue.mjs`: Redis-backed lazy detail worker
- `scripts/run_lazy_detail_queue_worker.sh`: launchd wrapper for the lazy detail worker
- `scripts/run_local_dispatch.sh`: launchd wrapper for local Discord dispatch with Codex list summaries
- `ops/codex/lazy-detail-worker.env.example`: lazy detail worker env template
- `ops/codex/local-dispatch.env.example`: local dispatch env template
- `ops/launchd/io.tabber.itnewsletter.lazy-detail-queue-worker.plist`: LaunchAgent for the lazy detail worker
- `ops/launchd/io.tabber.itnewsletter.local-dispatch.plist`: LaunchAgent for local dispatch

## 1. One-time setup

1. Make sure the Codex CLI is installed and authenticated:

   ```bash
   codex login
   ```

2. Copy the local config template:

   ```bash
   cp ops/codex/codex-runner.env.example ops/codex/codex-runner.env
   ```

3. Review and edit:
   - `ops/codex/codex-runner.env`
   - `ops/codex/prompt.md`

4. Make the runner executable:

   ```bash
   chmod +x scripts/run_codex_task.sh
   chmod +x scripts/run_lazy_detail_queue_worker.sh
   chmod +x scripts/run_local_dispatch.sh
   ```

5. Copy the lazy detail worker env:

   ```bash
   cp ops/codex/lazy-detail-worker.env.example ops/codex/lazy-detail-worker.env
   ```

6. Fill Redis and archive settings in `ops/codex/lazy-detail-worker.env`.

7. If you want English title/summary enrichment to happen locally on the Mac Studio, also copy:

   ```bash
   cp ops/codex/local-dispatch.env.example ops/codex/local-dispatch.env
   ```

8. Fill the Python interpreter path, Discord webhook, and Codex summary settings in `ops/codex/local-dispatch.env`.

## 2. Local smoke check

Validate the shell script and plist before loading the service:

```bash
zsh -n scripts/run_codex_task.sh
zsh -n scripts/run_lazy_detail_queue_worker.sh
zsh -n scripts/run_local_dispatch.sh
plutil -lint ops/launchd/io.tabber.itnewsletter.codex-loop.plist
plutil -lint ops/launchd/io.tabber.itnewsletter.lazy-detail-queue-worker.plist
plutil -lint ops/launchd/io.tabber.itnewsletter.local-dispatch.plist
```

If you want a manual run before `launchd`:

```bash
scripts/run_codex_task.sh
```

Note: this will only work after `codex login`, and it will use your configured Codex plan limits.

## 3. Install the LaunchAgent

Create the repo-local log directory first:

```bash
mkdir -p logs/codex
```

Copy the plist into your user LaunchAgents directory:

```bash
cp ops/launchd/io.tabber.itnewsletter.codex-loop.plist ~/Library/LaunchAgents/
```

Load or reload it:

```bash
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/io.tabber.itnewsletter.codex-loop.plist 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/io.tabber.itnewsletter.codex-loop.plist
launchctl enable "gui/$(id -u)/io.tabber.itnewsletter.codex-loop"
launchctl kickstart -k "gui/$(id -u)/io.tabber.itnewsletter.codex-loop"
```

The default schedule is every `1800` seconds (30 minutes). Edit `StartInterval` in the plist if you want a different cadence.

For the lazy detail worker:

```bash
cp ops/launchd/io.tabber.itnewsletter.lazy-detail-queue-worker.plist ~/Library/LaunchAgents/
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/io.tabber.itnewsletter.lazy-detail-queue-worker.plist 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/io.tabber.itnewsletter.lazy-detail-queue-worker.plist
launchctl enable "gui/$(id -u)/io.tabber.itnewsletter.lazy-detail-queue-worker"
launchctl kickstart -k "gui/$(id -u)/io.tabber.itnewsletter.lazy-detail-queue-worker"
```

The lazy detail worker runs every `60` seconds by default.

For local dispatch every 4 hours:

```bash
cp ops/launchd/io.tabber.itnewsletter.local-dispatch.plist ~/Library/LaunchAgents/
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/io.tabber.itnewsletter.local-dispatch.plist 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/io.tabber.itnewsletter.local-dispatch.plist
launchctl enable "gui/$(id -u)/io.tabber.itnewsletter.local-dispatch"
launchctl kickstart -k "gui/$(id -u)/io.tabber.itnewsletter.local-dispatch"
```

Do not keep `.github/workflows/news-discord.yml` on an automatic schedule at the same time. The GitHub runner and the Mac Studio runner do not share `data/state.json` unless you build an explicit sync path, so duplicate Discord sends can appear minutes or hours apart.

## 4. Logs and outputs

`launchd` appends service logs here:

- `logs/codex/launchd.stdout.log`
- `logs/codex/launchd.stderr.log`
- `logs/codex/lazy-detail-worker.stdout.log`
- `logs/codex/lazy-detail-worker.stderr.log`
- `logs/codex/local-dispatch.stdout.log`
- `logs/codex/local-dispatch.stderr.log`

Each successful scheduled run can also write a final response snapshot here:

- `logs/codex/last-message-YYYYMMDD-HHMMSS.md`

Useful commands:

```bash
tail -f logs/codex/launchd.stdout.log
tail -f logs/codex/launchd.stderr.log
ls -1 logs/codex/last-message-*.md | tail
```

## 5. Pause or stop the loop

To pause future runs without unloading the service:

```bash
touch ops/codex/STOP
```

To resume:

```bash
rm -f ops/codex/STOP
launchctl kickstart -k "gui/$(id -u)/io.tabber.itnewsletter.codex-loop"
```

To fully unload:

```bash
launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/io.tabber.itnewsletter.codex-loop.plist
```

## 6. Useful config switches

- `CODEX_SANDBOX="read-only"`: review-only loop
- `CODEX_SANDBOX="workspace-write"`: allow local edits inside this repo
- `CODEX_MODEL="..."`: override the default Codex model
- `CODEX_EXTRA_ARGS="--profile default"`: append more CLI flags
- `CODEX_JSON="1"`: write JSONL exec events into stdout logs
- `CODEX_DETAIL_MODEL="..."`: override the model used by the lazy detail worker
- `LAZY_DETAIL_QUEUE_BATCH_SIZE="2"`: number of queued detail jobs to process per launchd tick
- `NEWSLETTER_PYTHON_BIN="..."`: Python interpreter used by the local dispatch launcher
- `NEWSLETTER_BUILD_ARCHIVE="1"`: rebuild `dist/` after each local dispatch

## 7. Operational notes

- `launchd` is doing the loop. The shell runner intentionally executes only one task per invocation.
- `scripts/run_local_dispatch.sh` now takes a repo-local lock under `tmp/codex/local-dispatch.lock`, so a manual `kickstart` cannot overlap an already running send job.
- A lock directory under `tmp/codex` prevents overlapping runs.
- `fetch_and_send.py` only uses local Codex for English title/summary enrichment when it runs on the Mac Studio. GitHub Actions cannot reuse your local Codex login.
- The detail page Vercel function no longer generates the briefing itself. It only checks cache and enqueues the job.
- This setup does not bypass Codex usage limits. It just avoids calling your own separate OpenAI API integration for the agent loop itself.
- If you move this repository, update the absolute paths in:
  - `ops/codex/codex-runner.env`
  - `ops/launchd/io.tabber.itnewsletter.codex-loop.plist`
  - `ops/codex/lazy-detail-worker.env`
  - `ops/launchd/io.tabber.itnewsletter.lazy-detail-queue-worker.plist`
  - `ops/codex/local-dispatch.env`
  - `ops/launchd/io.tabber.itnewsletter.local-dispatch.plist`
