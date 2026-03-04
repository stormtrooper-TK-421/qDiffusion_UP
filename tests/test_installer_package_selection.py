from __future__ import annotations

from pathlib import Path


def test_get_needed_does_not_include_gui_requirement_list() -> None:
    main_py = (Path(__file__).resolve().parents[1] / "source" / "main.py").read_text(encoding="utf-8")
    get_needed_block = main_py.split("def get_needed(self):", 1)[1].split("@pyqtSlot()", 1)[0]

    assert "self.required_need" not in get_needed_block
    assert "needed += self.optional_need" in get_needed_block
