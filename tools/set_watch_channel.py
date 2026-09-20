#!/usr/bin/env python3
"""Register the Telegram channel the watchdog sends to, and prove it works.

Run this on the host, as root, with the bot token in hand. The token is read from the command line
and written straight into /etc/teemo-watch.env (0600, root) - it is never printed, never logged, and
never echoed back.

    python3 tools/set_watch_channel.py --token 123456:AA...            # find the chat, then test
    python3 tools/set_watch_channel.py --token 123456:AA... --chat 987654321
    python3 tools/set_watch_channel.py --show                          # what is registered now
    python3 tools/set_watch_channel.py --test                          # send a test message

Getting a token: talk to @BotFather in Telegram, send /newbot, follow the two questions, and the
token is the last line it prints. Then send any message to your new bot - until you do, the bot has
no chat to answer and this script cannot find your chat id.

The channel is one file with two keys:
    TELEGRAM_BOT_TOKEN=...
    TELEGRAM_CHAT_ID=...
"""
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CHANNEL_FILE = Path("/etc/teemo-watch.env")
API = "https://api.telegram.org/bot%s/%s"


def call(token: str, method: str, payload: dict | None = None, timeout: int = 20) -> dict:
    data = urllib.parse.urlencode(payload or {}).encode("utf-8")
    request = urllib.request.Request(API % (token, method), data=data if payload else None)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            return json.loads(answer.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            return json.loads(body)
        except ValueError:
            return {"ok": False, "description": "HTTP %s" % error.code}
    except Exception as error:                                      # noqa: BLE001
        return {"ok": False, "description": "%s: %s" % (type(error).__name__, str(error)[:100])}


def find_chat(token: str) -> tuple[str, str]:
    """The chat id from the bot's unread messages, and a label for it."""
    answer = call(token, "getUpdates")
    if not answer.get("ok"):
        return "", answer.get("description", "getUpdates failed")
    chats = []
    for update in answer.get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        if chat.get("id"):
            name = chat.get("title") or chat.get("username") or chat.get("first_name") or "chat"
            chats.append((str(chat["id"]), str(name)))
    if not chats:
        return "", ("no chat yet - send a message to your bot in Telegram, then run this again "
                    "(the bot cannot see a chat until somebody writes to it)")
    return chats[-1]


def write_channel(token: str, chat: str) -> None:
    CHANNEL_FILE.write_text("TELEGRAM_BOT_TOKEN=%s\nTELEGRAM_CHAT_ID=%s\n" % (token, chat),
                            encoding="utf-8")
    os.chmod(CHANNEL_FILE, stat.S_IRUSR | stat.S_IWUSR)              # 0600: root only


def read_channel() -> tuple[str, str]:
    if not CHANNEL_FILE.is_file():
        return "", ""
    values = {}
    for line in CHANNEL_FILE.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values.get("TELEGRAM_BOT_TOKEN", ""), values.get("TELEGRAM_CHAT_ID", "")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", default="", help="bot token from @BotFather (never printed)")
    parser.add_argument("--chat", default="", help="chat id; found from getUpdates when omitted")
    parser.add_argument("--show", action="store_true", help="print what is registered, not the token")
    parser.add_argument("--test", action="store_true", help="send one test message")
    parser.add_argument("--force", action="store_true", help="overwrite an existing channel file")
    args = parser.parse_args()

    if args.show:
        token, chat = read_channel()
        if not token:
            print("  no channel file at %s" % CHANNEL_FILE)
            return 1
        print("  %s: token %d chars, chat %s, mode %s"
              % (CHANNEL_FILE, len(token), chat or "(없음)", oct(CHANNEL_FILE.stat().st_mode & 0o777)))
        return 0

    if args.test:
        token, chat = read_channel()
        if not token or not chat:
            print("  no channel file to test")
            return 1
    else:
        token = args.token or read_channel()[0]
        if not token:
            print("  --token is required (or run --show to see what is registered)")
            return 2
        if CHANNEL_FILE.exists() and not args.force:
            print("  %s already exists - pass --force to replace it" % CHANNEL_FILE)
            return 2
        chat = args.chat
        if not chat:
            chat, label = find_chat(token)
            if not chat:
                print("  %s" % label)
                return 1
            print("  chat id %s (%s)" % (chat, label))

    answer = call(token, "sendMessage", {"chat_id": chat, "text": "✅ teemobkk.io 감시 연결됨"})
    if not answer.get("ok"):
        print("  send failed: %s" % answer.get("description", "?"))
        return 1
    print("  test message sent")

    if not args.test:
        write_channel(token, chat)
        print("  wrote %s (0600, root)" % CHANNEL_FILE)
        print("  the watchdog will send to this chat from its next run (every 30 minutes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
