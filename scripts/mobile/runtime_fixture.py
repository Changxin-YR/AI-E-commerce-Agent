"""Loopback-only TLS fixture for synthetic emulator probes; never connects to MySQL."""

import argparse
import asyncio
import base64
import hashlib
import ipaddress
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))


def make_app():
    from fastapi.responses import JSONResponse, Response, StreamingResponse
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    from starlette.requests import ClientDisconnect

    from app.core.config import Settings
    from app.main import create_app

    @event.listens_for(Engine, "do_connect")
    def deny_database(*_args, **_kwargs):
        raise RuntimeError("M0-B fixture forbids every database connection")

    app = create_app(
        Settings(
            _env_file=None,
            database_url="mysql+pymysql://m0b_probe@127.0.0.1:1/m0b_probe",
            scheduler_enabled=False,
            model_enabled=False,
            outbound_enabled=False,
            model_api_key=None,
            outbound_api_key=None,
            outbound_smtp_authorization_code=None,
        )
    )

    @app.middleware("http")
    async def allowlist(request, call_next):
        # Dedicated synthetic endpoints never dispatch to the business router.
        if request.url.path.startswith("/_m0c/"):
            if request.headers.get("x-m0-synthetic") != "true":
                return JSONResponse({"detail": "synthetic marker required"}, status_code=403)
            path = request.url.path
            if path in {"/_m0c/upload", "/_m0c/upload-slow"} and request.method == "POST":
                size = 0
                digest = hashlib.sha256()
                try:
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > 2 * 1024 * 1024:
                            return JSONResponse({"detail": "too large"}, status_code=413)
                        digest.update(chunk)
                        if path.endswith("-slow"):
                            await asyncio.sleep(0.1)
                except ClientDisconnect:
                    return JSONResponse({"detail": "synthetic upload cancelled"}, status_code=499)
                return JSONResponse({"size": size, "sha256": digest.hexdigest()})
            if path == "/_m0c/fail" and request.method in {"GET", "POST"}:
                return JSONResponse({"detail": "synthetic failure"}, status_code=503)
            if request.method != "GET":
                return JSONResponse({"detail": "fixture method blocked"}, status_code=403)
            if path == "/_m0c/slow":
                await asyncio.sleep(2)
                return JSONResponse({"synthetic": True})
            if path in {"/_m0c/download", "/_m0c/download-large", "/_m0c/download-slow"}:

                async def chunks():
                    count = 33 if path.endswith("-large") else 2
                    for _ in range(count):
                        if path.endswith("-slow"):
                            await asyncio.sleep(0.4)
                        yield b"M" * 65536

                return StreamingResponse(chunks(), media_type="application/octet-stream")
            if path == "/_m0c/redirect":
                return Response(status_code=302, headers={"location": "https://example.invalid/"})
            return JSONResponse({"detail": "fixture route blocked"}, status_code=403)
        if request.method != "GET":
            return JSONResponse({"detail": "fixture method blocked"}, status_code=403)
        if request.url.path == "/_m0b/echo":
            return JSONResponse(
                {
                    "cookie": request.cookies.get("m0b_probe") == "synthetic",
                    "bearer": request.headers.get("authorization") == "Bearer m0b-synthetic",
                }
            )
        if request.url.path not in {"/api/health/live", "/api/auth/session"}:
            return JSONResponse({"detail": "fixture route blocked"}, status_code=403)
        if request.headers.get("cookie") or request.headers.get("authorization"):
            return JSONResponse({"detail": "fixture credentials blocked"}, status_code=403)
        return await call_next(request)

    return app


def prepare(directory: Path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    directory.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SoloOps local M0-B")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=7))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM)
    (directory / "cert.pem").write_bytes(pem)
    (directory / "key.pem").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    (directory / "dart-defines.json").write_text(
        json.dumps(
            {
                "M0B_API_BASE": "https://127.0.0.1:18443",
                "M0B_CA_BASE64": base64.b64encode(pem).decode(),
            }
        ),
        encoding="utf8",
    )
    print("Prepared ephemeral fixture certificate and debug defines in ignored evidence directory")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "serve"])
    args = parser.parse_args()
    directory = ROOT / ".local/mobile-m0b/tls"
    if args.action == "prepare":
        prepare(directory)
    else:
        import uvicorn

        uvicorn.run(
            make_app(),
            host="127.0.0.1",
            port=18443,
            lifespan="off",
            ssl_certfile=str(directory / "cert.pem"),
            ssl_keyfile=str(directory / "key.pem"),
            access_log=False,
        )


if __name__ == "__main__":
    main()
