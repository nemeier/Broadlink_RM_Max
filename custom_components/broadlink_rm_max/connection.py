"""Test local RM Max connectivity without the Broadlink integration."""

from dataclasses import dataclass
from datetime import datetime
import ipaddress
import secrets
import socket
from socket import socket as udp_socket
import struct
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PORT = 80
TIMEOUT = 10.0
DEVICE_TYPE = 0xAF8B
INITIAL_KEY = bytes.fromhex("097628343fe99e23765c1513accf8b02")
INITIAL_IV = bytes.fromhex("562e17996d093d28ddb3ba695a2e6f58")
MAGIC = bytes.fromhex("5aa5aa555aa5aa55")


class ConnectionFailure(Exception):
    """Expose a safe, translatable connection error."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class DeviceInfo:
    """Non-secret identity returned by discovery."""

    ip_address: str
    mac: str
    devtype: int
    name: str


def _checksum(packet: bytes | bytearray) -> int:
    return (0xBEAF + sum(packet)) & 0xFFFF


def _validate_checksum(packet: bytes) -> None:
    if len(packet) < 0x24:
        raise ConnectionFailure("invalid_response")
    expected = int.from_bytes(packet[0x20:0x22], "little")
    actual = (_checksum(packet) - sum(packet[0x20:0x22])) & 0xFFFF
    if expected != actual:
        raise ConnectionFailure("invalid_response")


def _exchange(conn: socket.socket, packet: bytes | bytearray) -> bytes:
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        conn.settimeout(min(1.0, max(0.001, deadline - time.monotonic())))
        conn.send(packet)
        try:
            return conn.recv(2048)
        except socket.timeout:
            continue
    raise ConnectionFailure("cannot_connect")


def _discover(conn: socket.socket, ip_address: str) -> DeviceInfo:
    local_ip, local_port = conn.getsockname()
    now = datetime.now().astimezone()
    packet = bytearray(0x30)
    struct.pack_into(
        "<iH", packet, 0x08, int(now.utcoffset().total_seconds() / 3600), now.year
    )
    packet[0x0E:0x14] = bytes(
        (now.second, now.minute, now.hour, now.isoweekday(), now.day, now.month)
    )
    packet[0x18:0x1C] = socket.inet_aton(local_ip)[::-1]
    struct.pack_into("<H", packet, 0x1C, local_port)
    packet[0x26] = 0x06
    struct.pack_into("<H", packet, 0x20, _checksum(packet))
    response = _exchange(conn, packet)
    _validate_checksum(response)
    if len(response) < 0x40:
        raise ConnectionFailure("invalid_response")
    devtype = int.from_bytes(response[0x34:0x36], "little")
    if devtype != DEVICE_TYPE:
        raise ConnectionFailure("unsupported_device")
    mac = response[0x3A:0x40][::-1]
    if mac in (bytes(6), bytes([0xFF]) * 6):
        raise ConnectionFailure("invalid_response")
    name = response[0x40:0x7F].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    return DeviceInfo(ip_address, mac.hex(), devtype, name)


def _authenticate(conn: socket.socket, device: DeviceInfo) -> None:
    payload = bytearray(0x50)
    payload[0x04:0x14] = b"1" * 16
    payload[0x1E] = 1
    payload[0x2D] = 1
    payload[0x30:0x36] = b"Test 1"
    cipher = Cipher(algorithms.AES(INITIAL_KEY), modes.CBC(INITIAL_IV))
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(bytes(payload)) + encryptor.finalize()
    packet = bytearray(0x38)
    packet[:8] = MAGIC
    struct.pack_into(
        "<HHH", packet, 0x24, device.devtype, 0x65, secrets.randbelow(0x8000) + 0x8000
    )
    packet[0x2A:0x30] = bytes.fromhex(device.mac)[::-1]
    struct.pack_into("<H", packet, 0x34, _checksum(payload))
    packet.extend(encrypted)
    struct.pack_into("<H", packet, 0x20, _checksum(packet))
    response = _exchange(conn, packet)
    _validate_checksum(response)
    if int.from_bytes(response[0x22:0x24], "little") != 0:
        raise ConnectionFailure("auth_failed")
    if (
        len(response) < 0x58
        or response[:8] != MAGIC
        or int.from_bytes(response[0x26:0x28], "little") != 0x66
        or (len(response) - 0x38) % 16
    ):
        raise ConnectionFailure("invalid_response")
    decryptor = cipher.decryptor()
    decoded = decryptor.update(response[0x38:]) + decryptor.finalize()
    if int.from_bytes(response[0x34:0x36], "little") != _checksum(decoded):
        raise ConnectionFailure("invalid_response")
    if decoded[:4] == bytes(4) or decoded[4:20] == bytes(16):
        raise ConnectionFailure("auth_failed")


def test_connection(host: str) -> DeviceInfo:
    """Resolve, discover and authenticate; never send an IR/RF command."""
    host = host.strip()
    if (
        not host
        or any(character.isspace() for character in host)
        or any(character in host for character in "/:@")
    ):
        raise ConnectionFailure("invalid_host")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and (
        literal.version != 4
        or literal.is_unspecified
        or literal.is_multicast
        or str(literal) == "255.255.255.255"
    ):
        raise ConnectionFailure("invalid_host")
    try:
        addresses = socket.getaddrinfo(host, PORT, socket.AF_INET, socket.SOCK_DGRAM)
    except socket.gaierror as err:
        raise ConnectionFailure("cannot_resolve") from err
    for _, _, _, _, address in addresses:
        ip_address = address[0]
        resolved = ipaddress.IPv4Address(ip_address)
        if (
            resolved.is_unspecified
            or resolved.is_multicast
            or ip_address == "255.255.255.255"
        ):
            raise ConnectionFailure("invalid_host")
        try:
            with udp_socket(socket.AF_INET, socket.SOCK_DGRAM) as conn:
                conn.connect((ip_address, PORT))
                device = _discover(conn, ip_address)
                _authenticate(conn, device)
                return device
        except OSError:
            continue
        except ConnectionFailure as err:
            if err.reason != "cannot_connect":
                raise
    raise ConnectionFailure("cannot_connect")
