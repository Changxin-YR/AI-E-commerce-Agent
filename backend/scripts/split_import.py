"""Run from backend: python -m scripts.split_import source.csv NEW_OUTPUT_DIRECTORY."""

import argparse
from pathlib import Path

from app.services.import_split import split_csv


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SoloOps UTF-8 CSV 安全拆分（最大40MiB/40000行/20片）"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        manifest = split_csv(args.source, args.destination)
    except (ValueError, OSError) as error:
        parser.exit(1, f"拆分失败：{error}\n")
    print(f"已核对 {manifest.total_rows} 个源记录、{len(manifest.parts)} 个分片。")
    print("在文件导入页选择店铺与来源，读取 manifest.json 建组，再逐片上传、预览和确认。")


if __name__ == "__main__":
    main()
