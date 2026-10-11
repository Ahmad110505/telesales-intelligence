"""
Power BI Template (.pbit) Compiler.
Packages the Tabular DataModelSchema, Report Layout, and OpenXML metadata
into a deployable Microsoft Power BI Template (.pbit) file.
"""

from pathlib import Path
import zipfile


def build_pbit(
    output_path: str = "powerbi/Telesales_Intelligence.pbit",
    model_bim_path: str = "powerbi/Telesales_Intelligence.Dataset/model.bim",
    report_json_path: str = "powerbi/Telesales_Intelligence.Report/report.json"
) -> str:
    out_file = Path(output_path)
    model_file = Path(model_bim_path)
    layout_file = Path(report_json_path)

    if not model_file.exists():
        raise FileNotFoundError(f"model.bim not found at {model_file}")
    if not layout_file.exists():
        raise FileNotFoundError(f"report.json not found at {layout_file}")

    with open(model_file, "r", encoding="utf-8") as f:
        model_content = f.read()

    with open(layout_file, "r", encoding="utf-8") as f:
        layout_content = f.read()

    content_types_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\r\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\r\n'
        '  <Default Extension="json" ContentType="" />\r\n'
        '  <Override PartName="/Version" ContentType="" />\r\n'
        '  <Override PartName="/Settings" ContentType="" />\r\n'
        '  <Override PartName="/Report/Layout" ContentType="" />\r\n'
        '  <Override PartName="/DataModelSchema" ContentType="" />\r\n'
        '</Types>'
    )

    version_str = "1.28"
    settings_json = '{"Version": 2}'

    # PBIT packaging with UTF-16LE encoding required by Power BI Desktop
    with zipfile.ZipFile(out_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types_xml.encode("utf-8"))
        zf.writestr("Version", version_str.encode("utf-16le"))
        zf.writestr("Settings", settings_json.encode("utf-16le"))
        zf.writestr("DataModelSchema", model_content.encode("utf-16le"))
        zf.writestr("Report/Layout", layout_content.encode("utf-16le"))

    print(f"Successfully compiled Power BI Template: {out_file.resolve()} ({out_file.stat().st_size} bytes)")
    return str(out_file.resolve())


if __name__ == "__main__":
    build_pbit()
