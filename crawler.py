import json
import os
from datetime import datetime, timezone
from html.parser import HTMLParser
from time import sleep
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


URL = "https://wostools.net/gift-codes"
STORED_CODES_FILE = "known_gift_codes.json"
LOG_FILE = "crawler.log"
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
	return parser.codes


def load_stored_data():
	try:
		with open(STORED_CODES_FILE, encoding="utf-8") as file:
			data = json.load(file)
	except FileNotFoundError:
		return {"codes": [], "last_status_sent_at": None}

	if isinstance(data, list):
		return {
			"codes": [code for code in data if isinstance(code, str)],
			"last_status_sent_at": None,
		}

	if isinstance(data, dict):
		codes = data.get("codes", [])
		if not isinstance(codes, list) or not all(
			isinstance(code, str) for code in codes
		):
			raise RuntimeError(f"{STORED_CODES_FILE} 'codes' field must be a list of strings.")
		return {
			"codes": codes,
			"last_status_sent_at": data.get("last_status_sent_at"),
		}

	raise RuntimeError(f"{STORED_CODES_FILE} must contain a JSON object or list.")


def save_stored_data(data):
	with open(STORED_CODES_FILE, "w", encoding="utf-8") as file:
		json.dump(data, file, indent=2)
		file.write("\n")


def log_event(message, event_time=None):
	if event_time is None:
		event_time = datetime.now(timezone.utc)
	bucharest_time = event_time.astimezone(ZoneInfo("Europe/Bucharest"))
	timestamp = bucharest_time.strftime("%Y-%m-%d %H:%M:%S %Z")
	log_line = f"[{timestamp}] {message}\n"
	print(message)
	with open(LOG_FILE, "a", encoding="utf-8") as file:
		file.write(log_line)


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
		return

	body = message
	if len(body) > DISCORD_MAX_MESSAGE_LENGTH:
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


if __name__ == "__main__":
	now = datetime.now(timezone.utc)
	log_event("Crawler started: fetching gift codes from website...", now)

	retrieved_codes = get_gift_codes()
	data = load_stored_data()
	stored_codes = data.get("codes", [])
	new_codes = [code for code in retrieved_codes if code not in stored_codes]

	log_event(f"Retrieved codes: {retrieved_codes}", now)
	log_event(f"New codes: {new_codes}", now)

	if new_codes:
		message = build_discord_message(new_codes)
		send_discord_message(message)
		data["codes"] = stored_codes + new_codes
		data["last_status_sent_at"] = now.isoformat()
		save_stored_data(data)
		log_event(f"Found new codes ({len(new_codes)}) and sent message to Discord.", now)
	else:
		last_sent_str = data.get("last_status_sent_at")
		should_send_heartbeat = False
		if last_sent_str:
			try:
				last_sent_dt = datetime.fromisoformat(last_sent_str.replace("Z", "+00:00"))
				if (now - last_sent_dt).total_seconds() >= HEARTBEAT_INTERVAL_HOURS * 3600:
					should_send_heartbeat = True
			except (ValueError, TypeError):
				should_send_heartbeat = True
		else:
			data["last_status_sent_at"] = now.isoformat()
			save_stored_data(data)

		if should_send_heartbeat:
			message = build_discord_message([], checked_at=now)
			send_discord_message(message)
			data["last_status_sent_at"] = now.isoformat()
			save_stored_data(data)
			log_event("No new codes found (24h elapsed) and sent 24h status message to Discord.", now)
		else:
			log_event("No new codes found and did not send message (<24h elapsed).", now)
