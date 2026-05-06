"""Tests for find_references and find_definition tools."""

from kadmon.index.db import SymbolDB
from kadmon.tools.references import FindDefinitionTool, FindReferencesTool


def _setup_db(tmp_path):
    db = SymbolDB(str(tmp_path / "symbols.db"))
    # Create a source file to read lines from
    src = tmp_path / "app.py"
    src.write_text("import os\nclass Foo:\n    pass\n")
    db.upsert_file(str(src), 1.0, 100)
    db.insert_symbols(str(src), [
        {"name": "Foo", "type": "definition", "kind": "class",
         "start_line": 2, "start_col": 0, "end_line": 3, "end_col": 0,
         "parent_name": None, "signature": "class Foo"},
    ])
    ref_file = tmp_path / "main.py"
    ref_file.write_text("from app import Foo\nf = Foo()\n")
    db.upsert_file(str(ref_file), 1.0, 50)
    db.insert_symbols(str(ref_file), [
        {"name": "Foo", "type": "reference", "kind": "import",
         "start_line": 1, "start_col": 0, "end_line": 1, "end_col": 0},
        {"name": "Foo", "type": "reference", "kind": "usage",
         "start_line": 2, "start_col": 4, "end_line": 2, "end_col": 7},
    ])
    return db, src, ref_file


def test_find_references_all(tmp_path):
    db, src, ref_file = _setup_db(tmp_path)
    tool = FindReferencesTool(db)
    result = tool.execute(name="Foo")
    assert not result.error
    assert "Symbol: Foo" in result.output
    assert "Definitions:" in result.output
    assert "class Foo" in result.output
    assert "References (2):" in result.output
    assert "from app import Foo" in result.output


def test_find_references_filter_definition(tmp_path):
    db, _, _ = _setup_db(tmp_path)
    tool = FindReferencesTool(db)
    result = tool.execute(name="Foo", type="definition")
    assert "Definitions:" in result.output
    assert "References" not in result.output


def test_find_references_filter_reference(tmp_path):
    db, _, _ = _setup_db(tmp_path)
    tool = FindReferencesTool(db)
    result = tool.execute(name="Foo", type="reference")
    assert "Definitions:" not in result.output
    assert "References" in result.output


def test_find_references_not_found(tmp_path):
    db, _, _ = _setup_db(tmp_path)
    tool = FindReferencesTool(db)
    result = tool.execute(name="NonExistent")
    assert not result.error
    assert "No results found" in result.output
    assert "index may need updating" in result.output


def test_find_definition(tmp_path):
    db, _, _ = _setup_db(tmp_path)
    tool = FindDefinitionTool(db)
    result = tool.execute(name="Foo")
    assert not result.error
    assert "Symbol: Foo" in result.output
    assert "class Foo" in result.output


def test_find_definition_not_found(tmp_path):
    db, _, _ = _setup_db(tmp_path)
    tool = FindDefinitionTool(db)
    result = tool.execute(name="Bar")
    assert "No definition found" in result.output
