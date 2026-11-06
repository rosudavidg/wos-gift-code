[![Crawl WoS gift codes](https://github.com/rosudavidg/wos-gift-code/actions/workflows/crawler.yml/badge.svg)](https://github.com/rosudavidg/wos-gift-code/actions/workflows/crawler.yml)

# wos-gift-code

The crawler reads the Known Gift Codes section of wostools.net and submits each successful, nonempty observation to the State 3022 admin API. Firestore is the source of truth; the crawler logs to stdout and does not create a pull request. A missing section or empty result fails the run without changing active codes.

## Deploy and migrate

1. If migrating an existing installation, pause the old workflow and obtain a backup of its latest `known_gift_codes.json`; the legacy file is no longer included in this repository. Deploy the updated `state-3022-admin` server with Firestore configured.
2. Generate a dedicated random key with `openssl rand -hex 32`. Set `GIFT_CODE_API_KEY` on the admin server and redeploy/restart it. Keep this key private and separate from `AUTH_SECRET`.
3. From this repository, set the server base URL and key in your local shell. Use the actual HTTPS URL without `/gift-codes` at the end. HTTP is allowed only for localhost. For example, in zsh:

   ```sh
   export GIFT_CODE_API_URL="https://your-admin-server.example"
   read -s "GIFT_CODE_API_KEY?Gift code API key: "
   export GIFT_CODE_API_KEY
   python3 migrate_gift_codes.py known_gift_codes.json
   unset GIFT_CODE_API_KEY
   ```

   Migration creates the Firestore state only if it does not exist. HTTP 409 means it was already initialized; it will never overwrite it. The legacy file records all previously seen codes, not which ones are active or when they were discovered. Their active status and discovery dates are therefore unknown until a crawl; the old last-status timestamp is preserved. The first successful crawl sets activity without announcing migrated codes as new.
4. In the **wos-gift-code** GitHub repository, open **Settings > Secrets and variables > Actions**. Add the repository variable `GIFT_CODE_API_URL` with the admin server's HTTPS base URL. Add the repository secret `GIFT_CODE_API_KEY` with the same key configured on the server. Keep or add `DISCORD_WEBHOOK_URL` as a secret for notifications.
5. Deploy the crawler changes, run **Actions > Crawl WoS gift codes > Run workflow**, and check the run logs and `GET /gift-codes` on the admin server. The workflow currently has only a manual trigger; add a GitHub Actions `schedule` if automatic checks are desired.

## Data and notifications

The public `GET /gift-codes` returns `activeCodes`, `latestNewCodes`, `lastNewCodeAt`, and `lastCheckedAt`. A code is active only if it appeared in the latest successful observation. `latestNewCodes` is the latest nonempty discovery batch and is retained across checks with no new codes; `lastNewCodeAt` is its UTC timestamp. Migrated discovery times remain null because they cannot be recovered from the JSON. Previously seen codes that reappear are not announced again.

The protected crawler endpoints track `pendingNewCodes` and `lastStatusSentAt`. New codes are sent to Discord immediately, and a no-new-codes status is sent at most once per 24 hours since the most recent discovery or status message. A missing or failing webhook leaves new-code alerts pending for a later run. Notifications are acknowledged only after Discord accepts them; if the acknowledgment fails after Discord accepts a message, the next run may send it again. Concurrent external crawler runs can also duplicate notifications, so use the workflow's concurrency group and avoid running additional crawlers at the same time.

Run tests with `python3 -m unittest -v test_crawler`. The legacy JSON and log are ignored locally and remain available in Git history.

Use `./push "Commit message"` to stage all non-ignored changes, commit them, and push. Review `git status` first; never commit credentials or local backups.
