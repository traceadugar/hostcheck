#!/usr/bin/env python3
"""Read-only Linux resource snapshot. No network, subprocesses, or remediation."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys

VERSION = "0.1.0"


def percent_status(value, warning, critical):
    if value >= critical:
        return "critical"
    if value >= warning:
        return "warning"
    return "ok"


def memory_percent(text):
    fields = {}
    for line in text.splitlines():
        key, _, tail = line.partition(":")
        if key in ("MemTotal", "MemAvailable"):
            fields[key] = int(tail.strip().split()[0])
    total, available = fields["MemTotal"], fields["MemAvailable"]
    if total <= 0 or not 0 <= available <= total:
        raise ValueError("Invalid memory counters")
    return 100 * (total - available) / total


def filesystem_percent(stats):
    # df-style usage: reserved blocks are excluded from unprivileged availability.
    used = stats.f_blocks - stats.f_bfree
    denominator = used + stats.f_bavail
    if denominator <= 0 or used < 0 or stats.f_bavail < 0:
        raise ValueError("Invalid filesystem counters")
    disk = 100 * used / denominator
    if stats.f_files <= 0:
        inode = None
    else:
        if not 0 <= stats.f_ffree <= stats.f_files:
            raise ValueError("Invalid inode counters")
        inode = 100 * (stats.f_files - stats.f_ffree) / stats.f_files
    return disk, inode


def metric(name, value, warning, critical, unit="percent"):
    if not math.isfinite(value) or value < 0:
        raise ValueError("Invalid metric")
    return {"name": name, "status": percent_status(value, warning, critical),
            "value": round(value, 2), "unit": unit,
            "warning": warning, "critical": critical}


def unavailable(name, reason):
    return {"name": name, "status": "unknown", "reason": reason}


def collect(path, warning, critical):
    checks = []
    try:
        checks.append(metric("memory_used", memory_percent(Path("/proc/meminfo").read_text()), warning, critical))
    except (OSError, ValueError, KeyError, IndexError):
        checks.append(unavailable("memory_used", "Linux MemTotal/MemAvailable counters unavailable or invalid"))
    try:
        disk, inode = filesystem_percent(os.statvfs(path))
        checks.append(metric("filesystem_used", disk, warning, critical))
        checks.append(metric("inodes_used", inode, warning, critical) if inode is not None
                      else unavailable("inodes_used", "Filesystem does not expose inode capacity"))
    except (OSError, ValueError):
        checks.extend([unavailable("filesystem_used", "Filesystem counters unavailable or invalid"),
                       unavailable("inodes_used", "Filesystem counters unavailable or invalid")])
    return checks


def exit_code(checks):
    states = {c["status"] for c in checks}
    # Known critical issues take priority over incomplete telemetry.
    if "critical" in states:
        return 2
    if "unknown" in states:
        return 3
    return 1 if "warning" in states else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", default="/", help="Filesystem path to inspect (default /)")
    parser.add_argument("--warning", type=float, default=80)
    parser.add_argument("--critical", type=float, default=90)
    parser.add_argument("--json", action="store_true", help="Print structured JSON")
    args = parser.parse_args(argv)
    if not (0 < args.warning < args.critical <= 100):
        parser.error("thresholds must satisfy 0 < warning < critical <= 100")
    if sys.platform != "linux":
        checks = [unavailable("platform", "This tool supports Linux only")]
    else:
        checks = collect(args.path, args.warning, args.critical)
    result = {"schema_version": 1, "tool_version": VERSION,
              "observed_at": datetime.now(timezone.utc).isoformat(), "checks": checks,
              "exit_code": exit_code(checks)}
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        print("Hostcheck | read-only Linux resource snapshot")
        for check in checks:
            detail = f'{check["value"]:.2f}%' if "value" in check else check["reason"]
            print(f'{check["status"].upper():8} {check["name"]:20} {detail}')
        print(f'Exit: {result["exit_code"]}')
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
