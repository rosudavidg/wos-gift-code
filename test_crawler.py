import io
import json
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import crawler
import migrate_gift_codes


class CrawlerTests(unittest.TestCase):
	def test_parser_extracts_only_expected_section_and_deduplicates(self):
		parser = crawler.GiftCodeParser()
		parser.feed('<h2>Other</h2><span class="known-code-text">IGNORE</span>'
			'<h2>Known Gift Codes</h2><span class="known-code-text">ABC123</span>'
			'<span class="known-code-text">ABC123</span><h2>Expired</h2>'
			'<span class="known-code-text">OLD</span>')
		self.assertEqual(parser.codes, ['ABC123'])

	def test_empty_source_does_not_update_database(self):
		with patch('crawler.urlopen', return_value=io.BytesIO(b'<h2>Changed page</h2>')):
			with self.assertRaises(RuntimeError):
				crawler.get_gift_codes()

	def test_discord_success_acknowledges_only_sent_codes(self):
		now = datetime.now(timezone.utc)
		state = {'pendingNewCodes': ['NEW'], 'notificationBaselineAt': now.isoformat(),
			'lastStatusSentAt': None, 'lastNewCodeAt': now.isoformat()}
		with patch('crawler.get_gift_codes', return_value=['NEW']), \
			patch('crawler.api_request', side_effect=[state, {}]) as api, \
			patch('crawler.send_discord_message', return_value=True):
			crawler.main()
		self.assertEqual(api.call_args_list[1].args, ('/notifications/acknowledge', {'codes': ['NEW']}))

	def test_failed_or_missing_discord_does_not_acknowledge(self):
		now = datetime.now(timezone.utc)
		state = {'pendingNewCodes': ['NEW'], 'notificationBaselineAt': now.isoformat(),
			'lastStatusSentAt': None, 'lastNewCodeAt': now.isoformat()}
		with patch('crawler.get_gift_codes', return_value=['NEW']), \
			patch('crawler.api_request', return_value=state) as api, \
			patch('crawler.send_discord_message', return_value=False):
			crawler.main()
		self.assertEqual(api.call_count, 1)

	def test_heartbeat_waits_for_last_discovery(self):
		now = datetime.now(timezone.utc)
		state = {'pendingNewCodes': [], 'notificationBaselineAt': (now - timedelta(days=2)).isoformat(),
			'lastStatusSentAt': (now - timedelta(days=2)).isoformat(), 'lastNewCodeAt': now.isoformat()}
		with patch('crawler.get_gift_codes', return_value=['OLD']), \
			patch('crawler.api_request', return_value=state), \
			patch('crawler.send_discord_message') as send:
			crawler.main()
		send.assert_not_called()

	def test_large_backlog_fits_discord_limit(self):
		codes = [f'CODE{index:04d}' for index in range(500)]
		batches = list(crawler.notification_batches(codes))
		self.assertGreater(len(batches), 1)
		self.assertEqual([code for batch in batches for code in batch], codes)
		for batch in batches:
			self.assertLessEqual(len(crawler.build_discord_message(batch).encode('utf-16-le')) // 2, 2000)

	def test_migration_passes_legacy_data_to_create_only_endpoint(self):
		legacy = {'codes': ['OLD'], 'last_status_sent_at': '2026-01-01T00:00:00+00:00'}
		with patch('sys.argv', ['migrate_gift_codes.py', 'legacy.json']), \
			patch('pathlib.Path.open', return_value=io.StringIO(json.dumps(legacy))), \
			patch('migrate_gift_codes.api_request', return_value={'codes': [{}]}) as api:
			migrate_gift_codes.main()
		api.assert_called_once_with('/initialize', {'codes': ['OLD'], 'lastStatusSentAt': legacy['last_status_sent_at']})


if __name__ == '__main__':
	unittest.main()