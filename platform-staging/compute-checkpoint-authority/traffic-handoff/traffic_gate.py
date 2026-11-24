"""Control the temporary gateway relay through its private HAProxy socket."""

import csv
import io
import socket

SOCKET_PATH = "/run/handoff/runtime.sock"
MAP_PATH = "/handoff-config/writer.map"
WRITERS = {"incumbent", "candidate"}


class TrafficGate:
    def __init__(self, path=SOCKET_PATH):
        self.path = path

    def _command(self, command):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(0.5)
            connection.connect(self.path)
            connection.sendall((command + "\n").encode())
            connection.shutdown(socket.SHUT_WR)
            response = bytearray()
            while chunk := connection.recv(16384):
                response.extend(chunk)
                if len(response) > 262144:
                    raise ValueError("Unexpected relay control response size")
        return response.decode().strip()

    def route(self):
        response = self._command(f"show map {MAP_PATH}")
        fields = response.split()
        if len(fields) != 3 or fields[1] != "active" or fields[2] not in WRITERS | {"hold"}:
            raise ValueError("Unexpected relay route map")
        return fields[2]

    def select(self, route):
        if route not in WRITERS | {"hold"}:
            raise ValueError("Unknown gateway relay route")
        response = self._command(f"set map {MAP_PATH} active {route}")
        if response or self.route() != route:
            raise ValueError("Gateway relay route change was not confirmed")

    def in_flight(self, writer):
        if writer not in WRITERS:
            raise ValueError("Unknown gateway writer")
        response = self._command("show stat").removeprefix("# ")
        rows = csv.DictReader(io.StringIO(response))
        current = [
            row for row in rows
            if row["pxname"] == f"gateway_{writer}" and row["svname"] == "BACKEND"
        ]
        if len(current) != 1:
            raise ValueError("Expected exactly one gateway backend in relay stats")
        return int(current[0]["scur"]) + int(current[0]["qcur"])
