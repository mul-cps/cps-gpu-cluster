"""Render the gateway relay using verified IPv4 backends."""

import argparse
from ipaddress import IPv4Address
from pathlib import Path


def endpoint(value):
    address, separator, port = value.partition(":")
    if not separator or not port.isascii() or not port.isdecimal() or not 0 < int(port) <= 65535:
        raise argparse.ArgumentTypeError("Expected an IPv4 address and a valid TCP port")
    try:
        return f"{IPv4Address(address)}:{int(port)}"
    except ValueError as error:
        raise argparse.ArgumentTypeError("Expected an IPv4 address") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for backend in ("incumbent", "candidate", "capture"):
        parser.add_argument(f"--{backend}", type=endpoint, required=True)
    args = parser.parse_args()
    backends = vars(args)
    if len(set(backends.values())) != len(backends):
        parser.error("Each relay backend must have a distinct endpoint")

    configuration = Path(__file__).with_name("haproxy.cfg.in").read_text()
    for backend, target in backends.items():
        marker = f"@{backend.upper()}@"
        if configuration.count(marker) != 1:
            raise ValueError(f"Expected one {backend} endpoint in the configuration")
        configuration = configuration.replace(marker, target)
    print(configuration, end="")


if __name__ == "__main__":
    main()
