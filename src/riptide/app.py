"""Riptide Textual app. Entry point: riptide = riptide.app:main"""
from __future__ import annotations

import argparse
import sys

from textual.app import App

from . import __version__
from .theme import CSS


class RiptideApp(App):
    CSS = CSS
    TITLE = "riptide"

    def render(self):
        from textual.renderables.blank import Blank
        return Blank("transparent")

    def on_mount(self) -> None:
        self.styles.background = "transparent"
        from .screens.menu import MenuScreen

        self.push_screen(MenuScreen())

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="riptide",
        description="Direct, encrypted PC-to-PC file transfer in the terminal.",
    )
    parser.add_argument("--version", action="version", version=f"riptide {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    parser.parse_args(argv)
    app = RiptideApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
