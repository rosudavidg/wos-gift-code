import argparse
import json
from pathlib import Path

from crawler import api_request


def main():
	parser = argparse.ArgumentParser(description="Initialize the gift-code database from the legacy JSON file.")
	parser.add_argument("file", nargs="?", default="known_gift_codes.json")
	args = parser.parse_args()
	with Path(args.file).open(encoding="utf-8") as source:
		data = json.load(source)
	if isinstance(data, list):
		codes, last_sent = data, None
	elif isinstance(data, dict):
		codes, last_sent = data.get("codes"), data.get("last_status_sent_at")
	else:
		raise ValueError("Legacy data must be an object or a list of codes.")
	if not isinstance(codes, list) or not all(isinstance(code, str) for code in codes):
		raise ValueError("Legacy codes must be a list of strings.")
	result = api_request("/initialize", {"codes": codes, "lastStatusSentAt": last_sent})
	print(f"Initialized {len(result['codes'])} gift codes. Activity will be determined by the next successful crawl.")


if __name__ == "__main__":
	main()