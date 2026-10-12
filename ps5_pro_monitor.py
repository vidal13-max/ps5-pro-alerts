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


def notify(message, token, chat_id):
    """Send a Telegram message, raising on delivery failure."""
    if not token or not chat_id:
        raise RuntimeError('Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID GitHub secret')
    import requests
    response = requests.post(
        f'https://api.telegram.org/bot{token}/sendMessage',
        json={'chat_id': chat_id, 'text': '🎮 PS5 Pro stock alert\n\n' + message,
              'disable_web_page_preview': True}, timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not payload.get('ok'):
        raise RuntimeError('Telegram did not accept the message')
    print('Telegram notification sent.', flush=True)


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
    parser.add_argument('--token', default=os.getenv('TELEGRAM_BOT_TOKEN', ''), help='Telegram bot token')
    parser.add_argument('--chat-id', default=os.getenv('TELEGRAM_CHAT_ID', ''), help='Telegram chat ID')
    parser.add_argument('--show-browser', action='store_true', help='Show browser while checking')
    args = parser.parse_args()
    if args.test_alert:
        notify('Test OK: PS5 Pro alerts are configured. This is not a real stock alert.', args.token, args.chat_id)
        return
    interval = max(args.minutes, 3) * 60
    print('Monitoring:', URL)
    print('Interval:', interval // 60, 'minutes')
    print('Telegram alerts:', 'configured' if args.token and args.chat_id else 'NOT configured')
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
                        notify('PS5 Pro may be available! Open PlayStation Direct now: ' + URL, args.token, args.chat_id)
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
