from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.schemas.common import InputModel, OutputModel
from app.schemas.imports import BatchSummary, UploadOptions

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class ImportPart(InputModel):
    filename: Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[^/\\]+\.csv$")]
    sha256: Digest
    rows: Annotated[int, Field(ge=1, le=2000)]
    bytes: Annotated[int, Field(ge=1, le=2097152)]


class ImportManifest(InputModel):
    format: Literal["soloops-split-v1"]
    source_filename: Annotated[str, Field(min_length=1, max_length=240)]
    source_sha256: Digest
    total_rows: Annotated[int, Field(ge=1, le=40000)]
    parts: list[ImportPart] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def reconcile(self) -> Self:
        if sum(part.rows for part in self.parts) != self.total_rows:
            raise ValueError("分片行数合计须等于源总行数")
        if len({part.filename for part in self.parts}) != len(self.parts):
            raise ValueError("分片文件名须唯一")
        return self


class GroupInput(InputModel):
    options: UploadOptions
    manifest: ImportManifest

    @model_validator(mode="after")
    def standalone_options(self) -> Self:
        if self.options.group_id is not None or self.options.group_part is not None:
            raise ValueError("新建导入组不能引用其他组")
        if self.options.filename != self.manifest.source_filename:
            raise ValueError("源文件名与清单不一致")
        return self


class GroupOutput(OutputModel):
    id: int
    shop_id: int
    version: int
    status: str
    complete: bool
    options: UploadOptions
    manifest: ImportManifest
    batches: list[BatchSummary]
    committed_parts: int
    committed_rows: int
    unique_rows: int
    overlap_rows: int
