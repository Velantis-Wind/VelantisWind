# -*- coding: utf-8 -*-
"""Plugin version, read from ``metadata.txt`` so it is declared in one place."""

import configparser
import os

_METADATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "metadata.txt")


def plugin_version() -> str:
    """Return the ``version`` declared in ``metadata.txt`` (empty if unavailable)."""
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(_METADATA_PATH, encoding="utf-8")
    return parser.get("general", "version", fallback="")
