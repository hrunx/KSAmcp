from ksa_opendata.services.preview import preview_csv, preview_json, preview_xlsx


def test_preview_csv_simple():
    content = b"name,age\nAlice,30\nBob,25\n"
    result = preview_csv(content, rows=2)
    assert result["columns"] == ["name", "age"]
    assert len(result["rows"]) == 2


def test_preview_json_object():
    content = b'{"a": 1, "b": 2}'
    result = preview_json(content)
    assert result["shape"] == "object"


def test_preview_json_list():
    content = b'[{"a": 1}, {"a": 2}]'
    result = preview_json(content, rows=1)
    assert result["shape"] == "list"
    assert result["returned_rows"] == 1


def test_preview_xlsx_basic(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["name", "score"])
    ws.append(["test", 1])
    path = tmp_path / "demo.xlsx"
    wb.save(path)
    result = preview_xlsx(path.read_bytes(), rows=1)
    assert result["columns"] == ["name", "score"]
    assert result["returned_rows"] == 1
