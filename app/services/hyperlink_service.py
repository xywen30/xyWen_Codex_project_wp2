from __future__ import annotations

import os
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


SHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
OFFICE_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
HYPERLINK_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink"
TARGET_SHEETS = {"REAL全量", "REAL潜力榜", "评论热度预分析", "REAL7天榜", "REAL15天榜"}

NS = {"x": SHEET_NS, "r": OFFICE_REL_NS, "pr": PACKAGE_REL_NS}


def _cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//x:t", NS))
    value = cell.find("x:v", NS)
    if value is None or value.text is None:
        return ""
    if cell_type == "s":
        try:
            return shared_strings[int(value.text)]
        except (ValueError, IndexError):
            return ""
    return value.text


def _shared_strings(files: dict[str, bytes]) -> list[str]:
    payload = files.get("xl/sharedStrings.xml")
    if not payload:
        return []
    root = ET.fromstring(payload)
    return ["".join(node.text or "" for node in item.findall(".//x:t", NS)) for item in root.findall("x:si", NS)]


def _sheet_paths(files: dict[str, bytes]) -> dict[str, str]:
    workbook = ET.fromstring(files["xl/workbook.xml"])
    relations = ET.fromstring(files["xl/_rels/workbook.xml.rels"])
    targets = {rel.get("Id"): rel.get("Target") for rel in relations.findall("pr:Relationship", NS)}
    output: dict[str, str] = {}
    for sheet in workbook.findall(".//x:sheets/x:sheet", NS):
        rel_id = sheet.get(f"{{{OFFICE_REL_NS}}}id")
        target = targets.get(rel_id)
        if target:
            normalized = target.lstrip("/")
            output[sheet.get("name", "")] = posixpath.normpath(normalized if normalized.startswith("xl/") else posixpath.join("xl", normalized))
    return output


def _rels_path(sheet_path: str) -> str:
    return posixpath.join(posixpath.dirname(sheet_path), "_rels", f"{posixpath.basename(sheet_path)}.rels")


def _new_rel_id(existing: set[str], start: int = 1) -> tuple[str, int]:
    number = start
    while f"rId{number}" in existing:
        number += 1
    rel_id = f"rId{number}"
    existing.add(rel_id)
    return rel_id, number + 1


def apply_native_product_hyperlinks(path: Path) -> int:
    """Convert Ozon URL cells to native Excel hyperlinks without macros."""
    path = Path(path).resolve()
    with zipfile.ZipFile(path, "r") as archive:
        files = {entry.filename: archive.read(entry.filename) for entry in archive.infolist()}

    shared_strings = _shared_strings(files)
    sheet_paths = _sheet_paths(files)
    modified: dict[str, bytes] = {}
    hyperlink_count = 0

    ET.register_namespace("x", SHEET_NS)
    ET.register_namespace("r", OFFICE_REL_NS)
    ET.register_namespace("", PACKAGE_REL_NS)

    for sheet_name, sheet_path in sheet_paths.items():
        if sheet_name not in TARGET_SHEETS or sheet_path not in files:
            continue
        root = ET.fromstring(files[sheet_path])
        first_row = root.find(".//x:sheetData/x:row[@r='1']", NS)
        if first_row is None:
            continue
        link_column = None
        for cell in first_row.findall("x:c", NS):
            if _cell_text(cell, shared_strings) in {"Ozon商品链接", "商品链接"}:
                match = re.match(r"([A-Z]+)", cell.get("r", ""))
                link_column = match.group(1) if match else None
                break
        if not link_column:
            continue

        rels_path = _rels_path(sheet_path)
        if rels_path in files:
            rels_root = ET.fromstring(files[rels_path])
        else:
            rels_root = ET.Element(f"{{{PACKAGE_REL_NS}}}Relationships")
        existing_ids = {rel.get("Id", "") for rel in rels_root.findall("pr:Relationship", NS)}
        next_id = 1
        hyperlinks = ET.Element(f"{{{SHEET_NS}}}hyperlinks")

        for row in root.findall(".//x:sheetData/x:row", NS):
            row_number = row.get("r", "")
            if row_number == "1":
                continue
            cell = next(
                (
                    item
                    for item in row.findall("x:c", NS)
                    if re.match(r"([A-Z]+)", item.get("r", ""))
                    and re.match(r"([A-Z]+)", item.get("r", "")).group(1) == link_column
                ),
                None,
            )
            if cell is None:
                continue
            url = _cell_text(cell, shared_strings).strip()
            if not re.match(r"^https?://", url, flags=re.I):
                continue

            for child in list(cell):
                cell.remove(child)
            cell.set("t", "inlineStr")
            inline = ET.SubElement(cell, f"{{{SHEET_NS}}}is")
            text = ET.SubElement(inline, f"{{{SHEET_NS}}}t")
            text.text = "点击打开商品"

            rel_id, next_id = _new_rel_id(existing_ids, next_id)
            ET.SubElement(
                rels_root,
                f"{{{PACKAGE_REL_NS}}}Relationship",
                {"Id": rel_id, "Type": HYPERLINK_REL, "Target": url, "TargetMode": "External"},
            )
            ET.SubElement(
                hyperlinks,
                f"{{{SHEET_NS}}}hyperlink",
                {"ref": cell.get("r", f"{link_column}{row_number}"), f"{{{OFFICE_REL_NS}}}id": rel_id},
            )
            hyperlink_count += 1

        if not list(hyperlinks):
            continue
        insert_at = len(root)
        late_elements = {"printOptions", "pageMargins", "pageSetup", "headerFooter", "drawing", "legacyDrawing", "picture", "oleObjects", "controls", "webPublishItems", "tableParts", "extLst"}
        for index, child in enumerate(list(root)):
            if child.tag.rsplit("}", 1)[-1] in late_elements:
                insert_at = index
                break
        root.insert(insert_at, hyperlinks)
        modified[sheet_path] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        modified[rels_path] = ET.tostring(rels_root, encoding="utf-8", xml_declaration=True)

    if not hyperlink_count:
        return 0

    temporary = path.with_name(f"{path.stem}.hyperlink.tmp{path.suffix}")
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            if name not in modified:
                archive.writestr(name, payload)
        for name, payload in modified.items():
            archive.writestr(name, payload)
    os.replace(temporary, path)
    return hyperlink_count
