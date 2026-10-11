import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_fixture import make_app


class RuntimeFixtureTests(unittest.TestCase):
    def test_only_anonymous_read_only_routes_reach_original_app(self):
        from fastapi.testclient import TestClient

        # No lifespan: no scheduler and no startup side effects.
        client = TestClient(make_app(), base_url="https://127.0.0.1")
        self.assertEqual(client.get("/api/health/live").status_code, 200)
        self.assertEqual(client.get("/api/auth/session").status_code, 401)
        for path in ["/api/health/ready", "/api/products", "/api/auth/login"]:
            self.assertEqual(client.get(path).status_code, 403)
        self.assertEqual(client.post("/api/auth/login", json={}).status_code, 403)
        self.assertEqual(
            client.get(
                "/api/auth/session", headers={"cookie": "soloops_session=synthetic"}
            ).status_code,
            403,
        )
        self.assertEqual(
            client.get(
                "/_m0b/echo",
                headers={
                    "cookie": "m0b_probe=synthetic",
                    "authorization": "Bearer m0b-synthetic",
                },
            ).json(),
            {"cookie": True, "bearer": True},
        )
