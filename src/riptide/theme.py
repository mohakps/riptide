"""Theme constants. Pure terminal transparency, coral accent, muted metadata."""
from __future__ import annotations

import textual.renderables.blank as _blank_mod
from rich.style import Style as _RichStyle
from textual.color import Color as _Color
import textual.style as _style_mod
import textual.filter as _filter_mod

# Patch Textual's Blank visual to emit Style() with no background color for transparent/alpha=0
_orig_blank_init = _blank_mod.Blank.__init__
def _transparent_blank_init(self, color: _Color | str = "transparent") -> None:
    c = _Color.parse(color) if isinstance(color, str) else color
    if c.is_transparent or getattr(c, "a", 1) == 0:
        self._rich_style = _RichStyle()
    else:
        _orig_blank_init(self, color)
_blank_mod.Blank.__init__ = _transparent_blank_init

# Patch Textual's Style.rich_style and rich_style_with_offset so transparent background has bgcolor=None
_orig_rich_style_func = _style_mod.Style.rich_style.func
def _patched_rich_style(self) -> _RichStyle:
    rs = _orig_rich_style_func(self)
    bg = getattr(self, "background", None)
    if bg is not None and (getattr(bg, "a", 1) == 0 or getattr(bg, "is_transparent", False)):
        return _RichStyle(
            color=rs.color,
            bgcolor=None,
            bold=rs.bold,
            dim=rs.dim,
            italic=rs.italic,
            underline=rs.underline,
            underline2=rs.underline2,
            reverse=rs.reverse,
            strike=rs.strike,
            blink=rs.blink,
            link=rs.link,
            meta=rs.meta,
        )
    return rs
_style_mod.Style.rich_style = property(_patched_rich_style)

_orig_rich_style_with_offset = _style_mod.Style.rich_style_with_offset
def _patched_rich_style_with_offset(self, x: int, y: int) -> _RichStyle:
    rs = _orig_rich_style_with_offset(self, x, y)
    bg = getattr(self, "background", None)
    if bg is not None and (getattr(bg, "a", 1) == 0 or getattr(bg, "is_transparent", False)):
        return _RichStyle(
            color=rs.color,
            bgcolor=None,
            bold=rs.bold,
            dim=rs.dim,
            italic=rs.italic,
            underline=rs.underline,
            underline2=rs.underline2,
            reverse=rs.reverse,
            strike=rs.strike,
            blink=rs.blink,
            link=rs.link,
            meta=rs.meta,
        )
    return rs
_style_mod.Style.rich_style_with_offset = _patched_rich_style_with_offset

# Guard monochrome filter against None styles
_orig_monochrome_style = _filter_mod.monochrome_style
def _patched_monochrome_style(style: _RichStyle | None) -> _RichStyle:
    if style is None:
        return _RichStyle()
    return _orig_monochrome_style(style)
_filter_mod.monochrome_style = _patched_monochrome_style

BACKGROUND = "transparent"
SURFACE = "transparent"
ACCENT = "#FF6B6B"
TEXT = "#E8E8E8"
DIM = "#71717A"
SUCCESS = "#78DC8C"
WARNING = "#FFD166"
ERROR = "#FF6B6B"
BANNER_HOST = """\
█  █  ███   ███  █████
█▄▄█ █   █ ▀▀█     █  
█  █  ███  ███     █  \
"""
BANNER_CLIENT = """\
████ █    █ █████ █  █ █████
█    █    █ █▄▄   ██▄█   █  
████ ████ █ █▄▄▄  █  █   █  \
"""
HEADER_BANNER = """\
██████╗ ██╗██████╗ ████████╗██╗██████╗ ███████╗
██╔══██╗██║██╔══██╗╚══██╔══╝██║██╔══██╗██╔════╝
██████╔╝██║██████╔╝   ██║   ██║██║  ██║█████╗  
██╔══██╗██║██╔═══╝    ██║   ██║██║  ██║██╔══╝  
██║  ██║██║██║        ██║   ██║██████╔╝███████╗
╚═╝  ╚═╝╚═╝╚═╝        ╚═╝   ╚═╝╚═════╝ ╚══════╝\
"""

HEADER_LINES = HEADER_BANNER.splitlines()

TAGLINES = {
    "home": "Direct, encrypted PC-to-PC file transfer · Zero cloud storage, zero intermediate hops",
    "create": "Dial directly to peer · Outbound connection bypasses CGNAT and strict firewalls",
    "join": "Listening for peer handshake · Keep this screen open while creator dials in",
    "session": "Direct end-to-end encrypted channel · Select local files or drop paths to transfer",
    "setup": "Configure local SSH daemon and automated UPnP port forwarding for inbound connections",
}

CSS = """
App, Screen {
    background: transparent !important;
    color: #E8E8E8;
    layout: vertical;
    padding: 1 2;
}
Static, Label {
    background: transparent;
    color: #E8E8E8;
}
.header {
    color: #FF6B6B;
    text-style: bold;
    text-align: center;
    padding: 0 0 1 0;
}
.version-tag {
    color: #FF6B6B;
    text-style: bold;
    text-align: center;
}
.subheader {
    color: #71717A;
    text-align: center;
    padding: 0 0 1 0;
}
.screen-title {
    color: #FF6B6B;
    text-style: bold;
    padding: 1 0 0 0;
}
.screen-desc {
    color: #71717A;
    padding: 0 0 1 0;
}
.dim {
    color: #71717A;
}
.accent {
    color: #FF6B6B;
}
.success {
    color: #78DC8C;
}
.warning {
    color: #FFD166;
}
.error {
    color: #FF6B6B;
}
.keymap-bar {
    dock: bottom;
    height: 1;
    color: #71717A;
    background: transparent;
    padding: 0 1;
}
.keymap-key {
    color: #E8E8E8;
    text-style: bold;
}
/* Input fields, antigravity-cli style: a bordered composer box
   with a dim label above it and a hint below it, not a bare
   input. Placeholder text is grey, focus border is the accent. */
Input {
    border: round #3F3F46;
    background: transparent;
    color: #E8E8E8;
    height: 3;
    padding: 0 1;
    margin: 0 0 1 0;
}
Input:focus {
    border: round #FF6B6B;
}
Input > .input--placeholder {
    color: #71717A;
}
.composer-label {
    color: #71717A;
    text-style: bold;
    padding: 1 0 0 0;
}
.composer-hint {
    color: #71717A;
    padding: 0 0 1 0;
}
.composer {
    padding: 0 1 1 1;
    margin: 1 0;
    background: transparent;
}
/* Buttons - streamlined, non-bulky */
Button {
    background: transparent;
    color: #E8E8E8;
    border: round #3F3F46;
    height: 3;
    margin: 0 1;
    text-style: bold;
}
Button:focus {
    background: transparent;
    color: #FF6B6B;
    border: round #FF6B6B;
}
Button.primary {
    border: round #FF6B6B;
    color: #FF6B6B;
}
Button.primary:focus {
    background: #FF6B6B;
    color: #121212;
}
Button.allow {
    border: round #78DC8C;
    color: #78DC8C;
}
Button.allow:focus {
    background: #78DC8C;
    color: #121212;
}
Button.deny {
    border: round #71717A;
    color: #71717A;
}
Button.deny:focus {
    border: round #FF6B6B;
    color: #FF6B6B;
}
ProgressBar {
    margin: 1 0;
}
ProgressBar > .bar--bar {
    background: #FF6B6B;
}
OptionList {
    background: transparent;
    border: none;
    padding: 1 2;
    height: auto;
}
OptionList:focus {
    border: none;
}
OptionList > .option-list--option {
    padding: 0 1;
    background: transparent;
    color: #E8E8E8;
}
OptionList > .option-list--option-highlighted {
    background: transparent;
    color: #FF6B6B;
    text-style: bold;
}
ListView {
    background: transparent;
    border: round #3F3F46;
    padding: 0 1;
    height: 16;
}
ListView:focus {
    border: round #FF6B6B;
}
ListItem {
    background: transparent;
    padding: 0 1;
}
ListItem.-highlight,
ListItem.--highlight {
    background: transparent;
}
.file-row {
    width: 100%;
    height: 1;
    layout: horizontal;
    background: transparent;
}
/* File manager colours, in priority order:
   remaining files grey, selected files accent, and the hovered
   (highlighted) row pure white, even if it is also selected.
   The -highlight rules come last so hover/focus wins over selected. */
.file-name {
    width: 1fr;
    color: #71717A;
}
ListItem.selected .file-name {
    color: #FF6B6B;
    text-style: bold;
}
ListItem.selected .file-size,
ListItem.selected .file-mtime {
    color: #71717A;
}
ListItem.-highlight,
ListItem.--highlight,
ListItem.-highlight *,
ListItem.--highlight *,
ListItem.-highlight Label,
ListItem.--highlight Label,
ListItem.-highlight .file-name,
ListItem.--highlight .file-name,
ListItem.-highlight .file-size,
ListItem.--highlight .file-size,
ListItem.-highlight .file-mtime,
ListItem.--highlight .file-mtime,
ListItem.selected.-highlight Label,
ListItem.selected.--highlight Label,
ListView:focus > ListItem.-highlight Label,
ListView:focus > ListItem.--highlight Label {
    color: #FFFFFF !important;
    text-style: bold !important;
}
.file-size {
    width: 12;
    text-align: right;
    color: #71717A;
}
.file-mtime {
    width: 22;
    text-align: right;
    color: #71717A;
}
.file-header-row {
    width: 100%;
    height: 1;
    layout: horizontal;
    padding: 0 1;
    color: #71717A;
    text-style: bold;
}
.file-header-name {
    width: 1fr;
    color: #71717A;
    text-style: bold;
}
.file-header-size {
    width: 12;
    text-align: right;
    color: #71717A;
    text-style: bold;
}
.file-header-mtime {
    width: 22;
    text-align: right;
    color: #71717A;
    text-style: bold;
}

/* Redesigned Session Screen Styles */
#session_scroll {
    height: 1fr;
    overflow-y: auto;
    padding: 0;
    margin: 0;
}
#session_header_row {
    width: 100%;
    height: 3;
    max-height: 3;
    layout: horizontal;
    margin: 0;
    padding: 0;
}
#session_host_title {
    width: auto;
    height: 3;
    color: #FF6B6B;
    text-style: bold;
    padding: 0;
    margin: 0;
}
#session_peer_info {
    width: 1fr;
    height: 3;
    layout: vertical;
    padding: 0;
    margin: 0;
}
#peer_client_label {
    width: 100%;
    height: 1;
    text-align: right;
    color: #E8E8E8;
    text-style: bold;
    padding: 0;
    margin: 0;
}
#peer_status_label {
    width: 100%;
    height: 1;
    text-align: right;
    padding: 0;
    margin: 0;
}
#status {
    width: 100%;
    height: 1;
    padding: 0;
    margin: 0;
    color: #71717A;
}

#browser_box {
    width: 100%;
    height: auto;
    border: round #3F3F46;
    background: transparent;
    padding: 0 1;
    margin: 0;
}
#browser_box:focus-within {
    border: round #FF6B6B;
}
#browser_header_row {
    width: 100%;
    height: 1;
    layout: horizontal;
    padding: 0;
    margin: 0;
}
#browser_path {
    width: 1fr;
    height: 1;
    color: #E8E8E8;
    text-style: bold;
    padding: 0;
    margin: 0;
}
#browser_search_indicator {
    width: auto;
    height: 1;
    color: #FFD166;
    text-style: bold;
    padding: 0;
    margin: 0;
}
#browser_separator {
    width: 100%;
    height: 1;
    color: #3F3F46;
    padding: 0;
    margin: 0;
}
#browser_box ListView#cwd_list {
    width: 100%;
    height: 10;
    border: none;
    padding: 0;
    margin: 0;
}
#browser_box ListView#cwd_list:focus {
    border: none;
}
#browser_hint {
    width: 100%;
    height: 1;
    padding: 0;
    margin: 0;
    color: #71717A;
}

#selected_files_section,
#selected_files_list,
#selected_files_section Vertical {
    width: 100%;
    height: auto;
    margin: 0;
    padding: 0;
    background: transparent;
}
#selected_header {
    width: 100%;
    height: 1;
    margin: 0;
    padding: 0;
}
.selected-file-item {
    width: 100%;
    height: 1;
    color: #FF6B6B;
    margin: 0;
    padding: 0;
}

.composer {
    width: 100%;
    height: auto;
    padding: 0;
    margin: 0;
    background: transparent;
}
.composer-label {
    width: 100%;
    height: 1;
    padding: 0;
    margin: 0;
    color: #71717A;
    text-style: bold;
}
.composer-hint {
    width: 100%;
    height: 1;
    padding: 0;
    margin: 0;
    color: #71717A;
}

#download_composer.disabled {
    opacity: 0.35;
}
#download_composer.disabled Input {
    border: round #27272A;
    color: #52525B;
}
#download_composer.disabled .composer-label,
#download_composer.disabled .composer-hint {
    color: #52525B;
}

#progress_section {
    width: 100%;
    height: auto;
    margin: 0;
    padding: 0;
    display: none;
}
#progress_section ProgressBar#bar,
ProgressBar#bar,
ProgressBar {
    width: 100% !important;
    min-width: 100% !important;
    margin: 0 !important;
    padding: 0 !important;
}
ProgressBar > Bar {
    width: 1fr !important;
}
ProgressBar > .bar--bar {
    width: 100% !important;
    background: #FF6B6B;
}
#progress_metrics_row {
    width: 100%;
    height: 1;
    layout: horizontal;
    margin: 0;
    padding: 0;
}
.progress-metric {
    width: 1fr;
    text-align: center;
    color: #A1A1AA;
}
.progress-metric-left {
    width: 1fr;
    text-align: left;
    color: #A1A1AA;
}
.progress-metric-right {
    width: 1fr;
    text-align: right;
    color: #A1A1AA;
}
#progress_file_row {
    width: 100%;
    height: 1;
    layout: horizontal;
    margin: 0;
    padding: 0;
}
#progress_file_name {
    width: 1fr;
    height: 1;
    color: #E8E8E8;
    text-style: bold;
}
#progress_file_size {
    width: auto;
    height: 1;
    text-align: right;
    color: #71717A;
}

#footer_bar {
    dock: bottom;
    width: 100%;
    height: 1;
    layout: horizontal;
    background: transparent;
    padding: 0 1;
    margin: 0;
}
.keymap-item {
    width: 1fr;
    text-align: center;
    color: #71717A;
}
.keymap-left {
    text-align: left;
}
.keymap-right {
    text-align: right;
}
"""
