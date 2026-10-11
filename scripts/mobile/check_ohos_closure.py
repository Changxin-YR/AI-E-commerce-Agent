"""Record synthetic OHOS debug probe actions with fresh, isolated evidence."""

import argparse
import hashlib
import json
import re
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = "dev.soloops.soloops_flutter"
HAP = (
    ROOT
    / "apps/soloops_flutter/ohos/entry/build/default/outputs/default/entry-default-unsigned.hap"
)


class Session:
    def __init__(self, hdc, target, directory):
        self.hdc, self.target = hdc, target
        self.directory = directory.resolve()
        self.directory.relative_to((ROOT / ".local/mobile-m0b").resolve())
        self.directory.mkdir(parents=True, exist_ok=True)
        self.timeline = self.directory / "actions.json"
        self.actions = json.loads(self.timeline.read_text()) if self.timeline.exists() else []

    def run(self, *parts):
        result = subprocess.run(
            [self.hdc, "-t", self.target, *parts], capture_output=True, timeout=40, check=False
        )
        self.actions.append(
            {
                "at": datetime.now(UTC).isoformat(),
                "command": ["hdc", "-t", self.target, *parts],
                "exit_code": result.returncode,
            }
        )
        self.timeline.write_text(json.dumps(self.actions, indent=2), encoding="utf8")
        result.check_returncode()
        output = result.stdout.decode("utf8", errors="replace").strip()
        if "[Fail]" in output or "[Error]" in output:
            raise RuntimeError(output[:300])
        return output

    def snapshot(self, emit=True):
        stamp = datetime.now(UTC).strftime("%H%M%S%f")
        layout = self.directory / f"{stamp}-layout.json"
        screen = self.directory / f"{stamp}-screen.png"
        self.run("shell", "uitest", "dumpLayout", "-p", "/data/local/tmp/soloops-m0-layout.json")
        self.run("file", "recv", "/data/local/tmp/soloops-m0-layout.json", str(layout))
        self.run("shell", "uitest", "screenCap", "-p", "/data/local/tmp/soloops-m0-screen.png")
        self.run("file", "recv", "/data/local/tmp/soloops-m0-screen.png", str(screen))
        if not screen.is_file() or screen.stat().st_size == 0:
            raise RuntimeError("HDC did not produce a screenshot")
        nodes = []

        def visit(node):
            value = node.get("attributes", {})
            if value.get("text") or value.get("description"):
                nodes.append(
                    {
                        k: value.get(k, "")
                        for k in ("text", "description", "bounds", "clickable", "type")
                    }
                )
            for child in node.get("children", []):
                visit(child)

        visit(json.loads(layout.read_text(encoding="utf8")))
        if emit:
            print(
                json.dumps(
                    {"screen": str(screen.relative_to(ROOT)), "nodes": nodes}, ensure_ascii=False
                )
            )
        return nodes

    def tap(self, text):
        nodes = self.snapshot(emit=False)
        matches = [n for n in nodes if n["text"] == text or n["description"] == text]
        if not matches:
            raise RuntimeError(f"Visible control not found: {text}")
        bounds = [int(v) for v in re.findall(r"-?\d+", matches[-1]["bounds"])]
        self.run(
            "shell",
            "uitest",
            "uiInput",
            "click",
            str((bounds[0] + bounds[2]) // 2),
            str((bounds[1] + bounds[3]) // 2),
        )

    def logs(self):
        pid = self.run("shell", "pidof", BUNDLE)
        if not pid.isdigit():
            raise RuntimeError("App PID is ambiguous or missing")
        stamp = datetime.now(UTC).strftime("%H%M%S%f")
        raw = self.run("shell", "hilog", "-x", "-P", pid)
        markers = (
            "SOLOOPS_M0C ",
            "SOLOOPS_M0B ",
            "SOLOOPS_M0_NATIVE ",
            "SOLOOPS_M0_FIXTURE ",
            "SOLOOPS_M0_URI_DENIED ",
            "SOLOOPS_M0_SHARE_DISMISSED",
            "Unhandled Exception",
            "onUnhandledException",
            "A RenderFlex overflowed",
            "EXCEPTION CAUGHT BY",
        )
        value = "\n".join(
            line[:2000] for line in raw.splitlines() if any(marker in line for marker in markers)
        )
        (self.directory / f"pid-{pid}-{stamp}-hilog.txt").write_text(value, encoding="utf8")
        events = []
        for line in value.splitlines():
            if "SOLOOPS_M0C " in line:
                events.append(json.loads(line.split("SOLOOPS_M0C ", 1)[1]))
        print(
            json.dumps(
                {
                    "pid": pid,
                    "events": events,
                    "native": [
                        line.split("SOLOOPS_", 1)[1]
                        for line in value.splitlines()
                        if "SOLOOPS_M0_NATIVE" in line
                        or "SOLOOPS_M0_FIXTURE" in line
                        or "SOLOOPS_M0_URI" in line
                        or "SOLOOPS_M0_SHARE" in line
                    ],
                },
                ensure_ascii=False,
            )
        )
        record = {
            "pid": pid,
            "at": datetime.now(UTC).isoformat(),
            "hap_sha256": hashlib.sha256(HAP.read_bytes()).hexdigest(),
            "events": events,
        }
        (self.directory / f"pid-{pid}-{stamp}-events.json").write_text(
            json.dumps(record, ensure_ascii=False, indent=2), encoding="utf8"
        )
        return events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hdc", required=True)
    parser.add_argument("--target", default="127.0.0.1:5555")
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument(
        "action",
        choices=[
            "start",
            "stop",
            "back",
            "home",
            "snapshot",
            "tap",
            "logs",
            "click",
            "swipe",
            "longClick",
        ],
    )
    parser.add_argument("values", nargs="*")
    args = parser.parse_args()
    session = Session(args.hdc, args.target, args.session)
    if args.action == "start":
        print(session.run("shell", "aa", "start", "-a", "EntryAbility", "-b", BUNDLE))
    elif args.action == "stop":
        print(session.run("shell", "aa", "force-stop", BUNDLE))
    elif args.action in {"back", "home"}:
        session.run("shell", "uitest", "uiInput", "keyEvent", args.action.title())
    elif args.action == "tap":
        session.tap(args.values[0])
    elif args.action in {"click", "swipe", "longClick"}:
        if not all(v.isdigit() for v in args.values):
            parser.error("coordinates must be positive integers")
        session.run("shell", "uitest", "uiInput", args.action, *args.values)
    elif args.action == "logs":
        session.logs()
    else:
        session.snapshot()
    time.sleep(0.25)


if __name__ == "__main__":
    main()
