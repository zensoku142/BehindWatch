"""Fetch recent domestic headlines for discreet Windows notifications."""
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from xml.etree import ElementTree

FEED_URL = 'https://www.chinanews.com.cn/rss/china.xml'
MAX_FEED_BYTES = 512 * 1024
NEWS_APP_ID = 'BehindWatch.News'
NEWS_DISPLAY_NAME = '国内新闻速递'


def news_notifications_enabled():
    from winrt.windows.ui.notifications import NotificationSetting, ToastNotificationManager

    notifier = ToastNotificationManager.create_toast_notifier_with_id(NEWS_APP_ID)
    return notifier.setting == NotificationSetting.ENABLED


def register_news_app():
    import winreg
    path = rf'Software\Classes\AppUserModelId\{NEWS_APP_ID}'
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            if winreg.QueryValueEx(key, 'DisplayName')[0] == NEWS_DISPLAY_NAME:
                return
    except OSError:
        pass
    # 未打包的 Python 程序需要独立的用户级通知身份，才能发送可点击的 WinRT 通知。
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
        winreg.SetValueEx(key, 'DisplayName', 0, winreg.REG_EXPAND_SZ, NEWS_DISPLAY_NAME)


def parse_headlines(payload, now=None):
    now = now or datetime.now(timezone.utc)
    headlines = []
    root = ElementTree.fromstring(payload)
    for item in root.findall('./channel/item'):
        title = ' '.join((item.findtext('title') or '').split())
        url = (item.findtext('link') or '').strip()
        published = item.findtext('pubDate') or ''
        try:
            published_at = parsedate_to_datetime(published)
            if published_at.tzinfo is None:
                continue
            age = now - published_at
        except (TypeError, ValueError):
            continue
        # 只展示近两天的真实标题和中新网正文链接，避免旧闻或外部跳转伪装成热点。
        if not title or len(title) > 120 or not -timedelta(minutes=5) <= age <= timedelta(days=2):
            continue
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname not in ('www.chinanews.com.cn', 'chinanews.com.cn'):
            continue
        headlines.append((title, url))
        if len(headlines) == 10:
            break
    return headlines


def fetch_headlines():
    request = Request(FEED_URL, headers={'User-Agent': 'BehindWatch/1.0'})
    with urlopen(request, timeout=8) as response:
        payload = response.read(MAX_FEED_BYTES + 1)
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError('News feed exceeds size limit')
    return parse_headlines(payload)
