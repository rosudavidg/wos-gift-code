from html.parser import HTMLParser
from time import sleep
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


URL = "https://wostools.net/gift-codes"
MAX_ATTEMPTS = 3


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


if __name__ == "__main__":
	print(get_gift_codes())
