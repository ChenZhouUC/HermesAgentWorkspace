import zipfile
import xml.etree.ElementTree as ET
import sys


def parse_xlsx_with_formatting(file_path, target_sheet="sheet1.xml"):
    """
    Parses an .xlsx file using standard libraries to extract values and formatting.
    Returns a list of rows, where each row is a list of formatted string values.
    """
    result_rows = []
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            ns = {"ns": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

            # 1. Parse Styles
            xf_list, font_list, fill_list = [], [], []
            if "xl/styles.xml" in z.namelist():
                s_root = ET.fromstring(z.read("xl/styles.xml"))
                cell_xfs = s_root.find("ns:cellXfs", ns)
                fonts = s_root.find("ns:fonts", ns)
                fills = s_root.find("ns:fills", ns)

                if cell_xfs is not None:
                    xf_list = cell_xfs.findall("ns:xf", ns)
                if fonts is not None:
                    font_list = fonts.findall("ns:font", ns)
                if fills is not None:
                    fill_list = fills.findall("ns:fill", ns)

            def get_xf_info(xf_idx):
                if xf_idx >= len(xf_list):
                    return []
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
                return info

            # 2. Parse Shared Strings
            shared_strings = []
            if "xl/sharedStrings.xml" in z.namelist():
                root = ET.fromstring(z.read("xl/sharedStrings.xml"))
                for si in root.findall("ns:si", ns):
                    text_parts = []
                    runs = si.findall("ns:r", ns)
                    if runs:
                        for r in runs:
                            t = r.find("ns:t", ns)
                            if t is not None and t.text:
                                text_parts.append(t.text)
                        shared_strings.append("".join(text_parts))
                    else:
                        t_elem = si.find("ns:t", ns)
                        shared_strings.append(t_elem.text if t_elem is not None and t_elem.text else "")

            # 3. Parse Worksheet
            sheet_path = f"xl/worksheets/{target_sheet}"
            if sheet_path not in z.namelist():
                return []

            root = ET.fromstring(z.read(sheet_path))
            for row in root.findall(".//ns:row", ns):
                row_data = []
                for c in row.findall("ns:c", ns):
                    s_idx = int(c.get("s", 0))
                    fmt_info = get_xf_info(s_idx)

                    val = c.find("ns:v", ns)
                    v_text = ""
                    if val is not None:
                        v_text = val.text
                        if c.get("t") == "s":
                            v_text = shared_strings[int(v_text)]
                    else:
                        is_elem = c.find("ns:is/ns:t", ns)
                        if is_elem is not None:
                            v_text = is_elem.text

                    if v_text:
                        if "STRIKETHROUGH" in fmt_info:
                            v_text = f"[STRIKETHROUGH: {v_text}]"
                        # Add other formatting markup as needed (e.g., [BG:FFFF0000] for red backgrounds)

                    row_data.append(str(v_text))
                result_rows.append(row_data)

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")

    return result_rows


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for r in parse_xlsx_with_formatting(sys.argv[1]):
            if any(r):
                print(" | ".join(r))
