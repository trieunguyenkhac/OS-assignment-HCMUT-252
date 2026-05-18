"""Shared message helpers for the sample chat app."""

import time


def build_channel_message(sender, channel, text):
    return {
        "from": sender,
        "channel": channel,
        "text": text,
        "created_at": time.time(),
    }


def build_direct_message(sender, target, text):
    return {
        "from": sender,
        "to": target,
        "text": text,
        "created_at": time.time(),
    }


def append_message(messages, channel, message):
    messages.setdefault(channel, []).append(message)
    return message


def list_messages(messages, channel):
    return list(messages.get(channel, []))
