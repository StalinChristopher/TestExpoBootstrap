#!/usr/bin/env python3
"""Pick the first available iPhone Simulator from simctl JSON.

Default: print an xcodebuild -destination string (platform + name + OS), which
avoids brittle id=... UDIDs that differ per machine or Xcode install.

With --udid: print only the UDID (for simctl boot or legacy scripts).
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys


def runtime_version_tuple(runtime_key: str) -> tuple[int, ...]:
    m = re.search(r"\.SimRuntime\.iOS-(\d+)-(\d+)(?:-(\d+))?$", runtime_key)
    if not m:
        return (0, 0)
    parts = [int(m.group(1)), int(m.group(2))]
    if m.group(3) is not None:
        parts.append(int(m.group(3)))
    return tuple(parts)



def first_iphone_sim(data: dict) -> tuple[str, str, str] | None:
    """Return (runtime_key, udid, name) for newest iOS runtime, first iPhone."""
    devices_by_runtime = data.get("devices", {})
    ios_runtimes = [
        rk
        for rk in devices_by_runtime
        if ".SimRuntime.iOS-" in rk and "iOS" in rk
    ]
    ios_runtimes.sort(key=runtime_version_tuple, reverse=True)

    for rk in ios_runtimes:
        for d in devices_by_runtime[rk]:
            if d.get("isAvailable") and "iPhone" in d.get("name", ""):
                return rk, d["udid"], d["name"]
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--udid",
        action="store_true",
        help="Print only the device UDID instead of an xcodebuild destination string.",
    )
    args = parser.parse_args()

    out = subprocess.check_output(
        ["xcrun", "simctl", "list", "devices", "available", "-j"],
        text=True,
    )
    data = json.loads(out)
    picked = first_iphone_sim(data)
    if picked is None:
        sys.stderr.write("No available iPhone simulator found\n")
        sys.exit(1)

    rk, udid, name = picked
    if args.udid:
        print(udid)
        return

    # Include arch so xcodebuild never warns about multiple matching destinations
    # (arm64 and x86_64 share the same UDID on Apple-silicon runners).
    arch = "arm64" if platform.machine() == "arm64" else "x86_64"

    # Use OS=latest rather than the literal version from the simctl runtime key.
    # simctl may report newer runtimes (e.g. 26.5) installed by a different Xcode
    # version on the runner, while the active Xcode only supports an earlier SDK
    # (e.g. 26.1). Pinning the OS version causes xcodebuild to fail with
    # "Unable to find a destination matching... OS:<newer>".
    # OS=latest tells xcodebuild to use the newest runtime the active Xcode supports.
    print(f"platform=iOS Simulator,name={name},OS=latest,arch={arch}")


if __name__ == "__main__":
    main()
