# Broadlink RM Max

An independently installable Home Assistant custom integration. Version 0.1.0
provides installation and configuration only. It creates no devices, entities,
services, network connections, or Broadlink commands.

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
5. Search for **Broadlink RM Max** and confirm installation.

The configuration flow requires no credentials, host, or device. Only one entry
is allowed. No entities or devices should appear after installation.

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

Run `python -m unittest discover -s tests -v` and
`python -m compileall -q custom_components tests` using Python 3.13 or newer.
The tests use a minimal Home Assistant API substitute and cover the installation
flow, duplicate prevention, setup/unload, metadata, and dependency isolation.
They are not a substitute for installation testing in a running Home Assistant.
GitHub Actions additionally runs Home Assistant's hassfest validator.

After installation in an existing Home Assistant, verify that adding, restarting,
and removing the integration succeeds, that a second entry is refused, and that
the existing Broadlink integration continues to work unchanged.