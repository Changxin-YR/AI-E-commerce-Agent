import asyncio

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.dependencies import get_current_session, get_uow
from app.api.routes.imports import multipart_bytes, router
from app.core.errors import BusinessError
from app.schemas.identity import SessionOutput
from app.services.import_parser import MAX_BYTES


def request_for(body: bytes, content_type: str) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({"type": "http", "headers": [(b"content-type", content_type.encode())]}, receive)


def form_request(files):
    request = httpx.Request("POST", "http://testserver", files=files)
    return request_for(request.read(), request.headers["content-type"])


def test_multipart_preserves_original_bytes():
    data = b"\xef\xbb\xbfsku,name\r\na,\xe4\xb8\xad\r\n"
    request = form_request({"file": ("source.csv", data, "text/csv")})
    assert asyncio.run(multipart_bytes(request)) == data


def test_multipart_requires_single_file_field():
    with pytest.raises(BusinessError):
        asyncio.run(multipart_bytes(form_request({"wrong": ("source.csv", b"sku\na")})))


def test_multipart_enforces_file_and_envelope_limits():
    with pytest.raises(BusinessError):
        asyncio.run(multipart_bytes(form_request({"file": ("source.csv", b"x" * (MAX_BYTES + 1))})))
    with pytest.raises(BusinessError):
        asyncio.run(multipart_bytes(request_for(b"x" * (MAX_BYTES + 16385), "multipart/form-data")))


def test_multipart_rejects_extra_files_and_fields():
    for files in [
        [("file", ("a.csv", b"x")), ("file", ("b.csv", b"x"))],
        [("file", ("a.csv", b"x")), ("options", (None, "x"))],
    ]:
        with pytest.raises(Exception, match="Too many"):
            asyncio.run(multipart_bytes(form_request(files)))


def test_multipart_route_passes_authenticated_owner_options_and_bytes(monkeypatch):
    app = FastAPI()
    app.include_router(router)
    # Assert the adapter delegates unchanged bytes/options through the original service.
    app.dependency_overrides[get_current_session] = lambda: SessionOutput(
        user_id=7, username="seller", csrf_token="synthetic"
    )
    sentinel = object()
    app.dependency_overrides[get_uow] = lambda: sentinel
    captured = []

    def upload(self, owner, shop, options, data):
        captured.append((self.uow, owner, shop, options, data))
        raise BusinessError("sentinel", "reached original service", 409)

    monkeypatch.setattr("app.services.imports.ImportService.upload", upload)
    # ImportService initialization ordinarily accesses uow.imports.
    monkeypatch.setattr(
        "app.services.imports.ImportService.__init__", lambda self, uow: setattr(self, "uow", uow)
    )
    with TestClient(app) as client, pytest.raises(BusinessError, match="reached original service"):
        client.post(
            "/shops/3/imports/multipart",
            params={
                "filename": "products.csv",
                "kind": "products",
                "data_identity": "synthetic",
                "timezone": "Asia/Shanghai",
            },
            files={"file": ("temporary", b"sku,name\na,b\n", "text/csv")},
        )
    uow, owner, shop, options, data = captured[0]
    assert (uow, owner, shop) == (sentinel, 7, 3)
    assert options.filename == "products.csv" and options.data_identity == "synthetic"
    assert data == b"sku,name\na,b\n"
