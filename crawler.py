import json
import os
from datetime import datetime, timezone
from html.parser import HTMLParser
from time import sleep
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen


URL = "https://wostools.net/gift-codes"
MAX_ATTEMPTS = 3
DISCORD_MAX_MESSAGE_LENGTH = 2000
HEARTBEAT_INTERVAL_HOURS = 24


class GiftCodeParser(HTMLParser):
	"""Extract alphanumeric gift codes from the Known Gift Codes section."""

	def __init__(self):
		super().__init__()
		self.in_heading = False
		self.heading_text = []
		self.in_known_codes = False
		self.in_code_text = False
		self.code_text = []
		self.codes = []

	def handle_starttag(self, tag, attrs):
		if tag in {"h2", "h3"}:
			if self.in_known_codes:
				self.in_known_codes = False
			self.in_heading = True
			self.heading_text = []
		elif tag == "span":
			attributes = dict(attrs)
			classes = attributes.get("class", "").split()
			if self.in_known_codes and "known-code-text" in classes:
				self.in_code_text = True
				self.code_text = []

	def handle_endtag(self, tag):
		if tag == "span" and self.in_code_text:
			code = "".join(self.code_text).strip()
			if code and code not in self.codes:
				self.codes.append(code)
			self.in_code_text = False
		elif tag in {"h2", "h3"} and self.in_heading:
			heading = " ".join("".join(self.heading_text).split())
			self.in_known_codes = heading == "Known Gift Codes"
			self.in_heading = False

	def handle_data(self, data):
		if self.in_heading:
			self.heading_text.append(data)
		elif self.in_code_text:
			self.code_text.append(data)


def get_gift_codes():
	headers = {
		"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
		"Accept-Language": "en-US,en;q=0.9",
		"User-Agent": (
			"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
			"(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
		),
	}

	for attempt in range(1, MAX_ATTEMPTS + 1):
		request = Request(URL, headers=headers)
		try:
			with urlopen(request, timeout=30) as response:
				page = response.read().decode("utf-8", errors="ignore")
			break
		except (HTTPError, URLError) as error:
			if attempt == MAX_ATTEMPTS:
				raise RuntimeError(
					f"Could not fetch {URL} after {MAX_ATTEMPTS} attempts: {error}"
				) from error
			sleep(attempt * 2)

	parser = GiftCodeParser()
	parser.feed(page)
	if not parser.codes:
		raise RuntimeError("No gift codes found in the expected section; refusing to update the database.")
	return parser.codes


class RejectRedirects(HTTPRedirectHandler):
	def redirect_request(self, request, file_pointer, code, message, headers, new_url):
		raise RuntimeError("Gift code API redirects are not allowed.")


def api_request(path, data):
	base_url = os.getenv("GIFT_CODE_API_URL", "").rstrip("/")
	api_key = os.getenv("GIFT_CODE_API_KEY")
	if not base_url or not api_key:
		raise RuntimeError("GIFT_CODE_API_URL and GIFT_CODE_API_KEY are required.")
	parsed = urlsplit(base_url)
	if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
		or not (parsed.scheme == "https" or (parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}))):
		raise RuntimeError("GIFT_CODE_API_URL must use HTTPS except on localhost.")
	request = Request(
		f"{base_url}/gift-codes{path}",
		data=json.dumps(data).encode("utf-8"),
		headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
		method="POST",
	)
	try:
		with build_opener(RejectRedirects()).open(request, timeout=90) as response:
			return json.load(response)
	except HTTPError as error:
		raise RuntimeError(f"Gift code API request failed with HTTP {error.code}: {error.read().decode('utf-8', errors='replace')}") from error


def log_event(message, event_time=None):
	if event_time is None:
		event_time = datetime.now(timezone.utc)
	bucharest_time = event_time.astimezone(ZoneInfo("Europe/Bucharest"))
	timestamp = bucharest_time.strftime("%Y-%m-%d %H:%M:%S %Z")
	print(f"[{timestamp}] {message}")


def build_discord_message(new_codes, checked_at=None):
	if len(new_codes) == 1:
		return (
			"🎁 A new gift code is available!\n\n"
			f"Redeem this code:\n- 🎁 {new_codes[0]}"
		)
	elif new_codes:
		code_list = "\n".join(f"- 🎁 {code}" for code in new_codes)
		return (
			"🎁 New gift codes are available!\n\n"
			f"Redeem these codes:\n{code_list}"
		)

	if checked_at is None:
		checked_at = datetime.now(timezone.utc)
	bucharest_time = checked_at.astimezone(ZoneInfo("Europe/Bucharest"))
	timestamp = bucharest_time.strftime("%Y-%m-%d %H:%M %Z (Europe/Bucharest)")
	return f"No new gift codes in the last 24 hours. Checked: `{timestamp}`"


def send_discord_message(message):
	webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
	if not webhook_url:
		return False

	body = message
	if len(body.encode("utf-16-le")) // 2 > DISCORD_MAX_MESSAGE_LENGTH:
		raise RuntimeError("The gift-code message exceeds Discord's 2,000-character limit.")

	request = Request(
		webhook_url,
		data=json.dumps({"content": body}).encode("utf-8"),
		headers={
			"Content-Type": "application/json",
			"User-Agent": "wos-gift-code-crawler/1.0",
		},
		method="POST",
	)
	try:
		with urlopen(request, timeout=30) as response:
			response.read()
	except HTTPError as error:
		if error.code == 403:
			raise RuntimeError(
				"Discord rejected DISCORD_WEBHOOK_URL (HTTP 403). "
				"Recreate the webhook and update the GitHub secret with its complete URL."
			) from error
		raise RuntimeError(
			f"Discord webhook request failed with HTTP {error.code}."
		) from error
	return True


def notification_batches(codes):
	batch = []
	for code in codes:
		candidate = batch + [code]
		if len(build_discord_message(candidate).encode("utf-16-le")) // 2 > DISCORD_MAX_MESSAGE_LENGTH:
			if not batch:
				raise RuntimeError("A gift code cannot fit in a Discord message.")
			yield batch
			batch = [code]
		else:
			batch = candidate
	if batch:
		yield batch


def main():
	now = datetime.now(timezone.utc)
	log_event("Crawler started: fetching gift codes from website...", now)

	retrieved_codes = get_gift_codes()
	data = api_request("/observations", {"codes": retrieved_codes})
	pending_codes = data["pendingNewCodes"]

	log_event(f"Retrieved codes: {retrieved_codes}", now)
	log_event(f"Pending new codes: {pending_codes}", now)
	last_activity = max(
		datetime.fromisoformat(value.replace("Z", "+00:00"))
		for value in (data["notificationBaselineAt"], data["lastStatusSentAt"], data["lastNewCodeAt"])
		if value
	)
	heartbeat_due = (now - last_activity).total_seconds() >= HEARTBEAT_INTERVAL_HOURS * 3600
	if pending_codes or heartbeat_due:
		batches = notification_batches(pending_codes) if pending_codes else [[]]
		for batch in batches:
			message = build_discord_message(batch, checked_at=now)
			if not send_discord_message(message):
				log_event("Discord webhook not configured; notification remains pending.", now)
				break
			api_request("/notifications/acknowledge", {"codes": batch})
			log_event("Discord notification sent and acknowledged.", now)
	else:
		log_event("No notification due.", now)


if __name__ == "__main__":
	main()
