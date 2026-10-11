"""Export selected verified local build metadata without local machine paths or raw logs."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUSES = {"PASS", "FAIL", "BLOCKED", "NOT_TESTED"}


def relative(value: str) -> str:
    return Path(value).resolve().relative_to(ROOT).as_posix()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable_command(command: list[str]) -> list[str]:
    result = []
    for arg in command:
        key, separator, value = arg.partition("=")
        prefix = key + separator if separator else ""
        arg = value if separator else arg
        if Path(arg).is_absolute():
            try:
                arg = relative(arg)
            except ValueError:
                name = Path(arg).name.lower()
                if name in {"python.exe", "python"}:
                    arg = "python"
                elif name == "cli.bat":
                    arg = "WECHAT_DEVTOOLS_CLI"
                else:
                    raise ValueError(f"unmapped external tool: {name}") from None
        result.append(prefix + arg.replace("\\", "/"))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", action="append", required=True, help="NAME=STATUS")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/mobile/m0a-evidence.json")
    args = parser.parse_args()
    records = []
    for item in args.record:
        name, status = item.rsplit("=", 1)
        if status not in STATUSES or not name.replace("-", "").isalnum():
            parser.error("invalid evidence name or status")
        files = sorted((ROOT / ".local/mobile-m0a").glob(f"*-{name}.json"))
        if not files:
            parser.error(f"missing executed record: {name}")
        record = json.loads(files[-1].read_text(encoding="utf8"))
        log = Path(record["log"])
        if digest(log) != record["log_sha256"]:
            raise ValueError(f"log changed: {name}")
        if status == "PASS" and record["exit_code"] != 0:
            raise ValueError(f"nonzero exit cannot PASS: {name}")
        for artifact in record["artifacts"]:
            path = Path(artifact["path"])
            if digest(path) != artifact["sha256"]:
                raise ValueError(f"artifact changed: {path.name}")
            artifact["path"] = relative(artifact["path"])
        record["status"] = status
        record["log"] = relative(record["log"])
        record["cwd"] = relative(record["cwd"])
        record["command"] = portable_command(record["command"])
        records.append(record)
    output = {
        "schema_version": "1.0",
        "phase": "M0-A",
        "baseline_sha": "0a49a37dcd7f1ccf0acc2c0a225bfdc8d8bee686",
        "branch": "feat/soloops-mobile-m0a",
        "raw_logs": "Local ignored .local/mobile-m0a; paths relative to repository root",
        "status_policy": "Explicit assessment; exit 0 alone does not prove successful operation",
        "records": records,
    }
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(f"PASS: exported {len(records)} records after verifying logs and artifacts")


if __name__ == "__main__":
    main()
