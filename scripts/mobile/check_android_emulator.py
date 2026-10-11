"""Run M0-B checks against an explicitly selected Android emulator, saving evidence."""

import argparse
import json
import re
import subprocess
import time
import xml.etree.ElementTree as ET
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = "dev.soloops.soloops_flutter"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", required=True)
    parser.add_argument("--serial", required=True)
    args = parser.parse_args()
    if not args.serial.startswith("emulator-"):
        parser.error("This runner only changes emulator display settings.")
    output = ROOT / ".local/mobile-m0b" / args.serial
    output.mkdir(parents=True, exist_ok=True)
    commands = []
    results = {}

    def adb(*parts, binary=False):
        command = [args.adb, "-s", args.serial, *parts]
        result = subprocess.run(command, capture_output=True, timeout=35, check=False)
        commands.append(
            {
                "command": ["adb", "-s", args.serial, *parts],
                "exit_code": result.returncode,
            }
        )
        result.check_returncode()
        return result.stdout if binary else result.stdout.decode("utf8", errors="replace").strip()

    def layout(name):
        adb("shell", "uiautomator", "dump", "/sdcard/soloops-m0b-layout.xml")
        adb("pull", "/sdcard/soloops-m0b-layout.xml", str(output / f"{name}.xml"))
        return ET.parse(output / f"{name}.xml").getroot()

    def labels(tree):
        return "\n".join(n.get("content-desc", "") + n.get("text", "") for n in tree.iter())

    def tap(text):
        tree = layout("before-tap")
        nodes = [n for n in tree.iter() if text in [n.get("text"), n.get("content-desc")]]
        assert len(nodes) == 1, f"Expected unique visible control: {text}"
        coordinates = list(map(int, re.findall(r"\d+", nodes[0].get("bounds", ""))))
        assert len(coordinates) == 4
        x1, y1, x2, y2 = coordinates
        adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
        time.sleep(1)

    def screenshot(name):
        (output / f"{name}.png").write_bytes(adb("exec-out", "screencap", "-p", binary=True))

    def check(name, action):
        try:
            action()
            results[name] = "PASS"
        except (AssertionError, OSError, subprocess.SubprocessError, ET.ParseError) as error:
            results[name] = "FAIL"
            print(f"{name}: {error}")
        print(f"{name}: {results[name]}", flush=True)

    def require(condition, message):
        if not condition:
            raise AssertionError(message)

    original = {
        key: adb("shell", "settings", "get", "system", key)
        for key in ["accelerometer_rotation", "user_rotation", "font_scale"]
    }
    night = adb("shell", "cmd", "uimode", "night")
    device = {
        key: adb("shell", "getprop", key)
        for key in [
            "ro.build.version.sdk",
            "ro.build.version.release",
            "ro.product.model",
            "ro.product.cpu.abi",
            "ro.kernel.qemu",
        ]
    }
    try:
        adb("reverse", "tcp:18443", "tcp:18443")
        start = adb("shell", "am", "start", "-S", "-W", "-n", PACKAGE + "/.MainActivity")
        (output / "cold-start.txt").write_text(start)
        pid = adb("shell", "pidof", PACKAGE)
        time.sleep(2)
        check(
            "cold_start",
            lambda: require("M0-B" in labels(layout("startup")), "missing M0-B page"),
        )
        screenshot("startup")
        tap("运行合成诊断")
        logs = ""
        for _ in range(25):
            logs = adb("logcat", "-d", "-v", "brief", "--pid=" + pid)
            if '"event":"completed"' in logs:
                break
            time.sleep(1)
        events = []
        for line in logs.splitlines():
            if "SOLOOPS_M0B " in line:
                with suppress(json.JSONDecodeError):
                    events.append(json.loads(line.split("SOLOOPS_M0B ", 1)[1]))
        completed = [e["value"] for e in events if e["event"] == "completed"]
        expected = {
            "sandbox_file",
            "clipboard",
            "https_health",
            "anonymous_rejected",
            "synthetic_headers",
            "untrusted_certificate_rejected",
            "connection_failure_and_recovery",
        }

        def probes():
            require(bool(completed), "No completed device probe event")
            require(set(completed[-1]) == expected, "Incomplete probe coverage")
            require(all(v == "PASS" for v in completed[-1].values()), str(completed[-1]))

        check("runtime_probes", probes)
        results.update(completed[-1] if completed else {})
        screenshot("diagnostics")
        tap("查看环境信息")
        check(
            "navigation",
            lambda: require("环境信息" in labels(layout("environment")), "route missing"),
        )
        screenshot("environment")
        adb("shell", "input", "keyevent", "4")
        time.sleep(1)
        check(
            "system_back",
            lambda: require("三端工程验证" in labels(layout("returned")), "did not return"),
        )
        adb("shell", "input", "keyevent", "3")
        time.sleep(2)
        adb("shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity")
        time.sleep(2)
        logs = adb("logcat", "-d", "-v", "brief", "--pid=" + pid)
        check(
            "background_resume",
            lambda: require(
                '"value":"paused"' in logs and '"value":"resumed"' in logs,
                "missing paused/resumed events",
            ),
        )
        adb("shell", "cmd", "uimode", "night", "yes")
        time.sleep(2)
        check(
            "dark_theme",
            lambda: require("主题：dark" in labels(layout("dark")), "no dark theme"),
        )
        screenshot("dark")
        adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")
        adb("shell", "settings", "put", "system", "user_rotation", "1")
        time.sleep(2)
        # Open environment via its observed semantics, even if the list needs scrolling.
        tap("查看环境信息")
        check(
            "landscape",
            lambda: require("方向：landscape" in labels(layout("landscape")), "no landscape"),
        )
        screenshot("landscape")
        adb("shell", "settings", "put", "system", "font_scale", "1.3")
        time.sleep(2)
        check(
            "large_text",
            lambda: require("字体比例：1.3" in labels(layout("large-text")), "scale missing"),
        )
        screenshot("large-text")
        logs = adb("logcat", "-d", "-v", "brief", "--pid=" + pid)
        (output / "app-logcat.txt").write_text(logs, encoding="utf8")
        check(
            "no_runtime_exception",
            lambda: require(
                not any(
                    pattern in logs
                    for pattern in [
                        "FATAL EXCEPTION",
                        "Unhandled Exception",
                        "A RenderFlex overflowed",
                        "EXCEPTION CAUGHT BY",
                    ]
                ),
                "runtime exception in app log",
            ),
        )
    finally:
        for key, value in original.items():
            if value == "null":
                adb("shell", "settings", "delete", "system", key)
            else:
                adb("shell", "settings", "put", "system", key, value)
        match = re.search(r"Night mode: (\w+)", night)
        if match:
            adb("shell", "cmd", "uimode", "night", match.group(1))
        (output / "results.json").write_text(
            json.dumps(
                {
                    "device": device,
                    "original_settings": original,
                    "original_night_mode": night,
                    "results": results,
                    "commands": commands,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf8",
        )
    return 0 if results and all(v == "PASS" for v in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
