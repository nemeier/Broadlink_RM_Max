"""Test the installation scaffold without installing Home Assistant."""

import ast
import importlib
import json
from pathlib import Path
import socket
import struct
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "custom_components" / "broadlink_rm_max"


class FakeConfigFlow:
    """Implement only the Home Assistant flow methods used by the scaffold."""

    def __init_subclass__(cls, *, domain):
        cls.domain = domain

    def _async_current_entries(self):
        return getattr(self, "entries", [])

    def async_show_form(self, *, step_id, data_schema, errors):
        return {
            "type": "form",
            "step_id": step_id,
            "data_schema": data_schema,
            "errors": errors,
        }

    async def async_set_unique_id(self, unique_id):
        self.unique_id = unique_id

    def _abort_if_unique_id_configured(self):
        pass

    def _get_reconfigure_entry(self):
        return self.reconfigure_entry

    def async_update_reload_and_abort(self, entry, *, unique_id, data_updates):
        entry.unique_id = unique_id
        entry.data.update(data_updates)
        return self.async_abort(reason="reconfigure_successful")

    def async_abort(self, *, reason):
        return {"type": "abort", "reason": reason}

    def async_create_entry(self, *, title, data):
        return {"type": "create_entry", "title": title, "data": data}


class HomeAssistantTestCase(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        modules = {
            name: ModuleType(name)
            for name in (
                "homeassistant",
                "homeassistant.config_entries",
                "homeassistant.const",
                "homeassistant.core",
                "homeassistant.data_entry_flow",
                "homeassistant.exceptions",
                "homeassistant.helpers",
                "homeassistant.helpers.device_registry",
            )
        }
        modules["homeassistant.config_entries"].ConfigEntry = object
        modules["homeassistant.config_entries"].ConfigFlow = FakeConfigFlow
        modules["homeassistant.const"].CONF_HOST = "host"
        modules["homeassistant.core"].HomeAssistant = object
        modules["homeassistant.data_entry_flow"].FlowResult = dict
        modules["homeassistant.exceptions"].ConfigEntryError = type(
            "ConfigEntryError", (Exception,), {}
        )
        modules["homeassistant.exceptions"].ConfigEntryNotReady = type(
            "ConfigEntryNotReady", (Exception,), {}
        )
        self.device_registry = MagicMock()
        modules["homeassistant.helpers.device_registry"].async_get = MagicMock(
            return_value=self.device_registry
        )
        modules["homeassistant.helpers"].device_registry = modules[
            "homeassistant.helpers.device_registry"
        ]
        modules["homeassistant"].config_entries = modules[
            "homeassistant.config_entries"
        ]
        self.module_patch = patch.dict(sys.modules, modules)
        self.module_patch.start()
        self.addCleanup(self.module_patch.stop)
        self.integration = importlib.import_module("custom_components.broadlink_rm_max")
        flow_module = importlib.import_module(
            "custom_components.broadlink_rm_max.config_flow"
        )
        self.flow = flow_module.BroadlinkRMMaxConfigFlow()
        self.flow.hass = SimpleNamespace(async_add_executor_job=AsyncMock())


class InstallationTests(HomeAssistantTestCase):
    async def test_shows_installation_form(self):
        result = await self.flow.async_step_user()
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(result["errors"], {})
        self.assertEqual(
            result["data_schema"]({"host": "rm-max.local"}), {"host": "rm-max.local"}
        )
        self.flow.hass.async_add_executor_job.assert_not_called()
        self.assertEqual(self.flow.domain, "broadlink_rm_max")

    async def test_creates_entry_only_after_successful_test(self):
        connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        self.flow.hass.async_add_executor_job.return_value = connection.DeviceInfo(
            "192.168.1.50", "112233445566", 0xAF8B, "FCBLE GW"
        )
        self.assertEqual(
            await self.flow.async_step_user({"host": " rm-max.local "}),
            {
                "type": "create_entry",
                "title": "Broadlink RM Max",
                "data": {
                    "host": "rm-max.local",
                    "mac": "112233445566",
                    "devtype": 0xAF8B,
                    "name": "FCBLE GW",
                },
            },
        )
        self.assertEqual(self.flow.unique_id, "112233445566")
        self.flow.hass.async_add_executor_job.assert_awaited_once_with(
            connection.test_connection, "rm-max.local"
        )

    async def test_connection_errors_do_not_create_entry(self):
        connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        for reason in (
            "invalid_host",
            "cannot_resolve",
            "cannot_connect",
            "unsupported_device",
            "auth_failed",
            "invalid_response",
        ):
            with self.subTest(reason=reason):
                self.flow.hass.async_add_executor_job.side_effect = (
                    connection.ConnectionFailure(reason)
                )
                result = await self.flow.async_step_user({"host": "rm-max.local"})
                self.assertEqual(result["type"], "form")
                location = (
                    "host" if reason in ("invalid_host", "cannot_resolve") else "base"
                )
                self.assertEqual(result["errors"], {location: reason})
                self.assertFalse(hasattr(self.flow, "unique_id"))

    async def test_reconfigures_legacy_empty_entry(self):
        connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        self.flow.reconfigure_entry = SimpleNamespace(data={}, unique_id=None)
        form = await self.flow.async_step_reconfigure()
        self.assertEqual(form["step_id"], "reconfigure")
        self.flow.hass.async_add_executor_job.return_value = connection.DeviceInfo(
            "192.168.1.50", "112233445566", 0xAF8B, "FCBLE GW"
        )
        result = await self.flow.async_step_reconfigure({"host": "192.168.1.50"})
        self.assertEqual(result, {"type": "abort", "reason": "reconfigure_successful"})
        self.assertEqual(self.flow.reconfigure_entry.data["host"], "192.168.1.50")
        self.assertEqual(self.flow.reconfigure_entry.unique_id, "112233445566")

    async def test_reconfigure_rejects_different_device(self):
        connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        self.flow.reconfigure_entry = SimpleNamespace(data={"mac": "aabbccddeeff"})
        self.flow.hass.async_add_executor_job.return_value = connection.DeviceInfo(
            "192.168.1.50", "112233445566", 0xAF8B, "FCBLE GW"
        )
        result = await self.flow.async_step_reconfigure({"host": "192.168.1.50"})
        self.assertEqual(result, {"type": "abort", "reason": "wrong_device"})
        self.assertEqual(self.flow.reconfigure_entry.data, {"mac": "aabbccddeeff"})

    async def test_rejects_duplicate_entry(self):
        self.flow.entries = [object()]
        for user_input in (None, {}):
            self.assertEqual(
                await self.flow.async_step_user(user_input),
                {"type": "abort", "reason": "single_instance_allowed"},
            )

    async def test_setup_and_unload(self):
        connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        device = connection.DeviceInfo(
            "192.168.1.50", "112233445566", 0xAF8B, "FCBLE GW"
        )
        self.flow.hass.async_add_executor_job.return_value = device
        entry = SimpleNamespace(
            data={"host": "rm-max.local", "mac": device.mac}, entry_id="test-entry"
        )
        with patch.object(
            self.integration.dr, "async_get", return_value=self.device_registry
        ):
            self.assertTrue(
                await self.integration.async_setup_entry(self.flow.hass, entry)
            )
        self.assertEqual(entry.runtime_data, device)
        self.device_registry.async_get_or_create.assert_called_once_with(
            config_entry_id="test-entry",
            identifiers={("broadlink_rm_max", device.mac)},
            manufacturer="Broadlink",
            model="RM Max",
            name="Broadlink RM Max",
        )
        self.assertTrue(
            await self.integration.async_unload_entry(self.flow.hass, entry)
        )

    async def test_setup_legacy_entry_requires_reconfigure(self):
        with self.assertRaisesRegex(self.integration.ConfigEntryError, "Reconfigure"):
            await self.integration.async_setup_entry(
                self.flow.hass, SimpleNamespace(data={})
            )
        self.flow.hass.async_add_executor_job.assert_not_called()

    async def test_setup_retries_network_failure(self):
        connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        self.flow.hass.async_add_executor_job.side_effect = (
            connection.ConnectionFailure("cannot_connect")
        )
        with self.assertRaises(self.integration.ConfigEntryNotReady):
            await self.integration.async_setup_entry(
                self.flow.hass, SimpleNamespace(data={"host": "rm-max.local"})
            )

    async def test_setup_rejects_failed_authentication(self):
        connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        self.flow.hass.async_add_executor_job.side_effect = (
            connection.ConnectionFailure("auth_failed")
        )
        with self.assertRaises(self.integration.ConfigEntryError):
            await self.integration.async_setup_entry(
                self.flow.hass, SimpleNamespace(data={"host": "rm-max.local"})
            )

    async def test_setup_rejects_changed_mac(self):
        connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        self.flow.hass.async_add_executor_job.return_value = connection.DeviceInfo(
            "192.168.1.50", "112233445566", 0xAF8B, "FCBLE GW"
        )
        with self.assertRaisesRegex(
            self.integration.ConfigEntryError, "different device"
        ):
            await self.integration.async_setup_entry(
                self.flow.hass,
                SimpleNamespace(data={"host": "rm-max.local", "mac": "aabbccddeeff"}),
            )


class ConnectionTests(HomeAssistantTestCase):
    def setUp(self):
        super().setUp()
        self.connection = importlib.import_module(
            "custom_components.broadlink_rm_max.connection"
        )
        self.conn = MagicMock()
        self.conn.getsockname.return_value = ("192.168.1.10", 12345)
        self.conn.__enter__.return_value = self.conn
        self.socket_patch = patch.object(
            self.connection, "udp_socket", return_value=self.conn
        )
        self.socket_patch.start()
        self.addCleanup(self.socket_patch.stop)
        self.dns_patch = patch.object(
            self.connection.socket,
            "getaddrinfo",
            return_value=[
                (socket.AF_INET, socket.SOCK_DGRAM, 17, "", ("192.168.1.50", 80))
            ],
        )
        self.dns_patch.start()
        self.addCleanup(self.dns_patch.stop)

    def seal(self, packet):
        packet[0x20:0x22] = bytes(2)
        struct.pack_into("<H", packet, 0x20, (0xBEAF + sum(packet)) & 0xFFFF)
        return bytes(packet)

    def discovery_response(self, devtype=0xAF8B):
        packet = bytearray(0x80)
        struct.pack_into("<H", packet, 0x34, devtype)
        packet[0x3A:0x40] = bytes.fromhex("112233445566")[::-1]
        packet[0x40:0x48] = b"FCBLE GW"
        return self.seal(packet)

    def auth_response(self, error=0, missing_key=False):
        packet = bytearray(0x38)
        packet[:8] = self.connection.MAGIC
        struct.pack_into("<HH", packet, 0x24, 0xAF8B, 0x66)
        struct.pack_into("<H", packet, 0x22, error)
        if not error:
            payload = bytearray(32)
            payload[:4] = (1234).to_bytes(4, "little")
            if not missing_key:
                payload[4:20] = bytes(range(1, 17))
            struct.pack_into("<H", packet, 0x34, self.connection._checksum(payload))
            encryptor = Cipher(
                algorithms.AES(self.connection.INITIAL_KEY),
                modes.CBC(self.connection.INITIAL_IV),
            ).encryptor()
            packet.extend(encryptor.update(bytes(payload)) + encryptor.finalize())
        return self.seal(packet)

    def test_discovers_and_authenticates_hostname(self):
        self.conn.recv.side_effect = [self.discovery_response(), self.auth_response()]
        info = self.connection.test_connection(" rm-max.local ")
        self.assertEqual(info.mac, "112233445566")
        self.assertEqual(info.ip_address, "192.168.1.50")
        self.assertEqual(info.name, "FCBLE GW")
        self.conn.connect.assert_called_once_with(("192.168.1.50", 80))
        packets = [call.args[0] for call in self.conn.send.call_args_list]
        self.assertEqual([packet[0x26] for packet in packets], [0x06, 0x65])
        self.assertEqual(packets[1][0x2A:0x30], bytes.fromhex("665544332211"))
        self.conn.__exit__.assert_called_once()

    def test_rejects_other_device(self):
        self.conn.recv.return_value = self.discovery_response(0x520B)
        with self.assertRaisesRegex(
            self.connection.ConnectionFailure, "unsupported_device"
        ):
            self.connection.test_connection("192.168.1.50")
        self.assertEqual(self.conn.send.call_count, 1)

    def test_rejects_auth_error(self):
        self.conn.recv.side_effect = [
            self.discovery_response(),
            self.auth_response(error=0xFFF9),
        ]
        with self.assertRaisesRegex(self.connection.ConnectionFailure, "auth_failed"):
            self.connection.test_connection("192.168.1.50")

    def test_rejects_missing_session_key(self):
        self.conn.recv.side_effect = [
            self.discovery_response(),
            self.auth_response(missing_key=True),
        ]
        with self.assertRaisesRegex(self.connection.ConnectionFailure, "auth_failed"):
            self.connection.test_connection("192.168.1.50")

    def test_rejects_bad_checksum(self):
        response = bytearray(self.discovery_response())
        response[0] ^= 1
        self.conn.recv.return_value = bytes(response)
        with self.assertRaisesRegex(
            self.connection.ConnectionFailure, "invalid_response"
        ):
            self.connection.test_connection("192.168.1.50")

    def test_rejects_unresolvable_hostname(self):
        self.connection.socket.getaddrinfo.side_effect = socket.gaierror()
        with self.assertRaisesRegex(
            self.connection.ConnectionFailure, "cannot_resolve"
        ):
            self.connection.test_connection("missing.local")

    def test_rejects_urls_and_broadcast(self):
        for host in ("", "http://rm-max", "rm-max:80", "255.255.255.255", "224.0.0.1"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(
                    self.connection.ConnectionFailure, "invalid_host"
                ):
                    self.connection.test_connection(host)
        self.conn.connect.assert_not_called()

    def test_reports_network_failure(self):
        self.conn.connect.side_effect = OSError("unreachable")
        with self.assertRaisesRegex(
            self.connection.ConnectionFailure, "cannot_connect"
        ):
            self.connection.test_connection("192.168.1.50")

    def test_discovery_timeout(self):
        self.conn.recv.side_effect = socket.timeout()
        with patch.object(self.connection.time, "monotonic", side_effect=[0, 0, 0, 11]):
            with self.assertRaisesRegex(
                self.connection.ConnectionFailure, "cannot_connect"
            ):
                self.connection.test_connection("192.168.1.50")

    def test_rejects_truncated_discovery_response(self):
        self.conn.recv.return_value = self.seal(bytearray(0x30))
        with self.assertRaisesRegex(
            self.connection.ConnectionFailure, "invalid_response"
        ):
            self.connection.test_connection("192.168.1.50")


class PackageTests(unittest.TestCase):
    def test_manifest_is_independent(self):
        manifest = json.loads((COMPONENT / "manifest.json").read_text())
        self.assertEqual(manifest["domain"], "broadlink_rm_max")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(manifest["dependencies"], [])
        self.assertEqual(manifest["requirements"], [])
        self.assertEqual(manifest["version"], "0.2.0")
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
            self.assertEqual(
                translated["config"]["error"].keys(), strings["config"]["error"].keys()
            )
            for step in strings["config"]["step"]:
                self.assertEqual(
                    translated["config"]["step"][step]["data"].keys(),
                    strings["config"]["step"][step]["data"].keys(),
                )


if __name__ == "__main__":
    unittest.main()
