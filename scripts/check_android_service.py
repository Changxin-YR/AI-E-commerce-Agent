"""Exercise real isolated HTTP/MySQL auth; this is not device acceptance."""

import httpx


def main() -> None:
    headers = {"X-SoloOps-Client": "web", "Origin": "https://localhost"}
    with httpx.Client(base_url="http://127.0.0.1:8011", headers=headers) as client:
        assert client.get("/api/health/ready").json()["database"] == "mysql"
        assert client.get("/api/auth/session").status_code == 401
        login = client.post(
            "/api/auth/login",
            json={"username": "android_seller", "password": "Android-Synthetic-2026!"},
        )
        assert login.status_code == 200, login.text
        cookie = login.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
        assert client.get("/api/auth/session").status_code == 200
        rejected = client.post("/api/auth/logout")
        assert rejected.status_code == 403
        assert rejected.json()["error"]["code"] == "csrf_rejected"
        client.headers["X-CSRF-Token"] = "invalid"
        assert client.post("/api/auth/logout").status_code == 403
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        client.headers["Origin"] = "https://untrusted.invalid"
        assert client.post("/api/auth/logout").json()["error"]["code"] == "origin_rejected"
        client.headers["Origin"] = "https://localhost"
        assert client.post("/api/auth/logout").status_code == 204
        assert client.get("/api/auth/session").status_code == 401
    print("Real HTTP/MySQL auth: Cookie attributes, CSRF, Origin, logout verified.")


if __name__ == "__main__":
    main()
