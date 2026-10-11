"""Compare Flutter and Python CSV splitting using synthetic files only."""

import argparse
import base64
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.import_split import split_csv  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dart", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / ".local" / "mobile-business" / ("csv-diff-" + uuid4().hex[:8])
    output.mkdir(parents=True)
    fixtures = [
        b"sku,facts\r\nS1,plain\r\n",
        "\ufeffsku,facts\nS1,中文\n".encode(),
        b'sku,facts\nS1,"line 1\nline 2,comma"\nS2,"a""b"\n',
        b"sku,facts\rS1,test\r\rS2,last\r",
        b'sku\n""\n',
        b"sku,facts\nS1,\nS2",
        ("sku,facts\n" + "\n".join(f"S{i},{'中' * 53}" for i in range(2001))).encode(),
        ("sku,facts\n" + "\n".join(f"S{i},{'x' * 1800}" for i in range(1400))).encode(),
        b'sku,facts\nS1,"unclosed',
        b"sku,facts\nS1,\xff",
        b"sku,sku\nS1,S2",
        b"sku\n" + b"x" * 2001,
    ]
    inputs = [
        {"name": f"synthetic-{i}.csv", "bytes": base64.b64encode(data).decode()}
        for i, data in enumerate(fixtures)
    ]
    source = output / "input.json"
    source.write_text(json.dumps(inputs), encoding="utf-8")
    result = subprocess.run(
        [str(args.dart.resolve()), "run", "tool/csv_split_probe.dart", str(source)],
        cwd=ROOT / "apps/soloops_flutter",
        capture_output=True,
        text=True,
        check=True,
    )
    actual = json.loads(result.stdout)
    checks = []
    for i, data in enumerate(fixtures):
        path = output / inputs[i]["name"]
        path.write_bytes(data)
        try:
            expected = split_csv(path, output / f"parts-{i}")
        except ValueError:
            assert actual[i] == {"rejected": True}, f"case {i}: expected rejection"
            checks.append({"case": i, "rejected": True})
            continue
        assert actual[i]["manifest"] == expected.model_dump(), f"case {i}: manifest differs"
        for j, part in enumerate(expected.parts):
            assert (
                base64.b64decode(actual[i]["parts"][j])
                == (output / f"parts-{i}" / part.filename).read_bytes()
            ), f"case {i}: part {j} bytes differ"
        checks.append({"case": i, "parts": len(expected.parts), "rows": expected.total_rows})
    (output / "results.json").write_text(
        json.dumps({"status": "passed", "cases": checks}, indent=2), encoding="utf-8"
    )
    print(f"{len(checks)} synthetic cases match, evidence: {output / 'results.json'}")


if __name__ == "__main__":
    main()
