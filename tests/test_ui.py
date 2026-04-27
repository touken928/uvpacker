from __future__ import annotations

import pytest

from uvpacker.view import ui


class TestFormatBytes:
    def test_zero_bytes(self) -> None:
        assert ui.format_bytes(0) == "0 B"

    def test_bytes(self) -> None:
        assert ui.format_bytes(500) == "500 B"

    def test_one_kb(self) -> None:
        assert ui.format_bytes(1024) == "1.0 KB"

    def test_kb_fractional(self) -> None:
        assert ui.format_bytes(1536) == "1.5 KB"

    def test_mb(self) -> None:
        assert ui.format_bytes(1048576) == "1.0 MB"

    def test_gb(self) -> None:
        assert ui.format_bytes(1073741824) == "1.0 GB"

    def test_tb(self) -> None:
        assert ui.format_bytes(1099511627776) == "1.0 TB"

    def test_large_tb(self) -> None:
        assert ui.format_bytes(10995116277760) == "10.0 TB"

    def test_less_than_one_kb(self) -> None:
        assert ui.format_bytes(1023) == "1023 B"


class TestEmit:
    def test_info_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui._emit("hello", level="INFO")
        captured = capsys.readouterr()
        assert "[uvpacker] INFO: hello\n" == captured.out

    def test_error_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui._emit("fail", level="ERROR", to_stderr=True)
        captured = capsys.readouterr()
        assert "[uvpacker] ERROR: fail\n" == captured.err
        assert captured.out == ""

    def test_warn_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui._emit("caution", level="WARN")
        captured = capsys.readouterr()
        assert "[uvpacker] WARN: caution\n" == captured.out


class TestUiFunctions:
    def test_info(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.info("message")
        assert "INFO: message" in capsys.readouterr().out

    def test_warn(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.warn("caution")
        assert "WARN: caution" in capsys.readouterr().out

    def test_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.error("fail")
        assert "ERROR: fail" in capsys.readouterr().err

    def test_success(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.success("done")
        assert "OK: done" in capsys.readouterr().out

    def test_step(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.step(2, 5, "building")
        assert "Step 2/5: building" in capsys.readouterr().out

    def test_kv(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.kv("key", "value")
        assert "key: value" in capsys.readouterr().out

    def test_kv_with_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.kv("key", 42, level="STEP")
        captured = capsys.readouterr().out
        assert "STEP: key: 42" in captured

    def test_bullets(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.bullets(["apple", "banana", "cherry"])
        out = capsys.readouterr().out
        assert "- apple" in out
        assert "- banana" in out
        assert "- cherry" in out

    def test_bullets_empty(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.bullets([])
        assert capsys.readouterr().out == ""

    def test_bullets_with_level(self, capsys: pytest.CaptureFixture[str]) -> None:
        ui.bullets(["item"], level="WARN")
        captured = capsys.readouterr().out
        assert "WARN: - item" in captured
