"""Run a build/check and preserve its actual output and exit code outside Git."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not args.name.replace("-", "").replace("_", "").isalnum():
        parser.error("a safe evidence name and command are required")
    root = Path(__file__).resolve().parents[2]
    directory = root / ".local/mobile-m0a"
    directory.mkdir(parents=True, exist_ok=True)
    started = datetime.now(UTC)
    stem = started.strftime("%Y%m%dT%H%M%SZ") + "-" + args.name
    log = directory / (stem + ".log")
    resolved = shutil.which(command[0]) or command[0]
    if Path(resolved).is_file():
        resolved = str(Path(resolved).resolve())
    invocation = [resolved, *command[1:]]
    # Windows batch launchers require cmd.exe; list2cmdline quotes spaces in SDK paths.
    if os.name == "nt" and Path(resolved).suffix.lower() in {".bat", ".cmd"}:
        invocation = (
            subprocess.list2cmdline([os.environ.get("COMSPEC", "cmd.exe")])
            + ' /d /s /c "'
            + subprocess.list2cmdline(invocation)
            + '"'
        )
    with log.open("wb") as output:
        try:
            result = subprocess.run(
                invocation, cwd=args.cwd, stdout=output, stderr=subprocess.STDOUT, check=False
            )
            code = result.returncode
        except OSError as error:
            output.write(str(error).encode("utf-8"))
            code = 127
    artifacts = []
    for pattern in args.artifact:
        for path in sorted(args.cwd.glob(pattern)):
            if path.is_file():
                artifacts.append(
                    {
                        "path": str(path.resolve()),
                        "bytes": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                )
    metadata = {
        "name": args.name,
        "started_utc": started.isoformat(),
        "finished_utc": datetime.now(UTC).isoformat(),
        "command": command,
        "cwd": str(args.cwd.resolve()),
        "exit_code": code,
        "log": str(log),
        "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "artifacts": artifacts,
    }
    (directory / (stem + ".json")).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))
    print(log.read_text(encoding="utf-8", errors="replace")[-10000:])
    return code


if __name__ == "__main__":
    sys.exit(main())
