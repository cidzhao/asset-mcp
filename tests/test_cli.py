from __future__ import annotations

from pathlib import Path

import pytest

from asset_mcp import __version__
from asset_mcp import cli


def test_init_creates_default_config_under_home(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))

    exit_code = cli.main(["init"])

    config_path = tmp_path / ".config" / "asset-mcp" / "config.local.yaml"
    assert exit_code == 0
    assert config_path.exists()
    assert "replace-with-read-only-key" in config_path.read_text(encoding="utf-8")
    assert f"Created config: {config_path}" in capsys.readouterr().out


def test_init_does_not_overwrite_existing_config(tmp_path, capsys):
    config_path = tmp_path / "config.local.yaml"
    config_path.write_text("custom: true\n", encoding="utf-8")

    exit_code = cli.main(["init", "--path", str(config_path)])

    assert exit_code == 0
    assert config_path.read_text(encoding="utf-8") == "custom: true\n"
    assert f"Config already exists: {config_path}" in capsys.readouterr().out


def test_init_force_overwrites_existing_config(tmp_path):
    config_path = tmp_path / "config.local.yaml"
    config_path.write_text("custom: true\n", encoding="utf-8")

    exit_code = cli.main(["init", "--path", str(config_path), "--force"])

    assert exit_code == 0
    content = config_path.read_text(encoding="utf-8")
    assert "custom: true" not in content
    assert "baseCurrency: USD" in content


def test_init_path_writes_custom_location(tmp_path):
    config_path = tmp_path / "nested" / "asset.yaml"

    exit_code = cli.main(["init", "--path", str(config_path)])

    assert exit_code == 0
    assert config_path.exists()
    assert "manual:" in config_path.read_text(encoding="utf-8")


def test_help_includes_init(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--help"])

    assert exc_info.value.code == 0
    assert "init" in capsys.readouterr().out


def test_version_prints_package_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        cli.main(["--version"])

    assert exc_info.value.code == 0
    assert f"asset-mcp {__version__}" in capsys.readouterr().out


def test_no_args_delegates_to_server(monkeypatch):
    calls = []

    def fake_server_main():
        calls.append("served")

    monkeypatch.setattr(cli, "server_main", fake_server_main)

    result = cli.main([])

    assert result is None
    assert calls == ["served"]
