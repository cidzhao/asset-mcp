from __future__ import annotations

import argparse
from importlib import resources
from pathlib import Path
from typing import Sequence

from asset_mcp import __version__
from asset_mcp.config import default_user_config_path
from asset_mcp.server import main as server_main

TEMPLATE_PACKAGE = "asset_mcp.templates"
TEMPLATE_NAME = "config.local.yaml"


def main(argv: Sequence[str] | None = None) -> int | None:
    args = list(argv) if argv is not None else None
    if args == []:
        server_main()
        return None

    parser = _build_parser()
    namespace = parser.parse_args(args)
    return namespace.handler(namespace)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="asset-mcp",
        description="Read-only MCP server for personal asset aggregation.",
    )
    parser.add_argument("--version", action="version", version=f"asset-mcp {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser(
        "init",
        help="create a local config template",
        description="Create a local asset-mcp config template.",
    )
    init_parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help="config path to create; defaults to ~/.config/asset-mcp/config.local.yaml",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing config file",
    )
    init_parser.set_defaults(handler=_handle_init)

    serve_parser = subparsers.add_parser("serve", help="start the MCP stdio server")
    serve_parser.set_defaults(handler=_handle_serve)

    parser.set_defaults(handler=_handle_serve)
    return parser


def _handle_init(args: argparse.Namespace) -> int:
    config_path = init_config(path=args.path, force=args.force)
    if config_path.created:
        print(f"Created config: {config_path.path}")
    else:
        print(f"Config already exists: {config_path.path}")
    return 0


def _handle_serve(_args: argparse.Namespace) -> None:
    server_main()
    return None


def init_config(path: str | Path | None = None, *, force: bool = False) -> "InitConfigResult":
    target_path = Path(path).expanduser() if path is not None else default_user_config_path()
    target_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _chmod_if_supported(target_path.parent, 0o700)

    if target_path.exists() and not force:
        return InitConfigResult(path=target_path, created=False)

    template = _read_template()
    target_path.write_text(template, encoding="utf-8")
    _chmod_if_supported(target_path, 0o600)
    return InitConfigResult(path=target_path, created=True)


def _read_template() -> str:
    template = resources.files(TEMPLATE_PACKAGE).joinpath(TEMPLATE_NAME).read_text(encoding="utf-8")
    if not template.endswith("\n"):
        template += "\n"
    return template


def _chmod_if_supported(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except OSError:
        pass


class InitConfigResult:
    def __init__(self, *, path: Path, created: bool) -> None:
        self.path = path
        self.created = created
