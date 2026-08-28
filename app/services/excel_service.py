from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from app.services.hyperlink_service import apply_native_product_hyperlinks


BUNDLED_NODE = Path(
    r"C:\Users\Admin\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe"
)


def find_node() -> Path:
    configured = os.getenv("OZON_NODE_EXE")
    if configured and Path(configured).exists():
        return Path(configured)
    if BUNDLED_NODE.exists():
        return BUNDLED_NODE
    system_node = shutil.which("node")
    if system_node:
        return Path(system_node)
    raise RuntimeError("未找到 Node.js，无法生成统一 Excel")


def build_daily_workbook(root: Path, stamp: str) -> Path:
    root = Path(root).resolve()
    script = root / "scripts" / "build_daily_workbook.mjs"
    output = root / "网爬结果" / f"家居_{stamp}.xlsx"
    if not script.exists():
        raise FileNotFoundError(script)
    if not (root / "node_modules" / "@oai" / "artifact-tool").exists():
        raise RuntimeError("Excel 组件缺失：node_modules/@oai/artifact-tool")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [str(find_node()), str(script), str(root), stamp, str(output)],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"统一 Excel 生成失败：{result.stderr[-2000:]}")
    if not output.exists() or output.stat().st_size < 1024:
        raise RuntimeError("统一 Excel 未生成或文件异常")
    hyperlink_count = apply_native_product_hyperlinks(output)
    if hyperlink_count <= 0:
        raise RuntimeError("统一 Excel 未写入可点击的 Ozon 商品链接")
    return output
