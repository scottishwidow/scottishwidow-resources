#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import time

IAC = 255
SE = 240
SB = 250
WILL = 251
WONT = 252
DO = 253
DONT = 254

PROMPT = re.compile(r"[$#]\s*$")


class ProbeError(Exception):
    pass


class TelnetClient:

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.socket = socket.create_connection((host, port), timeout)
        self.socket.settimeout(timeout)
        self.timeout = timeout
        self.negotiation = bytearray()
        self.buffer = bytearray()
        self.text = ""

    def close(self) -> None:
        self.socket.close()

    def send_line(self, line: str) -> None:
        self.socket.sendall(line.encode() + b"\r\n")

    def read_until(self, matches, deadline: float) -> str:
        while not matches(self.text):
            if time.monotonic() > deadline:
                raise ProbeError(f"timeout, last read: {self.text[-200:]!r}")
            try:
                data = self.socket.recv(4096)
            except TimeoutError:
                continue
            if not data:
                raise ProbeError(f"connection closed, last read: {self.text[-200:]!r}")
            self.text += self._strip_commands(data)
        return self.text

    def _strip_commands(self, data: bytes) -> str:
        self.buffer.extend(data)
        plain = bytearray()
        answer = bytearray()

        while self.buffer:
            byte = self.buffer[0]
            if byte != IAC:
                plain.append(self.buffer.pop(0))
                continue
            if len(self.buffer) < 2:
                break
            command = self.buffer[1]
            if command in (DO, DONT, WILL, WONT):
                if len(self.buffer) < 3:
                    break
                option = self.buffer[2]
                self.negotiation.extend(self.buffer[:3])
                del self.buffer[:3]
                if command == DO:
                    answer.extend(bytes([IAC, WONT, option]))
                elif command == WILL:
                    answer.extend(bytes([IAC, DONT, option]))
            elif command == SB:
                end = self.buffer.find(bytes([IAC, SE]))
                if end == -1:
                    break
                self.negotiation.extend(self.buffer[: end + 2])
                del self.buffer[: end + 2]
            else:
                self.negotiation.extend(self.buffer[:2])
                del self.buffer[:2]

        if answer:
            self.socket.sendall(bytes(answer))
        return plain.decode("utf-8", "replace")


def run_probe(arguments: argparse.Namespace) -> dict:
    client = TelnetClient(arguments.host, arguments.port, arguments.timeout)
    deadline = time.monotonic() + arguments.timeout
    try:
        client.read_until(lambda text: "login:" in text.lower(), deadline)
        client.send_line(arguments.username)
        client.read_until(lambda text: "password:" in text.lower(), deadline)
        client.send_line(arguments.password)
        client.read_until(lambda text: PROMPT.search(text) is not None, deadline)
        before = len(client.text)
        client.send_line(arguments.command)
        command_deadline = time.monotonic() + arguments.timeout
        try:
            client.read_until(
                lambda text: PROMPT.search(text[before:]) is not None,
                command_deadline,
            )
            command_completed = True
        except ProbeError:
            command_completed = False
        output = client.text[before:]
        client.send_line("exit")
    finally:
        client.close()

    return {
        "negotiation": client.negotiation.hex(),
        "logged_in": True,
        "command_completed": command_completed,
        "command_output": output,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--port", type=int, default=23)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    arguments = parser.parse_args()

    try:
        result = run_probe(arguments)
    except (ProbeError, OSError) as error:
        print(f"{arguments.host}:{arguments.port}: {error}", file=sys.stderr)
        return 1

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
