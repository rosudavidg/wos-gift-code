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
