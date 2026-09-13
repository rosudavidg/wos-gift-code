[![Crawl WoS gift codes](https://github.com/rosudavidg/wos-gift-code/actions/workflows/crawler.yml/badge.svg)](https://github.com/rosudavidg/wos-gift-code/actions/workflows/crawler.yml)
# wos-gift-code
Whiteout Survival Gift Code Crawler

## Discord notifications

The GitHub Actions workflow can send the current codes to a Discord channel.
Create a webhook from **Discord channel settings > Integrations > Webhooks**,
copy its URL, and add it as this repository secret in GitHub under
**Settings > Secrets and variables > Actions**:

- `DISCORD_WEBHOOK_URL`

Without these secrets, the crawler only prints the codes. With them configured,
each scheduled run sends one Discord message. Keep the webhook URL private because
anyone who has it can post messages to that channel.

The file `known_gift_codes.json` stores every code seen by the crawler and the
timestamp of the last status report. Each run compares the scraped codes with
that file, immediately sending any newly discovered codes to Discord. If no new
codes are found, it only sends a status message once every 24 hours. Any updates
to the stored state are committed back to the repository.
