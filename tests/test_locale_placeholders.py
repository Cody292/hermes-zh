"""Placeholder parity against the English catalog.

hermes plugins validate only checks that keys exist and values are text.
It does not compare {placeholders}, which is how shortened gateway strings
shipped. This test is the gate for that.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

_PLUGIN = Path(__file__).resolve().parent.parent
_EN_CANDIDATES = [
    Path("/workspace/code/hermes-agent/locales/en.yaml"),
    Path("/tmp/hermes-locales/en.yaml"),
]
_PH = re.compile(r"\{[^{}]+\}")


def _flat(node, prefix=""):
    out = {}
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                out.update(_flat(value, path))
            else:
                out[path] = value
    return out


class TestPlaceholderParity(unittest.TestCase):
    def test_placeholder_sets_match_english(self):
        en_path = next((p for p in _EN_CANDIDATES if p.is_file()), None)
        if en_path is None:
            self.skipTest("en.yaml reference not available")
        zh = _flat(yaml.safe_load((_PLUGIN / "locales" / "zh.yaml").read_text(encoding="utf-8")))
        en = _flat(yaml.safe_load(en_path.read_text(encoding="utf-8")))
        bad = []
        for key, value in zh.items():
            if key not in en:
                bad.append(f"{key}: not in en.yaml")
                continue
            got = set(_PH.findall(value if isinstance(value, str) else ""))
            expect = set(_PH.findall(en[key] if isinstance(en[key], str) else ""))
            if got != expect:
                bad.append(f"{key}: zh={sorted(got)} en={sorted(expect)}")
        self.assertEqual(bad, [], "placeholder set must match en.yaml:\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
