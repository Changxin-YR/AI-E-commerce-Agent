"""M0 Android emulator diagnostics; records actual commands, UI and probe events."""

import argparse
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "dev.soloops.soloops_flutter"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument(
        "--stage",
        choices=[
            "inspect",
            "storage",
            "pick-open",
            "pick-cancel",
            "pick-small",
            "pick-large",
            "pick-roots",
            "pick-downloads",
            "transfer",
            "share",
            "external",
        ],
        required=True,
    )
    args = parser.parse_args()
    if not args.serial.startswith("emulator-"):
        parser.error("Only an explicitly selected emulator is supported")
    output = (
        ROOT
        / ".local/mobile-m0b"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-closure-" + args.stage)
    )
    output.mkdir(parents=True)
    commands = []
    outcome = {"stage": args.stage, "status": "FAIL"}

    def adb(*parts, binary=False):
        result = subprocess.run(
            [args.adb, "-s", args.serial, *parts], capture_output=True, timeout=40
        )
        commands.append(
            {"command": ["adb", "-s", args.serial, *parts], "exit_code": result.returncode}
        )
        result.check_returncode()
        return result.stdout if binary else result.stdout.decode("utf8", errors="replace").strip()

    def layout(name):
        adb("shell", "uiautomator", "dump", "/sdcard/soloops-m0c.xml")
        data = adb("shell", "cat", "/sdcard/soloops-m0c.xml")
        (output / (name + ".xml")).write_text(data, encoding="utf8")
        return ET.fromstring(data)

    def labels(tree):
        return [
            (n.get("text") or n.get("content-desc"))
            for n in tree.iter()
            if n.get("text") or n.get("content-desc")
        ]

    def tap(label):
        tree = layout("before-tap")
        nodes = [n for n in tree.iter() if label in [n.get("text"), n.get("content-desc")]]
        assert len(nodes) == 1, (label, labels(tree))
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", nodes[0].get("bounds", "")))
        adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
        time.sleep(0.8)

    def screen(name):
        (output / (name + ".png")).write_bytes(adb("exec-out", "screencap", "-p", binary=True))

    def events():
        pid = adb("shell", "pidof", PACKAGE)
        raw = adb("logcat", "-d", "-v", "brief", "--pid=" + pid)
        (output / ("app-logcat-" + pid + ".txt")).write_text(raw, encoding="utf8")
        values = []
        for line in raw.splitlines():
            if "SOLOOPS_M0C " in line:
                values.append(json.loads(line.split("SOLOOPS_M0C ", 1)[1]))
        return values

    baseline_counts = {}
    for item in events():
        baseline_counts[item["name"]] = baseline_counts.get(item["name"], 0) + 1

    def wait_event(name):
        for _ in range(35):
            values = [e for e in events() if e["name"] == name]
            if len(values) > baseline_counts.get(name, 0):
                assert values[-1]["status"] == "PASS", values[-1]
                return values[-1]
            time.sleep(1)
        raise AssertionError("Missing event: " + name)

    def start():
        baseline_counts.clear()
        adb("shell", "am", "start", "-S", "-W", "-n", PACKAGE + "/.MainActivity")
        time.sleep(1)
        tap("M0 技术验收")

    try:
        if args.stage == "storage":
            start()
            before = adb("shell", "pidof", PACKAGE)
            tap("存储与重启准备")
            wait_event("restart_prepared")
            outcome["before_restart"] = events()
            assert all(e["status"] == "PASS" for e in outcome["before_restart"])
            screen("prepared")
            start()
            after = adb("shell", "pidof", PACKAGE)
            assert before != after, "Process did not change"
            tap("重启读回并清除")
            wait_event("restart_read_clear")
            outcome["pids"] = [before, after]
        elif args.stage == "pick-open":
            tap("选择合成文件")
            for _ in range(10):
                if "Show roots" in labels(layout("picker-open")):
                    break
                time.sleep(1)
            else:
                raise AssertionError("System document picker not visible")
        elif args.stage == "pick-roots":
            tap("Show roots")
        elif args.stage == "pick-downloads":
            tap("Downloads")
        elif args.stage == "pick-cancel":
            adb("shell", "input", "keyevent", "4")
            wait_event("picker_cancelled")
        elif args.stage in ["pick-small", "pick-large"]:
            tap("soloops-m0-small.txt" if args.stage == "pick-small" else "soloops-m0-large.txt")
            wait_event("picker_selected" if args.stage == "pick-small" else "picker_size_limit")
        elif args.stage == "transfer":
            tap("传输与网络边界")
            wait_event("transfers_complete")
        elif args.stage == "share":
            start()
            tap("打开合成分享面板")
            wait_event("share_panel")
            outcome["share_ui"] = labels(layout("share-panel"))
            assert any("synthetic.txt" in s for s in outcome["share_ui"])
            screen("share-panel")
            adb("shell", "input", "keyevent", "4")
            time.sleep(1)
            tap("清理分享文件")
            wait_event("share_cleanup")
            outcome["delivery"] = "NOT_TESTED: panel cancelled; no recipient selected"
        elif args.stage == "external":
            start()
            tap("打开本机外链")
            wait_event("external_browser")
            outcome["browser_ui"] = labels(layout("browser"))
            screen("browser")
            adb("shell", "input", "keyevent", "4")
        outcome["labels"] = labels(layout("final"))
        screen("final")
        outcome["events"] = events()
        for log in output.glob("app-logcat-*.txt"):
            raw = log.read_text(encoding="utf8")
            assert not any(
                item in raw
                for item in ["Unhandled Exception", "FATAL EXCEPTION", "A RenderFlex overflowed"]
            )
        outcome["status"] = "PASS"
    finally:
        outcome["commands"] = commands
        (output / "results.json").write_text(
            json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf8"
        )
        print(
            json.dumps(
                {
                    "output": str(output),
                    **{
                        k: v
                        for k, v in outcome.items()
                        if k in {"stage", "status", "pids", "browser_ui", "delivery"}
                    },
                    "event_statuses": {e["name"]: e["status"] for e in outcome.get("events", [])},
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
