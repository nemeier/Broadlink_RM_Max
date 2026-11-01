"""Test the installation scaffold without installing Home Assistant."""

import ast
import importlib
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "broadlink_rm_max"


class FakeConfigFlow:
    """Implement only the Home Assistant flow methods used by the scaffold."""

    def __init_subclass__(cls, *, domain):
        cls.domain = domain

    def _async_current_entries(self):
        return getattr(self, "entries", [])

    def async_show_form(self, *, step_id):
        return {"type": "form", "step_id": step_id}

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}


class InstallationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        modules = {
            name: ModuleType(name)
            for name in (
                "homeassistant",
                "homeassistant.config_entries",
                "homeassistant.core",
                "homeassistant.data_entry_flow",
            )
        }
        modules["homeassistant.config_entries"].ConfigEntry = object
        modules["homeassistant.config_entries"].ConfigFlow = FakeConfigFlow
        modules["homeassistant.core"].HomeAssistant = object
        modules["homeassistant.data_entry_flow"].FlowResult = dict
        modules["homeassistant"].config_entries = modules[
            "homeassistant.config_entries"
        ]
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.integration = importlib.import_module(
            "custom_components.broadlink_rm_max"
        )
        flow_module = importlib.import_module(
            "custom_components.broadlink_rm_max.config_flow"
        )
        self.flow = flow_module.BroadlinkRMMaxConfigFlow()

    async def test_shows_installation_form(self):
        self.assertEqual(
            await self.flow.async_step_user(),
            {"type": "form", "step_id": "user"},
        )
        self.assertEqual(self.flow.domain, "broadlink_rm_max")

    async def test_creates_empty_entry(self):
        self.assertEqual(
            await self.flow.async_step_user({}),
            {"type": "create_entry", "title": "Broadlink RM Max", "data": {}},
        )

    async def test_rejects_duplicate_entry(self):
        self.flow.entries = [object()]
        for user_input in (None, {}):
            self.assertEqual(
                await self.flow.async_step_user(user_input),
                {"type": "abort", "reason": "single_instance_allowed"},
            )

    async def test_setup_and_unload(self):
        self.assertTrue(await self.integration.async_setup_entry(None, None))
        self.assertTrue(await self.integration.async_unload_entry(None, None))


class PackageTests(unittest.TestCase):
    def test_manifest_is_independent(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text())
        self.assertEqual(manifest["domain"], "broadlink_rm_max")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["dependencies"], [])
        self.assertEqual(manifest["requirements"], [])
        self.assertEqual(manifest["version"], "0.1.0")
        for source in COMPONENT.glob("*.py"):
            tree = ast.parse(source.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [node.module or ""]
                else:
                    continue
                for name in imported:
                    self.assertFalse(
                        name == "broadlink"
                        or name.startswith("broadlink.")
                        or name.startswith("homeassistant.components.broadlink"),
                        f"Forbidden dependency in {source.name}: {name}",
                    )

    def test_translations_match_strings(self):
        strings = json.loads((COMPONENT / "strings.json").read_text())
        for translation in (COMPONENT / "translations").glob("*.json"):
            translated = json.loads(translation.read_text())
            self.assertEqual(translated.keys(), strings.keys())
            self.assertEqual(
                translated["config"]["abort"].keys(),
                strings["config"]["abort"].keys(),
            )
            self.assertEqual(
                translated["config"]["step"].keys(),
                strings["config"]["step"].keys(),
            )


if __name__ == "__main__":
    unittest.main()