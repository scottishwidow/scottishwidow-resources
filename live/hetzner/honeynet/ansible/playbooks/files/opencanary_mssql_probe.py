#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import socket
import struct
import sys

TDS_HEADER_LENGTH = 8
TDS_TYPE_PRELOGIN = 0x12
TDS_TYPE_RESPONSE = 0x04
TDS_TYPE_LOGIN7 = 0x10

TDS_VERSION_7_4 = 0x74000004
LOGIN7_HEADER_LENGTH = 94
ERROR_TOKEN = 0xAA

PRELOGIN_OPTIONS = [
    (0x00, b"\x0b\x00\x00\x00\x00\x00"),  # version 11.0, build 0
    (0x01, b"\x00"),  # encryption off
    (0x02, b"\x00"),  # no named instance
    (0x03, struct.pack("<I", os.getpid())),  # thread id
    (0x04, b"\x00"),  # MARS off
]


class ProbeError(Exception):
    pass


def read_exactly(connection: socket.socket, count: int) -> bytes:
    data = b""
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            raise ProbeError(f"connection closed after {len(data)} of {count} bytes")
        data += chunk
    return data


def build_packet(packet_type: int, payload: bytes) -> bytes:
    header = struct.pack(
        ">BBHHBB", packet_type, 0x01, len(payload) + TDS_HEADER_LENGTH, 0, 1, 0
    )
    return header + payload


def read_packet(connection: socket.socket) -> tuple[int, bytes]:
    header = read_exactly(connection, TDS_HEADER_LENGTH)
    packet_type, _, length = struct.unpack(">BBH", header[:4])
    return packet_type, read_exactly(connection, length - TDS_HEADER_LENGTH)


def build_prelogin() -> bytes:
    data_offset = len(PRELOGIN_OPTIONS) * 5 + 1
    header = b""
    data = b""
    for token, value in PRELOGIN_OPTIONS:
        header += struct.pack(">BHH", token, data_offset + len(data), len(value))
        data += value
    return header + b"\xff" + data


def obfuscate_password(password: str) -> bytes:
    # TDS sends the password with its nibbles swapped and XORed with 0xa5.
    return bytes(
        ((byte << 4) & 0xF0 | byte >> 4) ^ 0xA5
        for byte in password.encode("utf-16-le")
    )


def build_login7(username: str, password: str, hostname: str) -> bytes:
    fields = [
        ("HostName", hostname.encode("utf-16-le")),
        ("UserName", username.encode("utf-16-le")),
        ("Password", obfuscate_password(password)),
        ("AppName", "opencanary-probe".encode("utf-16-le")),
        ("ServerName", b""),
        ("Extension", b""),
        ("CltIntName", "probe".encode("utf-16-le")),
        ("Language", b""),
        ("Database", b""),
    ]

    offsets = []
    data = b""
    for _, value in fields:
        offsets += [LOGIN7_HEADER_LENGTH + len(data), len(value) // 2]
        data += value

    header = struct.pack(
        "< 6I 4B l I 18H 6s 6H I",
        LOGIN7_HEADER_LENGTH + len(data),
        TDS_VERSION_7_4,
        4096,
        7,
        os.getpid(),
        0,
        0x00,  # optFlags1
        0x00,  # optFlags2
        0x00,  # typeFlags
        0x00,  # optFlags3
        0,  # clientTimeZone
        0x0409,  # clientLCID
        *offsets,
        b"\x00" * 6,  # ClientID
        0,  # ibSSPI
        0,  # cbSSPI, zero so that the server reads this as SQL authentication
        0,  # ibAtchDBFile
        0,  # cchAtchDBFile
        0,  # ibChangePassword
        0,  # cchChangePassword
        0,  # cbSSPILong
    )
    return header + data


def parse_error(payload: bytes) -> tuple[int, str]:
    if payload[0] != ERROR_TOKEN:
        raise ProbeError(f"expected an error token, got {payload[0]:#04x}")
    number, _, _, message_length = struct.unpack("<lBBH", payload[3:11])
    message = payload[11 : 11 + message_length * 2].decode("utf-16-le")
    return number, message


def run_probe(arguments: argparse.Namespace) -> dict:
    connection = socket.create_connection(
        (arguments.host, arguments.port), arguments.timeout
    )
    connection.settimeout(arguments.timeout)
    try:
        connection.sendall(build_packet(TDS_TYPE_PRELOGIN, build_prelogin()))
        prelogin_type, prelogin = read_packet(connection)
        if prelogin_type != TDS_TYPE_RESPONSE:
            raise ProbeError(f"unexpected prelogin reply type {prelogin_type:#04x}")

        login = build_login7(
            arguments.username, arguments.password, socket.gethostname()
        )
        connection.sendall(build_packet(TDS_TYPE_LOGIN7, login))
        login_type, reply = read_packet(connection)
        if login_type != TDS_TYPE_RESPONSE:
            raise ProbeError(f"unexpected login reply type {login_type:#04x}")
        error_number, error_message = parse_error(reply)
    finally:
        connection.close()

    return {
        "prelogin": prelogin.hex(),
        "error_number": error_number,
        "error_message": error_message,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=1433)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    arguments = parser.parse_args()

    try:
        result = run_probe(arguments)
    except (ProbeError, OSError, IndexError, ValueError, struct.error) as error:
        print(f"{arguments.host}:{arguments.port}: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
