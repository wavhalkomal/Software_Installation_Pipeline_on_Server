#!/usr/bin/env python3
"""Collect an auditable snapshot of a Linux server's RPM inventory."""

from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def run_command(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"success": False, "output": "", "error": str(error)}

    return {
        "success": result.returncode == 0,
        "output": result.stdout.strip(),
        "error": result.stderr.strip() if result.returncode else "",
    }


def read_operating_system(path: Path = Path("/etc/os-release")) -> dict[str, str]:
    if not path.exists():
        return {"name": platform.system(), "id": "unknown", "version": platform.release()}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')

    return {
        "name": values.get("PRETTY_NAME", "Unknown"),
        "id": values.get("ID", "unknown"),
        "version": values.get("VERSION_ID", "unknown"),
    }


def collect_installed_packages() -> dict[str, Any]:
    result = run_command(
        ["rpm", "-qa", "--queryformat", "%{NAME}|%{VERSION}-%{RELEASE}|%{ARCH}\\n"]
    )
    if not result["success"]:
        return {"packages": [], "error": result["error"]}

    packages = []
    for line in result["output"].splitlines():
        parts = line.split("|")
        if len(parts) == 3:
            packages.append({"name": parts[0], "version": parts[1], "architecture": parts[2]})
    return {"packages": sorted(packages, key=lambda item: item["name"]), "error": ""}


def collect_enabled_repositories() -> dict[str, Any]:
    result = run_command(["dnf", "repolist", "--enabled", "-q"])
    if not result["success"]:
        return {"repositories": [], "error": result["error"]}

    repositories = []
    for line in result["output"].splitlines():
        line = line.strip()
        if line and not line.lower().startswith("repo id"):
            repositories.append(line.split()[0])
    return {"repositories": sorted(set(repositories)), "error": ""}


def collect_inventory() -> dict[str, Any]:
    packages = collect_installed_packages()
    repositories = collect_enabled_repositories()
    return {
        "schema_version": "1.0",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "operating_system": read_operating_system(),
        "architecture": platform.machine(),
        "kernel_version": platform.release(),
        "installed_package_count": len(packages["packages"]),
        "installed_packages": packages["packages"],
        "enabled_repositories": repositories["repositories"],
        "collection_errors": {
            "packages": packages["error"],
            "repositories": repositories["error"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="/var/lib/linux-inventory-agent/inventory.json",
        help="Destination JSON file",
    )
    parser.add_argument("--stdout", action="store_true", help="Print JSON instead of saving it")
    arguments = parser.parse_args()

    inventory = collect_inventory()
    if arguments.stdout:
        print(json.dumps(inventory, indent=2))
        return

    output = Path(arguments.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    print(f"Inventory written to {output}")


if __name__ == "__main__":
    main()

