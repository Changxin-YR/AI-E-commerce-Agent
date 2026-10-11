"""Validate the R2 mobile UI contract against current routes and live OpenAPI metadata."""

import argparse
import json
import re
from pathlib import Path
from typing import Any

from mobile.openapi_source import ROOT, load_openapi

INVARIANTS = {
    "not_submitted": {"external_submission_confirmed": False},
    "seller_reported": {"channel_confirmed": False},
    "stale": {"requires_recheck": True},
    "candidate": {"executed": False},
    "approval": {"external_success": False},
}
CORE = {"r2.home", "r2.listings", "r2.support", "r2.analytics", "r2.b1"}
CORE_STATES = {
    "r2.home": {"task", "business", "source"},
    "r2.listings": {"listing", "source", "external"},
    "r2.support": {"support", "source", "external", "provenance"},
    "r2.analytics": {"analysis"},
    "r2.b1": {"agent", "source", "external"},
}
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def strings(value: Any, name: str, nonempty: bool = True) -> list[str]:
    require(isinstance(value, list), f"{name}: expected list")
    require(all(isinstance(item, str) and item for item in value), f"{name}: invalid string")
    require(not nonempty or bool(value), f"{name}: empty list")
    require(len(value) == len(set(value)), f"{name}: duplicate values")
    return value


def web_routes(root: Path) -> set[str]:
    # Deliberately limited to this repository's literal route table, not Vue runtime buttons.
    source = (root / "frontend/src/router/index.ts").read_text(encoding="utf-8")
    paths = re.findall(r"\bpath:\s*['\"]([^'\"]*)['\"]", source)
    return {"/" + path.lstrip("/") for path in paths if ":pathMatch" not in path}


def validate(contract: Any, api: dict[str, Any], root: Path = ROOT) -> None:
    require(isinstance(contract, dict), "contract must be an object")
    require(contract.get("schema_version") == "1.0", "unsupported schema_version")
    require(contract.get("phase") == "M0-A", "phase must remain M0-A")
    for name in (
        "display_semantics",
        "semantic_invariants",
        "guard_conditions",
        "state_groups",
        "error_states",
        "apis",
        "manual_review",
    ):
        require(isinstance(contract.get(name), dict) and bool(contract[name]), f"missing {name}")
    require(contract["semantic_invariants"] == INVARIANTS, "risk semantic invariants changed")
    require(
        all(
            type(value) is bool
            for group in contract["semantic_invariants"].values()
            for value in group.values()
        ),
        "semantic invariants must be booleans",
    )
    for group, states in contract["state_groups"].items():
        require(isinstance(states, dict) and bool(states), f"{group}: invalid state group")
        require(
            all(isinstance(v, str) and v for v in states.values()),
            f"{group}: missing state descriptions",
        )
    for group, state in (
        ("external", "not_submitted"),
        ("provenance", "seller_reported"),
        ("source", "stale"),
        ("agent", "waiting_approval"),
    ):
        require(state in contract["state_groups"].get(group, {}), f"missing state: {state}")
    for key in INVARIANTS:
        require(
            isinstance(contract["display_semantics"].get(key), str)
            and bool(contract["display_semantics"][key]),
            f"missing semantics: {key}",
        )
    features = contract.get("features")
    require(isinstance(features, list) and bool(features), "features must be nonempty")
    require(all(isinstance(f, dict) for f in features), "feature must be object")
    require(all(isinstance(f.get("web_route"), str) for f in features), "invalid Web route")
    ids = strings([f.get("feature_id") for f in features], "feature_id")
    require(set(ids) >= CORE, "missing core MVP/B1 mapping")
    require(
        {f.get("web_route") for f in features} == web_routes(root), "Web route coverage differs"
    )
    entries = contract.get("entries")
    require(isinstance(entries, list) and len(entries) == 5, "exactly five entries required")
    require(all(isinstance(e, dict) for e in entries), "entry must be object")
    entry_ids = strings([e.get("entry_id") for e in entries], "entry_id")
    require(set(entry_ids) == {"home", "tasks", "ai", "support", "mine"}, "entry IDs differ")
    mapped = set()
    for entry in entries:
        refs = strings(entry.get("feature_ids"), "entry feature_ids")
        require(set(refs) <= set(ids), "unknown entry feature")
        mapped.update(refs)
    require(mapped == set(ids), "feature missing from five-entry navigation")
    schemas = api["components"]["schemas"]
    seen_api = set()
    for api_id, reference in contract["apis"].items():
        require(isinstance(reference, dict), f"{api_id}: API must be object")
        method, path = reference.get("method"), reference.get("path")
        require(method in HTTP_METHODS and isinstance(path, str), f"{api_id}: invalid API")
        require((method, path) not in seen_api, f"{api_id}: duplicate API")
        seen_api.add((method, path))
        operation = api["paths"].get(path, {}).get(method.lower())
        require(isinstance(operation, dict), f"{api_id}: unknown API {method} {path}")
        require(operation.get("operationId") == api_id, f"{api_id}: operationId mismatch")
        body = operation.get("requestBody", {}).get("content", {}).get("application/json", {})
        model = body.get("schema", {}).get("$ref", "").split("/")[-1] or None
        require(reference.get("request_schema") == model, f"{api_id}: request schema changed")
    used_api = set()
    for feature in features:
        feature_id = feature["feature_id"]
        require(feature.get("entry") in entry_ids, f"{feature_id}: unknown entry")
        for name in ("title", "behavior", "empty_state", "client_reason"):
            require(
                isinstance(feature.get(name), str) and bool(feature[name]),
                f"{feature_id}: missing {name}",
            )
        for name in (
            "permissions",
            "approval_nodes",
            "evidence_requirements",
            "so_ids",
            "source_files",
        ):
            strings(feature.get(name), f"{feature_id}.{name}")
        require(
            all(re.fullmatch(r"SO-0(?:0[1-9]|[1-6][0-9]|7[0-4])", so) for so in feature["so_ids"]),
            f"{feature_id}: invalid SO ID",
        )
        require(
            all((root / p).is_file() for p in feature["source_files"]),
            f"{feature_id}: source file missing",
        )
        require(
            feature.get("client_status") == {"flutter": "NOT_TESTED", "weapp": "NOT_TESTED"},
            f"{feature_id}: M0-A cannot assert mobile business implementation",
        )
        require(
            feature.get("flutter_route") is None and feature.get("weapp_route") is None,
            f"{feature_id}: unimplemented client route",
        )
        require(feature.get("unknown_status_policy") == "unknown", "unknown state must fail closed")
        for name, dictionary, allow_empty in (
            ("statuses", "state_groups", True),
            ("display_semantics", "display_semantics", False),
            ("error_states", "error_states", False),
        ):
            refs = strings(feature.get(name), f"{feature_id}.{name}", not allow_empty)
            require(
                set(refs) <= set(contract[dictionary]), f"{feature_id}: invalid {name} reference"
            )
        if feature_id in CORE:
            require(
                set(INVARIANTS) <= set(feature["display_semantics"]),
                f"{feature_id}: core risk semantics missing",
            )
            require(
                CORE_STATES[feature_id] <= set(feature["statuses"]),
                f"{feature_id}: core states missing",
            )
        fields = feature.get("data_fields")
        require(isinstance(fields, list) and bool(fields), f"{feature_id}: missing data fields")
        for field in fields:
            require(isinstance(field, dict), f"{feature_id}: invalid field")
            require(
                field.get("field") in schemas.get(field.get("schema"), {}).get("properties", {}),
                f"{feature_id}: unknown data field {field}",
            )
        actions = feature.get("allowed_actions")
        require(isinstance(actions, list) and bool(actions), f"{feature_id}: missing actions")
        require(all(isinstance(a, dict) for a in actions), f"{feature_id}: action must be object")
        strings([a.get("action_id") for a in actions], f"{feature_id}.action_id")
        for action in actions:
            ref = action.get("api_ref")
            require(ref in contract["apis"], f"{feature_id}: unknown API reference")
            used_api.add(ref)
            reference = contract["apis"][ref]
            conditions = strings(action.get("guard_conditions"), "guard_conditions", False)
            require(set(conditions) <= set(contract["guard_conditions"]), "unknown guard condition")
            if reference["method"] not in {"GET", "HEAD", "OPTIONS"}:
                expected = {"risk", "readback", "web_origin"}
                if reference["path"] != "/api/auth/login":
                    expected |= {"session", "csrf"}
                require(expected <= set(conditions), f"{feature_id}: write guard missing")
            model = reference["request_schema"]
            if model:
                require(
                    action.get("payload_fields") == list(schemas[model].get("properties", {})),
                    f"{ref}: payload fields differ",
                )
                require(
                    action.get("required_payload_fields") == schemas[model].get("required", []),
                    f"{ref}: required fields differ",
                )
                expected_variants = None
                for field in ("action", "decision"):
                    prop = schemas[model].get("properties", {}).get(field, {})
                    if "enum" in prop:
                        expected_variants = {"field": field, "values": prop["enum"]}
                require(
                    action.get("variants") == expected_variants, f"{ref}: action variants differ"
                )
        if feature_id == "r2.b1":
            require(
                feature["approval_nodes"] == ["analysis_todo", "listing_draft"],
                "B1 must retain two distinct approval nodes",
            )
            require(
                all("b1_two_nodes" in a["guard_conditions"] for a in actions),
                "B1 approval guard missing",
            )
    require(used_api == set(contract["apis"]), "unreferenced API catalogue entry")


def render_document(contract: dict[str, Any]) -> str:
    lines = [
        "# SoloOps R2 跨端 UI 行为契约",
        "",
        "本页由 `contracts/ui-contract.json` 生成；修改 JSON 后运行 "
        "`python scripts/validate_ui_contract.py --write-doc`，CI 检查两者一致。",
        "",
        contract["scope"],
        "",
        "## 五个移动主入口",
        "",
    ]
    by_id = {f["feature_id"]: f for f in contract["features"]}
    for entry in contract["entries"]:
        lines.append(
            f"- {entry['title']}：" + "、".join(by_id[i]["title"] for i in entry["feature_ids"])
        )
    lines += ["", "## 必须保留的显示语义", ""]
    for key, value in contract["display_semantics"].items():
        lines.append(f"- `{key}`：{value}")
    lines += [
        "",
        "## 页面、字段、API 与操作",
        "",
        "19 个原业务路由另加登录映射；B1 复用 `/agent`。Flutter/Taro 业务路由均尚未实现。"
        "下列字段和请求签名来自现有 OpenAPI；条件还须服从实际服务层。",
        "",
    ]
    for feature in contract["features"]:
        lines += [
            f"### {feature['feature_id']} · {feature['title']}",
            "",
            f"Web：`{feature['web_route']}`；{', '.join(feature['so_ids'])}。",
            "",
            feature["behavior"],
            "",
            "显示字段："
            + "、".join(f"`{f['schema']}.{f['field']}`" for f in feature["data_fields"])
            + "。",
            "",
            "状态字典："
            + ("、".join(feature["statuses"]) or "采用服务端原值及未知状态策略")
            + "。",
            "",
            "| API | 请求模型 / 动作值 | 前置条件 |",
            "|---|---|---|",
        ]
        for action in feature["allowed_actions"]:
            api = contract["apis"][action["api_ref"]]
            payload = api["request_schema"] or "无 JSON 请求模型；按路由参数/原字节协议"
            if action.get("variants"):
                payload += "；" + ", ".join(action["variants"]["values"])
            lines.append(
                f"| `{api['method']} {api['path']}` | {payload} | "
                + ", ".join(action["guard_conditions"])
                + " |"
            )
        lines += ["", "空状态：" + feature["empty_state"], ""]
    lines += ["## 状态字典", ""]
    for group, states in contract["state_groups"].items():
        lines += [f"### {group}", ""]
        lines += [f"- `{key}`：{value}" for key, value in states.items()]
        lines.append("")
    lines += ["## 前置条件字典", ""]
    lines += [f"- `{key}`：{value}" for key, value in contract["guard_conditions"].items()]
    lines += ["", "## 错误处理", ""]
    lines += [f"- `{key}`：{value}" for key, value in contract["error_states"].items()]
    lines += [
        "",
        "## 核验边界",
        "",
        contract["manual_review"]["coverage"],
        "",
        contract["manual_review"]["limitations"],
        "",
        "当前校验只证明结构、路由覆盖、API/字段引用及必要语义存在；"
        "各端设备行为和真实业务状态一致性为 NOT_TESTED。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=ROOT / "contracts/ui-contract.json")
    parser.add_argument("--write-doc", action="store_true")
    args = parser.parse_args()
    try:
        contract = json.loads(args.contract.read_text(encoding="utf-8"))
        validate(contract, load_openapi())
        expected = render_document(contract)
        doc = ROOT / "docs/mobile/ui-contract.md"
        if args.write_doc:
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text(expected, encoding="utf-8")
        require(
            doc.is_file() and doc.read_text(encoding="utf-8") == expected,
            "ui-contract.md differs; regenerate with --write-doc",
        )
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(f"FAIL: {error}")
        return 1
    print(
        f"PASS: static UI contract; {len(contract['features'])} features, "
        f"{len(contract['apis'])} API references; no database or client execution"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
