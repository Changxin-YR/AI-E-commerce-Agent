"""Export OHOS closure assertions tied to a verified HAP installation."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from export_evidence import ROOT, digest, portable_command, relative

EXPECTED = {
    "secure_roundtrip_overwrite",
    "asset_invalid_update_rejected",
    "asset_alias_isolation",
    "cache_scopes_and_clear",
    "uri_selection_guard",
    "share_size_rejected",
    "localized_dates",
    "restart_read_clear",
    "picker_cancelled",
    "picker_size_limit",
    "picker_selected",
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
    "share_panel",
    "share_cleanup",
    "external_browser",
}


def installed_successfully(log):
    return "install bundle successfully" in log and "[Fail]" not in log


def validate_snapshot(record, installed_at, hap_sha):
    if datetime.fromisoformat(record["at"]) < installed_at:
        raise ValueError("Runtime snapshot predates HAP installation")
    if record["hap_sha256"] != hap_sha:
        raise ValueError("Runtime snapshot belongs to a different HAP")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--basic", type=Path, required=True)
    parser.add_argument("--display", type=Path, required=True)
    args = parser.parse_args()
    evidence = json.loads(args.output.read_text(encoding="utf8"))
    build = next(r for r in evidence["records"] if r["name"] == "closure-ohos-build")
    install = next(r for r in evidence["records"] if r["name"] == "closure-ohos-install")
    hap = ROOT / build["artifacts"][0]["path"]
    hap_sha = digest(hap)
    if hap_sha != build["artifacts"][0]["sha256"]:
        raise ValueError("Current HAP differs from build evidence")
    if not installed_successfully((ROOT / install["log"]).read_text(encoding="utf8")):
        raise ValueError("HDC did not confirm installation")
    installed_at = datetime.fromisoformat(install["finished_utc"])
    if datetime.fromisoformat(install["started_utc"]) < datetime.fromisoformat(
        build["finished_utc"]
    ):
        raise ValueError("Installation predates build")
    cases = {}
    sources = []
    metadata = None
    pids = set()
    snapshots = [
        (source, json.loads(source.read_text(encoding="utf8")))
        for source in args.session.glob("pid-*-events.json")
    ]
    for source, record in sorted(snapshots, key=lambda item: item[1]["at"]):
        validate_snapshot(record, installed_at, hap_sha)
        pids.add(record["pid"])
        for event in record["events"]:
            if event["name"] in EXPECTED:
                cases[event["name"]] = event["status"]
            if event["name"] == "secure_metadata":
                metadata = event["detail"]
        sources.append({"path": relative(str(source)), "sha256": digest(source)})
    if set(cases) != EXPECTED or set(cases.values()) != {"PASS"}:
        raise ValueError(
            f"Incomplete runtime evidence: missing={sorted(EXPECTED - set(cases))}; "
            f"failed={[k for k, v in cases.items() if v != 'PASS']}"
        )
    if len(pids) < 2:
        raise ValueError("Process restart evidence requires distinct PIDs")
    basic = json.loads(args.basic.read_text(encoding="utf8"))
    validate_snapshot(basic, installed_at, hap_sha)
    if set(basic["results"].values()) != {"PASS"}:
        raise ValueError("Basic regression did not pass")
    display = json.loads(args.display.read_text(encoding="utf8"))
    if display["hap_sha256"] != hap_sha:
        raise ValueError("Display evidence belongs to a different HAP")
    evidence["platform"] = {
        "os": "OHOS",
        "device_api": basic["device_api"],
        "scope": "emulator",
        "asset_policy": metadata,
    }
    evidence["runtime"] = {
        "hap_sha256": hap_sha,
        "cases": cases,
        "sources": sources,
        "commands": [
            {**c, "command": portable_command(c["command"])}
            for c in json.loads((args.session / "actions.json").read_text())
        ],
        "evidence_files": [
            {"path": relative(str(p)), "sha256": digest(p)}
            for p in sorted(args.session.iterdir())
            if p.is_file()
        ],
    }
    evidence["basic_regression"] = {
        "cases": basic["results"],
        "source": relative(str(args.basic)),
        "sha256": digest(args.basic),
    }
    evidence["display"] = display
    evidence["limits"] = {
        "physical_device": "NOT_TESTED",
        "hardware_security": "NOT_TESTED",
        "os_uri_revocation": "NOT_TESTED",
        "channel_delivery": "NOT_TESTED",
        "browser_page_load": "NOT_TESTED",
        "business_authentication": "NOT_TESTED",
        "production_release": "BLOCKED",
    }
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf8"
    )
    print(
        f"PASS: {len(cases)} OHOS assertions, {len(basic['results'])} basic records; HAP {hap_sha}"
    )


if __name__ == "__main__":
    main()
