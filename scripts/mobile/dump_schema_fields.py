"""Dump output-model fields for the schemas the WeChat pages consume.

Usage (from backend/, so app.* is importable):

    .venv/Scripts/python.exe ../scripts/mobile/dump_schema_fields.py ../.local/schema-fields.json

The result feeds scripts/mobile/check_schema_fields.mjs, which verifies that the
client DTOs still declare every field the service returns. Writing the file from
Python keeps UTF-8 intact instead of relying on shell redirection.
"""

import json
import sys
from importlib import import_module
from pathlib import Path

MODULES = {
    "profit": ["StudyResult", "SavedStudyOutput"],
    "expenses": ["ExpenseSaved", "ExpensePage", "ExpenseOrder", "ExpenseSummary"],
    "fee_rules": ["FeeRuleSaved", "FeeRulePage", "FeeRulePreview"],
    "statements": ["StatementReconciliation"],
    "statement_reviews": ["ReviewSaved", "ReviewPreview", "ReviewPage", "ReviewCurrent"],
    "order_statement_reviews": [
        "OrderReviewSaved",
        "OrderReviewPreview",
        "OrderReviewCurrent",
    ],
    "settlements": ["SettlementSaved", "SettlementPreview", "SettlementCurrent"],
    "authorizations": ["AuthorizationOutput"],
    "schedules": ["ScheduleOutput", "OccurrenceOutput", "ScheduleStatus"],
    "product_quality": ["QualitySaved", "QualityResult"],
    "product_edits": ["EditSaved", "EditSnapshot"],
    "outbound": ["MailOutput", "ChannelOutput", "MailPage"],
    "overview": ["OverviewSaved", "OverviewResult"],
}


def main() -> int:
    result: dict[str, list[str]] = {}
    for module_name, classes in MODULES.items():
        module = import_module(f"app.schemas.{module_name}")
        for class_name in classes:
            model = getattr(module, class_name, None)
            if model is None or not hasattr(model, "model_fields"):
                print(f"missing model app.schemas.{module_name}.{class_name}", file=sys.stderr)
                return 1
            result[class_name] = sorted(model.model_fields)
    payload = json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
