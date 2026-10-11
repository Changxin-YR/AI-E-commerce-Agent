"""Mutation tests for contract drift; these do not exercise client business UI."""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from validate_ui_contract import ROOT, load_openapi, validate  # noqa: E402


class ContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = load_openapi()
        cls.contract = json.loads((ROOT / "contracts/ui-contract.json").read_text(encoding="utf8"))

    def setUp(self):
        self.data = copy.deepcopy(self.contract)

    def rejects(self, message):
        with self.assertRaisesRegex(ValueError, message):
            validate(self.data, self.api)

    def test_current_contract(self):
        validate(self.data, self.api)

    def test_duplicate_id(self):
        self.data["features"][1]["feature_id"] = self.data["features"][0]["feature_id"]
        self.rejects("duplicate")

    def test_unknown_api(self):
        next(iter(self.data["apis"].values()))["path"] = "/api/not-implemented"
        self.rejects("unknown API")

    def test_missing_business_route(self):
        self.data["features"] = [
            f for f in self.data["features"] if f["feature_id"] != "r2.inventory"
        ]
        self.rejects("route coverage")

    def test_external_success_inference(self):
        self.data["semantic_invariants"]["approval"]["external_success"] = True
        self.rejects("invariants changed")

    def test_unknown_field(self):
        self.data["features"][0]["data_fields"][0]["field"] = "invented_profit"
        self.rejects("unknown data field")

    def test_missing_write_guard(self):
        action = next(
            a
            for a in self.data["features"][0]["allowed_actions"]
            if "csrf" in a["guard_conditions"]
        )
        action["guard_conditions"].remove("csrf")
        self.rejects("write guard missing")

    def test_missing_b1_approval(self):
        next(f for f in self.data["features"] if f["feature_id"] == "r2.b1")["approval_nodes"].pop()
        self.rejects("two distinct")

    def test_invalid_structure(self):
        self.data["entries"][0] = None
        self.rejects("entry must be object")

    def test_missing_action_variants(self):
        action = next(
            a for f in self.data["features"] for a in f["allowed_actions"] if "variants" in a
        )
        del action["variants"]
        self.rejects("action variants differ")

    def test_missing_required_state(self):
        del self.data["state_groups"]["external"]["not_submitted"]
        self.rejects("invalid state group|missing state")

    def test_false_mobile_implementation(self):
        self.data["features"][0]["client_status"]["flutter"] = "implemented"
        self.rejects("cannot assert")


if __name__ == "__main__":
    unittest.main()
