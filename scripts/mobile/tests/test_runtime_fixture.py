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


class SyntheticTransferFixtureTests(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        self.client = TestClient(make_app(), base_url="https://127.0.0.1")
        self.headers = {"x-m0-synthetic": "true"}

    def test_upload_stream_boundary_and_no_business_write(self):
        import hashlib

        data = b"M" * (2 * 1024 * 1024)
        response = self.client.post("/_m0c/upload", content=data, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(), {"size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        )
        self.assertEqual(
            self.client.post("/_m0c/upload", content=data + b"X", headers=self.headers).status_code,
            413,
        )
        self.assertEqual(self.client.post("/_m0c/upload", content=b"x").status_code, 403)
        self.assertEqual(
            self.client.post("/api/imports", content=data, headers=self.headers).status_code, 403
        )
        self.assertEqual(self.client.post("/_m0c/unknown", headers=self.headers).status_code, 403)

    def test_chunked_limit_does_not_trust_content_length(self):
        response = self.client.post(
            "/_m0c/upload", content=(b"M" * 65536 for _ in range(33)), headers=self.headers
        )
        self.assertEqual(response.status_code, 413)

    def test_download_failures_and_redirect_are_synthetic(self):
        response = self.client.get("/_m0c/download", headers=self.headers)
        self.assertEqual(response.content, b"M" * 131072)
        self.assertEqual(self.client.get("/_m0c/fail", headers=self.headers).status_code, 503)
        response = self.client.get("/_m0c/redirect", headers=self.headers, follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["location"], "https://example.invalid/")
