import csv
from io import BytesIO, StringIO
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request, Response
from openpyxl import Workbook
from starlette.concurrency import run_in_threadpool

from app.api.dependencies import CurrentSession, UowDependency
from app.core.errors import BusinessError
from app.schemas.import_groups import GroupInput, GroupOutput
from app.schemas.imports import (
    BatchOutput,
    BatchSummary,
    CatalogOutput,
    CommitInput,
    ImportKind,
    MappingTemplateInput,
    MappingTemplateOutput,
    PreviewInput,
    UploadOptions,
    VersionInput,
)
from app.services.import_catalog import FIELDS
from app.services.import_groups import ImportGroupService
from app.services.import_parser import MAX_BYTES, MAX_ROWS
from app.services.imports import ImportService

router = APIRouter(tags=["文件导入"])


@router.get("/imports/catalog")
def catalog(current: CurrentSession) -> CatalogOutput:
    return CatalogOutput(
        products=FIELDS["products"],
        orders=FIELDS["orders"],
        messages=FIELDS["messages"],
        inventory=FIELDS["inventory"],
        statements=FIELDS["statements"],
        max_bytes=MAX_BYTES,
        max_rows=MAX_ROWS,
    )


@router.get("/imports/templates/{kind}")
def template(
    kind: ImportKind,
    current: CurrentSession,
    format: Literal["csv", "xlsx"] = "csv",
) -> Response:
    headers = [field.key for field in FIELDS[kind]]
    if format == "xlsx":
        workbook = Workbook()
        sheet = workbook.active
        assert sheet is not None
        sheet.title = kind
        sheet.append(headers)
        output_bytes = BytesIO()
        workbook.save(output_bytes)
        workbook.close()
        return Response(
            output_bytes.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="soloops-{kind}.xlsx"'},
        )
    output = StringIO(newline="")
    csv.writer(output).writerow(headers)
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="soloops-{kind}.csv"'},
    )


@router.get("/imports/mappings")
def mappings(current: CurrentSession, uow: UowDependency) -> list[MappingTemplateOutput]:
    return ImportService(uow).templates(current.user_id)


@router.post("/imports/mappings")
def save_mapping(
    data: MappingTemplateInput, current: CurrentSession, uow: UowDependency
) -> MappingTemplateOutput:
    return ImportService(uow).save_template(current.user_id, data)


@router.post("/shops/{shop_id}/imports", status_code=201)
async def upload(
    shop_id: int,
    request: Request,
    options: Annotated[UploadOptions, Query()],
    current: CurrentSession,
    uow: UowDependency,
) -> BatchOutput:
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise BusinessError("file_too_large", "文件不能超过 2 MiB，请拆分后上传", 413)
        data.extend(chunk)
    return await run_in_threadpool(
        ImportService(uow).upload, current.user_id, shop_id, options, bytes(data)
    )


@router.get("/shops/{shop_id}/imports")
def batches(shop_id: int, current: CurrentSession, uow: UowDependency) -> list[BatchSummary]:
    return ImportService(uow).list_batches(current.user_id, shop_id)


@router.get("/imports/{batch_id}")
def batch(batch_id: int, current: CurrentSession, uow: UowDependency) -> BatchOutput:
    return ImportService(uow).get(current.user_id, batch_id)


@router.post("/imports/{batch_id}/preview")
def preview(
    batch_id: int, data: PreviewInput, current: CurrentSession, uow: UowDependency
) -> BatchOutput:
    return ImportService(uow).preview(current.user_id, batch_id, data)


@router.post("/imports/{batch_id}/commit")
def commit(
    batch_id: int, data: CommitInput, current: CurrentSession, uow: UowDependency
) -> BatchOutput:
    return ImportService(uow).commit(current.user_id, batch_id, data)


@router.post("/imports/{batch_id}/revoke")
def revoke(
    batch_id: int, data: VersionInput, current: CurrentSession, uow: UowDependency
) -> BatchOutput:
    return ImportService(uow).withdraw(current.user_id, batch_id, data.version)


@router.post("/imports/{batch_id}/clear")
def clear(
    batch_id: int, data: VersionInput, current: CurrentSession, uow: UowDependency
) -> BatchOutput:
    return ImportService(uow).withdraw(current.user_id, batch_id, data.version, purge=True)


@router.get("/imports/{batch_id}/errors.csv")
def error_report(batch_id: int, current: CurrentSession, uow: UowDependency) -> Response:
    result = ImportService(uow).get(current.user_id, batch_id)
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["source_row", "field", "error"])
    for message in result.errors:
        writer.writerow(["", "'mapping", "'" + message])
    for row in result.rows:
        for issue in row.errors:
            # Always quote text as a spreadsheet literal, including attacker-controlled headers.
            writer.writerow([row.row_number, "'" + issue.field, "'" + issue.message])
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="import-{batch_id}-errors.csv"'},
    )


@router.post("/shops/{shop_id}/import-groups", status_code=201)
def create_group(
    shop_id: int, data: GroupInput, current: CurrentSession, uow: UowDependency
) -> GroupOutput:
    return ImportGroupService(uow).create(current.user_id, shop_id, data)


@router.get("/shops/{shop_id}/import-groups")
def groups(
    shop_id: int,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(ge=1)] = None,
) -> list[GroupOutput]:
    return ImportGroupService(uow).list(current.user_id, shop_id, before)


@router.get("/import-groups/{group_id}")
def group(group_id: int, current: CurrentSession, uow: UowDependency) -> GroupOutput:
    return ImportGroupService(uow).get(current.user_id, group_id)


@router.post("/import-groups/{group_id}/revoke")
def revoke_group(
    group_id: int, data: VersionInput, current: CurrentSession, uow: UowDependency
) -> GroupOutput:
    return ImportGroupService(uow).withdraw(current.user_id, group_id, data.version)
