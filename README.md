# Broadlink RM Max

An independently installable Home Assistant custom integration. Version 0.2.1
accepts an IP address or hostname, tests local discovery and authentication, and
registers the verified RM Max as a device. It provides no entities, services,
IR/RF commands, Bluetooth control, or periodic polling.

The integration uses the domain `broadlink_rm_max`. It does not import, depend on,
modify, or replace Home Assistant's built-in `broadlink` integration or the
Broadlink Python package. Both integrations can be installed together.

## Manual installation

1. Download this repository from GitHub.
2. Copy `custom_components/broadlink_rm_max` into your existing Home Assistant
   configuration directory, resulting in
   `<config>/custom_components/broadlink_rm_max/manifest.json`.
   For Home Assistant OS, the configuration directory is normally `/config`.
3. Restart Home Assistant.
4. Open **Settings > Devices & services > Add integration**.
5. Search for **Broadlink RM Max**, enter its IPv4 address or hostname, and submit.

The RM Max must already be connected to Wi-Fi through the manufacturer's app.
Only its IP address or hostname is required; MAC address and device type are
discovered automatically. No Wi-Fi password or Broadlink account is requested.
Home Assistant must be able to resolve the hostname and exchange UDP traffic on
port 80 with the device. A DHCP reservation is recommended.

The entry is saved only after discovery identifies an RM Max (`0xAF8B`) and
authentication returns a valid session ID and AES key. Session credentials are
not persisted or logged. The connection is checked again when the entry loads,
including after a restart or reload. Temporary network failures trigger Home
Assistant's setup retry mechanism. Only one entry is allowed, and no entities
should appear after installation.

## Upgrade from version 0.1.0

Replace the integration folder with the current version and restart Home Assistant.
The old, empty entry cannot establish a connection until an address is entered.
In **Settings > Devices & services**, open the existing Broadlink RM Max entry's
menu and select **Reconfigure**, then enter the address. The connection is tested
before the existing entry is updated and reloaded.

Use **Reconfigure** again if the address changes. A configured entry cannot be
reassigned to a different MAC address; remove and recreate it to replace hardware.

## Connection failures and RM Max compatibility

The form distinguishes invalid addresses, DNS failures, network timeouts,
unsupported device types, rejected authentication, and invalid protocol replies.
Discovery alone does not prove authenticated communication.

Version 0.2.1 records connection-test failures as warnings in the Home Assistant
log under `custom_components.broadlink_rm_max.config_flow`. Authentication
diagnostics include the stage, device error code (hexadecimal and signed decimal),
and response length. Raw packets, session IDs, and AES keys are never logged.
For example, `device_error=0xffff (-1); response_length=56` means the device
returned an authentication error without a session payload. It does not establish
that the device is locked or that an app unlock setting exists.

RM Max authentication is not universally confirmed. Community reports include
both successful local control and rejected authentication on firmware V62130.
This integration tests the known local Broadlink handshake; it does not bypass
device locks, change firmware, or guarantee compatibility with every RM Max.
No IR/RF commands are sent during the connection test.

When reporting an authentication failure, include the warning plus firmware,
SDK version, and PID from the manufacturer's app. Do not include passwords,
tokens, or session keys. Version 0.2.1 improves diagnostics, not authentication
compatibility.

Protocol references:

- [Known local protocol](https://github.com/mjg59/python-broadlink/blob/master/protocol.md)
- [RM Max support and conflicting authentication reports](https://github.com/mjg59/python-broadlink/pull/838)

## HACS installation

This repository has the standard HACS integration layout. For a public repository:

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/nemeier/Broadlink_RM_Max` with category **Integration**.
3. Download **Broadlink RM Max** and restart Home Assistant.
4. Add the integration using **Settings > Devices & services**.

A private repository requires suitable GitHub access and may not be accessible
through HACS. Manual installation works with an authenticated repository download.
This project is not included in HACS's default catalog.

## Removal

Delete the entry in **Settings > Devices & services**. Then remove
`custom_components/broadlink_rm_max` (or uninstall through HACS) and restart
Home Assistant. The built-in Broadlink integration is unaffected.

## Development and validation

Home Assistant already provides `cryptography` and `voluptuous`. For standalone
tests, install them with `python -m pip install cryptography voluptuous`.
Run `python -m unittest discover -s tests -v` and
`python -m compileall -q custom_components tests` using Python 3.13 or newer.
The tests use a minimal Home Assistant API substitute and simulated UDP replies.
They cover discovery/authentication, connection failures, configuration and
reconfiguration, duplicate prevention, setup/unload, and dependency isolation.
They are not a substitute for testing against a physical RM Max in Home Assistant.
GitHub Actions additionally runs Home Assistant's hassfest validator.

After installation in an existing Home Assistant, verify that adding, restarting,
reconfiguring and removing the integration succeeds, that unreachable addresses
and failed authentication cannot create an entry, that a second entry is refused,
and that the existing Broadlink integration continues to work unchanged.