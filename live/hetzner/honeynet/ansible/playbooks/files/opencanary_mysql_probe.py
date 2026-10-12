#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import struct
import sys

CLIENT_CAPABILITIES = 0x00088205
MAX_PACKET_SIZE = 16777216
CHARSET_UTF8 = 0x21


class ProbeError(Exception):
    pass


def read_packet(connection: socket.socket) -> tuple[int, bytes]:
    header = read_exactly(connection, 4)
    length = struct.unpack("<I", header[:3] + b"\x00")[0]
    return header[3], read_exactly(connection, length)


def read_exactly(connection: socket.socket, count: int) -> bytes:
    data = b""
    while len(data) < count:
        chunk = connection.recv(count - len(data))
        if not chunk:
            raise ProbeError(f"connection closed after {len(data)} of {count} bytes")
        data += chunk
    return data


def build_packet(sequence_id: int, payload: bytes) -> bytes:
    return struct.pack("<I", len(payload))[:3] + bytes([sequence_id]) + payload


def parse_greeting(payload: bytes) -> tuple[str, bytes]:
    if payload[0] != 0x0A:
        raise ProbeError(f"unexpected protocol version {payload[0]}")
    end_of_banner = payload.index(b"\x00", 1)
    banner = payload[1:end_of_banner].decode("utf-8", "replace")

    # Protocol::Handshake, from the banner onwards: 4 bytes thread id, the
    # first 8 salt bytes, 8 bytes of filler, capabilities, charset and status,
    # the salt length, 10 reserved bytes, then the rest of the salt. The salt
    # length counts a trailing NUL that is not part of the salt.
    salt_offset = end_of_banner + 1 + 4
    first_salt = payload[salt_offset : salt_offset + 8]
    salt_length = payload[salt_offset + 16]
    second_salt_offset = salt_offset + 27
    second_salt = payload[second_salt_offset : second_salt_offset + salt_length - 9]
    return banner, first_salt + second_salt


def scramble(password: str, salt: bytes) -> bytes:
    stage1 = hashlib.sha1(password.encode()).digest()
    token = hashlib.sha1(salt + hashlib.sha1(stage1).digest()).digest()
    return bytes(left ^ right for left, right in zip(stage1, token))


def build_handshake_response(username: str, auth_response: bytes) -> bytes:
    return (
        struct.pack("<IIB", CLIENT_CAPABILITIES, MAX_PACKET_SIZE, CHARSET_UTF8)
        + b"\x00" * 23
        + username.encode()
        + b"\x00"
        + bytes([len(auth_response)])
        + auth_response
        + b"mysql_native_password\x00"
    )


def parse_error(payload: bytes) -> tuple[int, str]:
    if payload[0] != 0xFF:
        raise ProbeError(f"expected an error packet, got type {payload[0]:#04x}")
    error_code = struct.unpack("<H", payload[1:3])[0]
    message = payload[3:]
    if message.startswith(b"#"):
        message = message[6:]
    return error_code, message.decode("utf-8", "replace")


def run_probe(arguments: argparse.Namespace) -> dict:
    connection = socket.create_connection(
        (arguments.host, arguments.port), arguments.timeout
    )
    connection.settimeout(arguments.timeout)
    try:
        _, greeting = read_packet(connection)
        banner, salt = parse_greeting(greeting)
        response = build_handshake_response(
            arguments.username, scramble(arguments.password, salt)
        )
        connection.sendall(build_packet(1, response))
        _, reply = read_packet(connection)
        error_code, error_message = parse_error(reply)
    finally:
        connection.close()

    return {
        "banner": banner,
        "error_code": error_code,
        "error_message": error_message,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=3306)
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
