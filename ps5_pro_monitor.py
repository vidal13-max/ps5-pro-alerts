#!/usr/bin/env python3
"""PS5 Pro PlayStation Direct availability notifier (not an auto-purchaser)."""
import argparse
import datetime as dt
import os
import re
import sys
import time
import webbrowser
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = 'https://direct.playstation.com/en-us/buy-consoles/playstation5-pro-console-2-tb'
OUT = re.compile(r'not in stock|out of stock|sold out|currently unavailable|check back later', re.I)
BUY = re.compile(r'^\s*(add to cart|add to bag|buy now)\s*$', re.I)


def notify(message, topic):
    print('\a' + message, flush=True)
    if topic:
        try:
            import requests
            response = requests.post(f'https://ntfy.sh/{topic}', data=message.encode('utf-8'),
                                     headers={'Title': 'PS5 Pro stock alert', 'Priority': 'urgent',
                                              'Click': URL, 'Tags': 'video_game'}, timeout=12)
            response.raise_for_status()
            print('Phone notification sent.', flush=True)
        except Exception as exc:
            print(f'Notification failed: {exc}', flush=True)


def status(page):
    # Product pages are rendered dynamically. Only report available when an actionable,
    # visible, enabled purchase button is found. Never guess from page text alone.
    page.goto(URL, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(5000)
    buttons = page.get_by_role('button', name=BUY)
    for i in range(buttons.count()):
        button = buttons.nth(i)
        if button.is_visible() and button.is_enabled():
            return 'BUY_BUTTON'
    body = page.locator('body').inner_text(timeout=10000)
    if OUT.search(body):
        return 'OUT_OF_STOCK'
    return 'UNKNOWN'


def main():
    parser = argparse.ArgumentParser(description='Monitor PS5 Pro stock at PlayStation Direct')
    parser.add_argument('--once', action='store_true', help='Check once, for cloud scheduling')
    parser.add_argument('--test-alert', action='store_true', help='Send test notification without visiting store')
    parser.add_argument('--minutes', type=int, default=5, help='Interval in minutes (minimum 3)')
    parser.add_argument('--topic', default=os.getenv('NTFY_TOPIC', ''),
                        help='Unique ntfy topic for push notifications (optional)')
    parser.add_argument('--show-browser', action='store_true', help='Show browser while checking')
    args = parser.parse_args()
    if args.test_alert:
        if not args.topic:
            sys.exit('Set NTFY_TOPIC secret before testing.')
        notify('Test OK: PS5 Pro alerts are configured. This is not a real stock alert.', args.topic)
        return
    interval = max(args.minutes, 3) * 60
    print('Monitoring:', URL)
    print('Interval:', interval // 60, 'minutes')
    print('Phone alerts:', 'enabled' if args.topic else 'disabled (terminal bell only)')
    last = None
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.show_browser)
        page = browser.new_page(locale='en-US', viewport={'width': 1200, 'height': 900})
        try:
            while True:
                try:
                    current = status(page)
                    print(dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), current, flush=True)
                    if current == 'BUY_BUTTON' and last != 'BUY_BUTTON':
                        notify('PS5 Pro may be available! Open PlayStation Direct now: ' + URL, args.topic)
                        if not args.once:
                            webbrowser.open(URL)
                    elif current == 'UNKNOWN' and last != 'UNKNOWN':
                        print('Page could not be classified. It may have changed or presented a challenge; check manually.', flush=True)
                    last = current
                except Exception as exc:
                    print('Check failed (not interpreted as in stock):', str(exc)[:300], flush=True)
                if args.once:
                    break
                time.sleep(interval)
        except KeyboardInterrupt:
            print('\nStopped.')
        finally:
            browser.close()


if __name__ == '__main__':
    main()
