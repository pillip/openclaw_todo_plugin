"""Tests for openclaw.plugin.json manifest fields."""

from __future__ import annotations

import json
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "bridge" / "openclaw-todo" / "openclaw.plugin.json"


class TestManifestBypassLlm:
    """Verify command_prefix and bypass_llm fields in the plugin manifest."""

    def test_manifest_is_valid_json(self):
        data = json.loads(MANIFEST_PATH.read_text())
        assert isinstance(data, dict)

    def test_command_prefix_exists_and_correct(self):
        data = json.loads(MANIFEST_PATH.read_text())
        assert data["command_prefix"] == "todo:"

    def test_bypass_llm_exists_and_true(self):
        data = json.loads(MANIFEST_PATH.read_text())
        assert data["bypass_llm"] is True

    def test_triggers_block_preserved(self):
        data = json.loads(MANIFEST_PATH.read_text())
        assert "triggers" in data
        assert "dm" in data["triggers"]
        assert "pattern" in data["triggers"]["dm"]

    def test_existing_fields_intact(self):
        data = json.loads(MANIFEST_PATH.read_text())
        assert data["id"] == "openclaw-todo"
        assert data["name"] == "openclaw-todo"
        assert "version" in data
        assert "main" in data
        assert "configSchema" in data
