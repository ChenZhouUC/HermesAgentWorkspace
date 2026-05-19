#!/usr/bin/env python3
import sys
import zipfile
import xml.etree.ElementTree as ET


def extract(file_path):
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            # Styles
            s_root = ET.fromstring(z.read("xl/styles.xml"))
            ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

            cell_xfs = s_root.find("ns:cellXfs", ns)
            fonts = s_root.find("ns:fonts", ns)
            fills = s_root.find("ns:fills", ns)

            xf_list = cell_xfs.findall("ns:xf", ns) if cell_xfs is not None else []
            font_list = fonts.findall("ns:font", ns) if fonts is not None else []
            fill_list = fills.findall("ns:fill", ns) if fills is not None else []

            def get_xf_info(xf_idx):
                if xf_idx >= len(xf_list):
                    return ""
                xf = xf_list[xf_idx]
                font_id = int(xf.get("fontId", 0))
                fill_id = int(xf.get("fillId", 0))

                info = []
                if font_id < len(font_list):
                    f = font_list[font_id]
                    if f.find("ns:strike", ns) is not None:
                        info.append("STRIKETHROUGH")
                    color = f.find("ns:color", ns)
                    if color is not None and color.get("rgb"):
                        info.append(f"COLOR:{color.get('rgb')}")
                if fill_id < len(fill_list):
                    fill = fill_list[fill_id]
                    pattern = fill.find("ns:patternFill", ns)
                    if pattern is not None:
                        fgColor = pattern.find("ns:fgColor", ns)
                        if fgColor is not None and fgColor.get("rgb"):
                            info.append(f"BG:{fgColor.get('rgb')}")
                return ",".join(info)

            # Shared strings
            shared_strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in root.findall("ns:si", ns):
                    text_parts = []
                    runs = si.findall("ns:r", ns)
                    if runs:
                        for r in runs:
                            t = r.find("ns:t", ns)
                            rPr = r.find("ns:rPr", ns)
                            if t is not None and t.text:
                                is_strike = rPr is not None and rPr.find("ns:strike", ns) is not None
                                if is_strike:
                                    text_parts.append(f"[STRIKETHROUGH: {t.text}]")
                                else:
                                    text_parts.append(t.text)
                        shared_strings.append("".join(text_parts))
                    else:
                        t_elem = si.find("ns:t", ns)
                        shared_strings.append(t_elem.text if t_elem is not None and t_elem.text else "")

            # Read sheet1 (Assuming sheet1.xml, can be extended to loop all sheets)
            root = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))

            print("--- Extracted Rows with Formatting ---")
            for row in root.findall(".//ns:row", ns):
                row_data = []
                for c in row.findall("ns:c", ns):
                    s_idx = int(c.get("s", 0))
                    fmt_info = get_xf_info(s_idx)

                    val = c.find("ns:v", ns)
                    if val is not None:
                        v = val.text
                        if c.get("t") == "s":
                            v = shared_strings[int(v)]
                        if "STRIKETHROUGH" in fmt_info and not str(v).startswith("[STRIKETHROUGH"):
                            v = f"[STRIKETHROUGH: {v}]"
                        elif fmt_info:
                            v = f"[{fmt_info}] {v}"
                        row_data.append(str(v).replace("\n", " "))
                    else:
                        is_elem = c.find("ns:is/ns:t", ns)
                        if is_elem is not None:
                            row_data.append(str(is_elem.text).replace("\n", " "))
                        else:
                            row_data.append("")

                if any(row_data):
                    print(f"Row {row.get('r')}: " + " | ".join(row_data))
    except Exception as e:
        print(f"Error extracting formatting: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_xlsx_formatting.py <file.xlsx>")
        sys.exit(1)
    extract(sys.argv[1])
