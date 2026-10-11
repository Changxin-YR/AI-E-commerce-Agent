"""Export Android closure evidence, verifying local sources and omitting raw UI labels."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from export_evidence import ROOT, digest, portable_command, relative

STAGES = {
    "storage": [
        "secure_roundtrip_overwrite",
        "secureTamper",
        "secureDropKey",
        "cache_scopes_and_clear",
        "uri_permission_denied",
        "share_size_rejected",
        "localized_dates",
        "restart_read_clear",
    ],
    "pick-cancel": ["picker_cancelled"],
    "pick-large": ["picker_size_limit"],
    "pick-small": ["picker_selected"],
    "transfer": [
        "selected_upload",
        "upload_2mib_boundary",
        "upload_oversize_rejected",
        "upload_server_failure",
        "upload_cancelled",
        "download_download",
        "download_download-large",
        "download_fail",
        "download_download-slow",
        "response_timeout",
        "redirect_not_followed",
        "transfer_error_recovery",
    ],
    "share": ["share_panel", "share_cleanup"],
    "external": ["external_browser"],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    directory = ROOT / ".local/mobile-m0b"
    evidence = json.loads(args.output.read_text(encoding="utf8"))
    artifact = ROOT / "apps/soloops_flutter/build/app/outputs/flutter-apk/app-debug.apk"
    apk_sha = digest(artifact)
    build = next(r for r in evidence["records"] if r["name"] == "closure-android-build")
    install = next(r for r in evidence["records"] if r["name"] == "closure-android-install")
    assert build["artifacts"][0]["sha256"] == apk_sha
    installed_at = datetime.fromisoformat(install["finished_utc"])
    assert datetime.fromisoformat(install["started_utc"]) >= datetime.fromisoformat(
        build["finished_utc"]
    )
    key_info = None
    records = []
    for stage, expected in STAGES.items():
        source = sorted(directory.glob("*-closure-" + stage + "/results.json"))[-1]
        timestamp = datetime.strptime(source.parent.name[:16], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        assert timestamp >= installed_at, "Stage predates current APK installation"
        result = json.loads(source.read_text(encoding="utf8"))
        assert result["status"] == "PASS", stage
        events = result.get("before_restart", []) + result["events"]
        if stage == "storage":
            key_info = next(e["detail"] for e in events if e["name"] == "secure_metadata")
        cases = {name: [e for e in events if e["name"] == name][-1]["status"] for name in expected}
        assert all(status == "PASS" for status in cases.values()), stage
        files = [
            {"path": relative(str(p)), "bytes": p.stat().st_size, "sha256": digest(p)}
            for p in sorted(source.parent.iterdir())
            if p.is_file()
        ]
        records.append(
            {
                "stage": stage,
                "status": "PASS",
                "apk_sha256": apk_sha,
                "source": relative(str(source)),
                "cases": cases,
                "commands": [
                    {**c, "command": portable_command(c["command"])} for c in result["commands"]
                ],
                "evidence_files": files,
            }
        )
    source = sorted(directory.glob("*-emulator-5580/results.json"))[-1]
    result = json.loads(source.read_text(encoding="utf8"))
    assert all(value == "PASS" for value in result["results"].values())
    evidence["platform"] = {
        "os": "Android",
        "device": result["device"],
        "serial": "emulator-5580",
        "scope": "emulator",
        "hardware_security": "NOT_TESTED",
        "key_info": key_info,
    }
    evidence["runtime"] = records
    evidence["basic_regression"] = {
        "status": "PASS",
        "source": relative(str(source)),
        "cases": result["results"],
        "commands": [{**c, "command": portable_command(c["command"])} for c in result["commands"]],
        "evidence_files": [
            {"path": relative(str(p)), "sha256": digest(p)}
            for p in sorted(source.parent.iterdir())
            if p.is_file()
        ],
    }
    evidence["limits"] = {
        "physical_device": "NOT_TESTED",
        "channel_delivery": "NOT_TESTED",
        "browser_page_load": "NOT_TESTED",
        "production_release": "BLOCKED",
        "business_authentication": "NOT_TESTED",
        "ohos_closure": "NOT_TESTED",
        "weapp_closure": "NOT_TESTED",
    }
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(
        f"PASS: {sum(len(r['cases']) for r in records)} closure assertions; "
        f"{len(result['results'])} basic records; {apk_sha}"
    )


if __name__ == "__main__":
    main()
