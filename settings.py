#!/usr/bin/env python

from __future__ import print_function, unicode_literals

import os
import json

import config

SETTINGS_FILE = os.path.expanduser(
    os.path.join(config.DATA_DIR, "settings.json")
)

_settings = None


def _ensure_loaded():
    if _settings is None:
        load()


def load():
    global _settings
    _settings = {}
    if os.path.isfile(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            _settings.update(json.load(f))


def save():
    dir = os.path.dirname(SETTINGS_FILE)
    if not os.path.isdir(dir):
        os.makedirs(dir)

    with open(SETTINGS_FILE, "w") as f:
        json.dump(_settings, f, indent=4)


def _resolve(key, create):
    container = _settings
    key_parts = key.split(".")
    for part in key_parts[:-1]:
        if part not in container:
            if not create:
                return None, None

            container[part] = {}

        container = container[part]
        if not isinstance(container, dict):
            raise KeyError("Invalid container: " + part)

    return container, key_parts[-1]


def set(key, value):
    _ensure_loaded()
    container, last_key = _resolve(key, True)
    container[last_key] = value
    save()


def get(key, default=None):
    _ensure_loaded()
    container, last_key = _resolve(key, False)
    if container is None:
        return default

    return container.get(last_key, default)


def delete(key):
    _ensure_loaded()
    container, last_key = _resolve(key, False)
    if container is None or last_key not in container:
        return

    del container[last_key]
    save()


if __name__ == "__main__":
    import sys
    if len(sys.argv) == 1:
        load()
        print(json.dumps(_settings))
    elif len(sys.argv) == 2:
        print(get(sys.argv[1]))
    else:
        _, key, value = sys.argv
        try:
            value = int(value)
        except ValueError:
            value = value.strip('"')  # Allow setting numbers as string

        if value == "--delete":
            delete(key)
        else:
            set(key, value)
