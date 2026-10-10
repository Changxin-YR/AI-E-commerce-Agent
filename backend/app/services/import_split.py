"""Local bounded CSV splitting; no database, network, or formula evaluation."""

import csv
import hashlib
import json
from io import StringIO
from pathlib import Path

from app.core.errors import BusinessError
from app.schemas.import_groups import ImportManifest, ImportPart
from app.services.import_parser import MAX_BYTES, MAX_CELL, MAX_COLUMNS, MAX_ROWS, parse_file

MAX_SOURCE_BYTES = 40 * 1024 * 1024
MAX_PARTS = 20


def encoded_row(values: list[str]) -> bytes:
    output = StringIO(newline="")
    csv.writer(output).writerow(values)
    return output.getvalue().encode("utf-8")


def split_csv(source: Path, destination: Path) -> ImportManifest:
    if source.suffix.lower() != ".csv" or not source.is_file():
        raise ValueError("请选择 UTF-8 CSV；Excel 请先将目标工作表另存为 CSV UTF-8")
    initial = source.stat()
    if not 0 < initial.st_size <= MAX_SOURCE_BYTES:
        raise ValueError("源文件须非空且不超过 40 MiB；更大报表请先按明确日期范围导出")
    if destination.exists():
        raise ValueError("输出目录已存在；请选择新的目录以保留既有分片")
    destination.mkdir(parents=False)
    created: list[Path] = []
    parts: list[ImportPart] = []

    def write_part(data: bytearray, count: int) -> None:
        if len(parts) >= MAX_PARTS:
            raise ValueError("最多 20 个分片／40000 行；请按明确范围重新导出")
        name = f"part-{len(parts) + 1:03d}.csv"
        # Reuse the same security contract as server uploads before producing a manifest.
        _, parsed, _ = parse_file(name, bytes(data))
        if len(parsed) != count:
            raise ValueError("拆分行数核对失败")
        path = destination / name
        with path.open("xb") as output:
            created.append(path)
            output.write(data)
        parts.append(
            ImportPart(
                filename=name, sha256=hashlib.sha256(data).hexdigest(), rows=count, bytes=len(data)
            )
        )

    try:
        with source.open("rb") as raw:
            hasher = hashlib.sha256()
            read_bytes = 0
            while block := raw.read(65536):
                read_bytes += len(block)
                if read_bytes > MAX_SOURCE_BYTES:
                    raise ValueError("源文件读取期间超过40MiB，请关闭编辑后重试")
                hasher.update(block)
            digest = hasher.hexdigest()
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            headers = next(reader)
            if not headers or len(headers) > MAX_COLUMNS:
                raise ValueError("表头须有 1 至 64 列")
            header = b"\xef\xbb\xbf" + encoded_row(headers)
            chunk = bytearray(header)
            count = total = 0
            for values in reader:
                if len(values) > len(headers) or any(
                    len(value) > MAX_CELL or "\x00" in value for value in values
                ):
                    raise ValueError(f"源记录 {total + 1} 列数、单元格长度或控制字符不符合导入限制")
                row = encoded_row(values)
                if len(header) + len(row) > MAX_BYTES:
                    raise ValueError("单行超过分片大小限制")
                if count == MAX_ROWS or len(chunk) + len(row) > MAX_BYTES:
                    write_part(chunk, count)
                    chunk, count = bytearray(header), 0
                chunk.extend(row)
                count += 1
                total += 1
                if total > MAX_ROWS * MAX_PARTS:
                    raise ValueError("最多 40000 个源数据记录；请按明确范围重新导出")
            if not count:
                raise ValueError("源文件须有表头和至少一个数据记录")
            write_part(chunk, count)
        final = source.stat()
        if (initial.st_size, initial.st_mtime_ns) != (final.st_size, final.st_mtime_ns):
            raise ValueError("拆分期间源文件发生变化，请关闭编辑后重试")
        manifest = ImportManifest(
            format="soloops-split-v1",
            source_filename=source.name,
            source_sha256=digest,
            total_rows=total,
            parts=parts,
        )
        path = destination / "manifest.json"
        with path.open("x", encoding="utf-8") as output:
            created.append(path)
            output.write(json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2) + "\n")
        return manifest
    except Exception as error:
        for path in reversed(created):
            path.unlink()
        destination.rmdir()
        if isinstance(error, (UnicodeError, csv.Error, StopIteration)):
            raise ValueError("无法安全读取 UTF-8 CSV；请核对编码、引号与表头后重试") from error
        if isinstance(error, BusinessError):
            raise ValueError("分片未通过现有导入安全校验，请核对表头与单元格") from error
        raise
