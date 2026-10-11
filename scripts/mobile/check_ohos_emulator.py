"""Verify completed synthetic OHOS events from the current application process."""

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "sandbox_file",
    "clipboard",
    "https_health",
    "anonymous_rejected",
    "synthetic_headers",
    "untrusted_certificate_rejected",
    "connection_failure_and_recovery",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hdc", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--require-navigation", action="store_true")
    parser.add_argument("--require-lifecycle", action="store_true")
    args = parser.parse_args()
    output = (
        ROOT
        / ".local/mobile-m0b"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-ohos-emulator")
    )
    output.mkdir(parents=True, exist_ok=True)
    commands = []

    def hdc(*parts):
        command = [args.hdc, "-t", args.target, *parts]
        result = subprocess.run(command, capture_output=True, timeout=30, check=False)
        commands.append(
            {"command": ["hdc", "-t", args.target, *parts], "exit_code": result.returncode}
        )
        result.check_returncode()
        return result.stdout.decode("utf8", errors="replace").strip()

    pid = hdc("shell", "pidof", "dev.soloops.soloops_flutter")
    if not pid.isdigit():
        raise RuntimeError("App is not running or PID is ambiguous")
    raw = hdc("shell", "hilog", "-x", "-P", pid)
    markers = (
        "SOLOOPS_M0B ",
        "onUnhandledException",
        "Unhandled Exception",
        "A RenderFlex overflowed",
        "EXCEPTION CAUGHT BY",
    )
    logs = "\n".join(line[:2000] for line in raw.splitlines() if any(m in line for m in markers))
    (output / "app-hilog.txt").write_text(logs, encoding="utf8")
    events = [
        json.loads(line.split("SOLOOPS_M0B ", 1)[1])
        for line in logs.splitlines()
        if "SOLOOPS_M0B " in line
    ]
    completed = [e["value"] for e in events if e["event"] == "completed"]
    if not completed or set(completed[-1]) != EXPECTED:
        raise RuntimeError("No complete set of runtime probe evidence")
    results = {k: "PASS" if v == "PASS" else "FAIL" for k, v in completed[-1].items()}
    if args.require_navigation:
        values = [e["value"] for e in events if e["event"] == "navigation"]
        results["navigation_and_back"] = (
            "PASS" if values[-2:] == ["environment", "startup"] else "FAIL"
        )
    if args.require_lifecycle:
        values = [e["value"] for e in events if e["event"] == "lifecycle"]
        results["background_resume"] = (
            "PASS" if "paused" in values and "resumed" in values else "FAIL"
        )
    results["no_unhandled_exception"] = (
        "FAIL"
        if any(
            p in logs
            for p in [
                "onUnhandledException",
                "Unhandled Exception",
                "A RenderFlex overflowed",
                "EXCEPTION CAUGHT BY",
            ]
        )
        else "PASS"
    )
    report = {
        "at": datetime.now(UTC).isoformat(),
        "hap_sha256": hashlib.sha256(
            (
                ROOT
                / "apps/soloops_flutter/ohos/entry/build/default/outputs/default"
                / "entry-default-unsigned.hap"
            ).read_bytes()
        ).hexdigest(),
        "device_api": hdc("shell", "param", "get", "const.ohos.apiversion"),
        "pid": pid,
        "events": events,
        "results": results,
        "commands": commands,
    }
    (output / "results.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf8"
    )
    print(json.dumps(results, indent=2))
    return 0 if all(v == "PASS" for v in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
