# Hostcheck

A small, read-only Linux resource checker with human-readable output, JSON output, and documented exit codes. Built as an AI-assisted infrastructure portfolio project, not claimed as deployed production experience.

## Problem

During a first-pass triage, an administrator needs to distinguish a resource warning from missing telemetry. A command that reports success when it cannot read a metric is misleading. Hostcheck checks memory, filesystem space, and inode usage without root, installing an agent, or changing the host.

## Quick start

Requires **Linux and Python 3.9+**. No third-party packages or installation step.

```sh
python3 hostcheck.py
python3 hostcheck.py --path /var --warning 75 --critical 90
python3 hostcheck.py --json
```

Only the filesystem containing `--path` is checked. Pass a path that exists on the filesystem you want to inspect. It does not walk directories or automatically enumerate remote mounts.

### Example output

Illustrative values, not a claim about any employer or production system:

```text
Hostcheck | read-only Linux resource snapshot
OK       memory_used          42.00%
WARNING  filesystem_used      84.00%
OK       inodes_used          18.00%
Exit: 1
```

The versioned JSON format includes the observation timestamp, metric values, thresholds and status. See [examples/report.json](examples/report.json).

## What is measured

| Metric | Calculation | Important limitation |
|---|---|---|
| Memory used | `(MemTotal - MemAvailable) / MemTotal` from `/proc/meminfo` | Not merely “free” RAM. Does not attribute usage to applications. |
| Filesystem used | used blocks / (used blocks + unprivileged available blocks) | Includes reserved-block effects; not a direct substitute for every `df` option. |
| Inodes used | `(f_files - f_ffree) / f_files` | Unknown if the filesystem does not expose inode capacity. |

Thresholds default to warning **80%**, critical **90%**, and must satisfy `0 < warning < critical <= 100`. Comparison uses the raw measurement; display rounds to two decimal places. A value displayed as `80.00%` can be just below the warning threshold.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | All checks are OK |
| 1 | At least one warning, no critical or unknown check |
| 2 | At least one critical check **or invalid CLI arguments** (argparse convention) |
| 3 | At least one check is unknown, with no known critical check |

If a known critical and unknown metric coexist, exit 2 takes precedence. Inspect JSON for per-check details. Unsupported platforms return unknown rather than pretending to pass.

Example integration:

```sh
python3 hostcheck.py --json > report.json
status=$?
printf 'Hostcheck exit code: %s\n' "$status"
```

The redirect above writes a report because **you explicitly requested it in the shell**. Hostcheck itself prints only to stdout and reads local counters.

## Safety and privacy

- No network traffic, shell execution, subprocesses, package installation, remediation, or privilege escalation.
- Does not collect hostnames, usernames, IP addresses, process lists, environment variables, file contents, or credentials.
- Reads `/proc/meminfo` and filesystem metadata through `statvfs`.
- Reports may still reveal capacity utilization and timestamps; review them before sharing.
- A filesystem metadata call can block on an unhealthy/remote filesystem. There is no internal timeout. For such paths, use a suitable external timeout (for example GNU `timeout 5s python3 hostcheck.py --path /mount`) and treat timeout exit 124 separately.
- In containers, `/proc/meminfo` may describe the host while cgroups enforce a smaller memory limit. **Not cgroup-aware**; do not use this as container memory-limit monitoring.

## Testing

```sh
python3 -m unittest discover -s tests -v
python3 -m py_compile hostcheck.py
```

15 tests cover boundary thresholds, reserved blocks, malformed/missing telemetry, inode-less filesystems, exit-code precedence, JSON output, unsupported platforms, and invalid input. A live smoke test was run in a Linux cloud workspace; this is **not** RHEL, Azure, fleet, or production validation. CI is supplied for Python 3.9 and 3.12 on Ubuntu, but has not run remotely while this is an unpublished draft.

## Design choices and scope

The checker stays deliberately small and dependency-free. Missing telemetry is visible, collection is separate from formatting, and calculations can be tested without needing to fill a real disk. It is a snapshot, not an alerting platform, performance diagnosis, security audit, or uptime guarantee. It cannot prove a machine is healthy.

Potential next steps: cgroup-aware memory checks, selected systemd service checks with timeouts, and configuration-file support. These are not implemented.

## Review before publication

This draft was generated and tested with AI assistance. Review the code, run it in your own Linux lab, and be prepared to explain its calculations and limitations. Do not describe it as used at an employer unless that genuinely occurs with permission. No employer source code or data is included.
