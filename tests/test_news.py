"""RSS headline selection without network access."""
import unittest
from datetime import datetime, timezone

from core.news import parse_headlines


class NewsTests(unittest.TestCase):
    def test_recent_domestic_headlines_keep_matching_article_links(self):
        feed = b'''<rss><channel>
            <item><title>First headline</title><link>https://www.chinanews.com.cn/gn/2026/09-16/1.shtml</link><pubDate>Wed, 16 Sep 2026 12:00:00 GMT</pubDate></item>
            <item><title>Old headline</title><link>https://www.chinanews.com.cn/gn/2026/09-10/2.shtml</link><pubDate>Thu, 10 Sep 2026 12:00:00 GMT</pubDate></item>
            <item><title>External headline</title><link>https://example.com/story</link><pubDate>Wed, 16 Sep 2026 12:00:00 GMT</pubDate></item>
        </channel></rss>'''
        headlines = parse_headlines(feed, datetime(2026, 9, 16, 15, tzinfo=timezone.utc))
        self.assertEqual(headlines, [('First headline', 'https://www.chinanews.com.cn/gn/2026/09-16/1.shtml')])


if __name__ == '__main__':
    unittest.main()
