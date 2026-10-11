"""Small HDC UI test helper; selects only nodes in fresh device layout dumps."""

import argparse
import json
import re
import subprocess
from pathlib import Path

HDC = r"C:/Program Files/Huawei/DevEco Studio/sdk/default/openharmony/toolchains/hdc.exe"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / ".local/mobile-business/device"
BUNDLE = "dev.soloops.soloops_flutter"
REMOTE = "/data/local/tmp/soloops-r2-layout.json"


def hdc(*args):
    result = subprocess.run(
        [HDC, "-t", "127.0.0.1:5555", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout


def snapshot(label="current"):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    hdc("shell", "uitest", "dumpLayout", "-b", BUNDLE, "-p", REMOTE)
    tree = json.loads(hdc("shell", "cat", REMOTE))
    (OUTPUT / (label + ".json")).write_text(json.dumps(tree, ensure_ascii=False), encoding="utf-8")
    items = []

    def visit(node):
        value = node.get("attributes", {})
        if (
            value.get("text")
            or value.get("clickable") == "true"
            or value.get("type") in ("TextInput", "TextField")
        ):
            items.append(
                {
                    key: value.get(key)
                    for key in ("text", "type", "bounds", "clickable", "focused", "enabled", "hint")
                }
            )
        for child in node.get("children", []):
            visit(child)

    def sheets(node):
        if node.get("attributes", {}).get("type") == "SheetWrapper":
            return [node]
        return [sheet for child in node.get("children", []) for sheet in sheets(child)]

    active_sheets = sheets(tree)
    visit(active_sheets[-1] if active_sheets else tree)
    return items


def match(items, text):
    found = (
        [item for item in items if item["type"] == "TextInput"][int(text[7:]) : int(text[7:]) + 1]
        if text.startswith("@input:")
        else [
            item
            for item in items
            if item["text"] == text or (item["text"] or "").startswith(text + "\n")
        ]
    )
    if len(found) > 1:
        found = [item for item in found if item["clickable"] == "true"]
    if len(found) != 1:
        raise ValueError(f"Expected exactly one node for {text!r}; found {len(found)}")
    if found[0]["enabled"] == "false":
        raise RuntimeError(f"Target is disabled: {text!r}")
    numbers = list(map(int, re.findall(r"-?\d+", found[0]["bounds"])))
    x1, y1, x2, y2 = numbers
    if x2 <= x1 or y2 <= y1:
        raise ValueError("Node is not visible")
    return str((x1 + x2) // 2), str((y1 + y2) // 2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["dump", "tap", "findtap", "findtapup", "input", "screen", "swipe", "key"]
    )
    parser.add_argument("values", nargs="*")
    parser.add_argument("--bundle", default=BUNDLE)
    options = parser.parse_args()
    BUNDLE = options.bundle
    if options.action in ("findtap", "findtapup"):
        previous = None
        unchanged = 0
        for _attempt in range(12):
            current = snapshot()
            if not current:
                raise RuntimeError(f"No active UI for {BUNDLE}; refusing to scroll")
            unchanged = unchanged + 1 if current == previous else 0
            if unchanged >= 2:
                raise RuntimeError("Target absent at end of scrollable content")
            previous = current
            bottom = min(
                [
                    int(re.findall(r"-?\d+", item["bounds"])[1])
                    for item in current
                    if "个标签，共" in (item["text"] or "")
                ]
                or [2758]
            )
            try:
                x, y = match(current, options.values[0])
                if int(y) > bottom - 80:
                    raise ValueError("Clipped at viewport edge")
            except ValueError:
                hdc(
                    "shell",
                    "uitest",
                    "uiInput",
                    "swipe",
                    "1050",
                    "800" if options.action == "findtapup" else "2470",
                    "1050",
                    "2470" if options.action == "findtapup" else "800",
                    "2500",
                )
            else:
                print(hdc("shell", "uitest", "uiInput", "click", x, y).strip())
                break
        else:
            raise ValueError("Target not visible after bounded scroll")
    elif options.action in ("tap", "input"):
        x, y = match(snapshot(), options.values[0])
        if options.action == "input":
            hdc("shell", "uitest", "uiInput", "click", x, y)
            hdc("shell", "uitest", "uiInput", "keyEvent", "2072", "2017")
        args = ["click", x, y] if options.action == "tap" else ["text", options.values[1]]
        print(hdc("shell", "uitest", "uiInput", *args).strip())
    elif options.action == "swipe":
        print(hdc("shell", "uitest", "uiInput", "swipe", *options.values).strip())
    elif options.action == "key":
        print(hdc("shell", "uitest", "uiInput", "keyEvent", *options.values).strip())
    elif options.action == "screen":
        OUTPUT.mkdir(parents=True, exist_ok=True)
        name = options.values[0] if options.values else "current"
        remote = "/data/local/tmp/soloops-r2-screen.png"
        hdc("shell", "uitest", "screenCap", "-p", remote)
        hdc("file", "recv", remote, str(OUTPUT / (name + ".png")))
    label = options.values[0] if options.action == "dump" and options.values else "current"
    for index, item in enumerate(snapshot(label)):
        print(f"{index} {item['type']} {item['bounds']} enabled={item['enabled']} {item['text']!r}")
