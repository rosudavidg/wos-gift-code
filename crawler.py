from html.parser import HTMLParser
from urllib.request import Request, urlopen


URL = "https://wostools.net/gift-codes"


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
	request = Request(URL, headers={"User-Agent": "Mozilla/5.0"})
	with urlopen(request) as response:
		page = response.read().decode("utf-8", errors="ignore")

	parser = GiftCodeParser()
	parser.feed(page)
	return parser.codes


if __name__ == "__main__":
	print(get_gift_codes())
