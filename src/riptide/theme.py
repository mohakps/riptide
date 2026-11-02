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
# Page headers, larger than body text. Terminals render all text
# at one pixel size, which Textual cannot change per widget, so
# a "larger" header here means a 5-row block-letter banner, bold
# and accent coloured, in its own taller header row. This is the
# same trick as the menu's ANSI Shadow banner, scaled to short
# page titles so it fits an 80-column terminal.
_BLOCK_FONT = {
    'A': [" ███ ", "█   █", "█████", "█   █", "█   █"],
    'C': [" ████", "█    ", "█    ", "█    ", " ████"],
    'R': ["████ ", "█   █", "████ ", "█ █  ", "█  █ "],
    'E': ["█████", "█    ", "████ ", "█    ", "█████"],
    'T': ["█████", "  █  ", "  █  ", "  █  ", "  █  "],
    'J': ["  ███", "   █ ", "   █ ", "█  █ ", " ██  "],
    'O': [" ███ ", "█   █", "█   █", "█   █", " ███ "],
    'I': ["███", " █ ", " █ ", " █ ", "███"],
    'N': ["█   █", "██  █", "█ █ █", "█  ██", "█   █"],
    'H': ["█   █", "█   █", "█████", "█   █", "█   █"],
    'S': [" ████", "█    ", " ███ ", "    █", "████ "],
    'L': ["█    ", "█    ", "█    ", "█    ", "█████"],
}


def block_banner(text: str) -> str:
    rows = [""] * 5
    for ch in text:
        glyph = _BLOCK_FONT.get(ch, ["     "] * 5)
        for i, row in enumerate(glyph):
            rows[i] += row + " "
    return "\n".join(row.rstrip() for row in rows)


# Session roles, after the Create/Join name swap: the creator
# (listener, Create Server) is the host, the joiner (dialler,
# Join Server) is the client.
BANNER_HOST = r"""   __ ______  __________
  / // / __ \/ __/_  __/
 / _  / /_/ /\ \  / /   
/_//_/\____/___/ /_/"""

BANNER_CLIENT = r"""  _______   _________  ________
 / ___/ /  /  _/ __/ |/ /_  __/
/ /__/ /___/ // _//    / / /   
\___/____/___/___/_/|_/ /_/"""

BANNER_CREATE = r"""  ________  _______ __________
 / ___/ _ \/ __/ _ /_  __/ __/
/ /__/ , _/ _// __ |/ / / _/  
\___/_/|_/___/_/ |_/_/ /___/"""

BANNER_JOIN = r"""     ______  _____  __
 __ / / __ \/  _/ |/ /
/ // / /_/ // //    / 
\___/\____/___/_/|_/"""
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
    # After the name swap: Create Server listens, Join Server dials.
    "create": "Listening for peer handshake · Keep this screen open while joiner dials in",
    "join": "Dial directly to peer · Outbound connection bypasses CGNAT and strict firewalls",
    "session": "Direct end-to-end encrypted channel · Select local files or drop paths to transfer",
    "setup": "Configure local SSH daemon and automated UPnP port forwarding for inbound connections",
}

CSS = """
App, Screen {
    background: transparent !important;
    color: #E8E8E8;
    layout: vertical;
    padding: 1 2;
    layers: base overlay;
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
    border: round #9696a3;
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
    color: #9696a3;
}
.composer-label {
    color: #D7D7D7;
    text-style: bold;
    padding: 1 0 0 0;
}
.composer-hint {
    color: #D0D0D0;
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
    background: #78DC8C;
    color: #121212;
    text-style: bold;
    border: none;
    width: 22;
    min-width: 22;
    height: 3;
}
Button.allow:focus {
    background: #8EEC9F;
    color: #000000;
    border: tall #FFFFFF;
}
Button.deny {
    background: #FF6B6B;
    color: #121212;
    text-style: bold;
    border: none;
    width: 22;
    min-width: 22;
    height: 3;
}
Button.deny:focus {
    background: #FF8585;
    color: #000000;
    border: tall #FFFFFF;
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
    color: #E0E0E0;
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
    color: #E0E0E0;
}
ListItem.selected .file-name {
    color: #FF6B6B;
    text-style: bold;
}
ListItem.selected .file-size,
ListItem.selected .file-mtime {
    color: #E0E0E0;
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
    color: #E0E0E0;
}
.file-mtime {
    width: 22;
    text-align: right;
    color: #E0E0E0;
}
.file-header-pointer {
    width: 2;
    min-width: 2;
    max-width: 2;
    padding: 0;
    margin: 0;
}
.file-pointer {
    width: 2;
    min-width: 2;
    max-width: 2;
    color: #FF6B6B;
    text-style: bold;
    padding: 0;
    margin: 0;
}
.file-header-row {
    width: 100%;
    height: 1;
    layout: horizontal;
    padding: 0 1;
    color: #E0E0E0;
    text-style: bold;
}
.file-header-name {
    width: 1fr;
    color: #E0E0E0;
    text-style: bold;
}
.file-header-size {
    width: 12;
    text-align: right;
    color: #E0E0E0;
    text-style: bold;
}
.file-header-mtime {
    width: 22;
    text-align: right;
    color: #E0E0E0;
    text-style: bold;
}

/* Redesigned Session Screen Styles */
#session_scroll {
    height: 1fr;
    overflow-y: auto;
    padding: 0;
    margin: 0;
}
/* Create Server page: plain container, no scroll container, so
   no vertical scrollbar can appear on this page. */
#create_content {
    height: 1fr;
    width: 100%;
    padding: 0;
    margin: 0;
}
#session_header_row {
    width: 100%;
    height: 5;
    max-height: 5;
    layout: horizontal;
    margin: 0;
    padding: 0;
}
#session_host_title {
    width: auto;
    height: 5;
    color: #FF6B6B;
    text-style: bold;
    padding: 0;
    margin: 0;
}
/* Router port-forwarding notice, shown only when port was closed in OS firewall */
#router_banner {
    display: none;
    width: 100%;
    height: auto;
    background: #FFD166;
    color: #121212;
    text-style: bold;
    text-align: center;
    padding: 1 2;
    margin: 0 0 1 0;
}
.session-header-text {
    color: #FF6B6B;
    text-style: bold;
}
#session_peer_info {
    width: 1fr;
    height: 5;
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
    margin: 1 0;
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
#join_actions {
    width: 100%;
    layout: horizontal;
    padding: 1 0;
    margin: 0;
}
#join_actions Button {
    margin: 0 1;
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

#download_composer {
    width: 100%;
    height: auto;
    padding: 0;
    margin: 2 0 0 0;
    background: transparent;
}
#download_composer .composer-label {
    width: 100%;
    height: 1;
    color: #D7D7D7;
    text-style: bold;
    padding: 0;
    margin: 0;
}
#download_composer Input {
    width: 100%;
    height: 3;
    border: round #3F3F46;
    background: transparent;
    color: #D7D7D7;
    padding: 0 1;
    margin: 0;
}
#download_composer Input > .input--placeholder {
    color: #D7D7D7;
}
#download_composer Input:focus {
    border: round #FF6B6B;
}
#download_denied_message {
    display: none;
    width: 100%;
    height: auto;
    color: #FF6B6B;
    text-style: bold;
    padding: 0;
    margin: 0;
}
#download_denied_message.active {
    display: block;
}
#download_composer.disabled {
    opacity: 0.35;
}
#download_composer.disabled Input {
    border: round #27272A;
    color: #52525B;
}
#download_composer.disabled .composer-label {
    color: #52525B;
}

#progress_section {
    width: 100%;
    height: auto;
    margin: 1 0 0 0;
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
    color: #FF6B6B;
}
.progress-metric-left {
    width: 1fr;
    text-align: left;
    color: #FF6B6B;
}
.progress-metric-right {
    width: 1fr;
    text-align: right;
    color: #FF6B6B;
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
#session_scroll {
    layer: base;
}

/* Download Request Modal Popup (dims background, centered) */
#download_modal_overlay {
    layer: overlay;
    display: none;
    align: center middle;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
}
#download_modal_overlay.active {
    display: block;
}
#download_modal_card {
    width: 60;
    height: auto;
    border: round #FF6B6B;
    background: #18181B;
    padding: 1 2;
    align: center middle;
}
#download_modal_title {
    width: 100%;
    text-align: center;
    color: #FFD166;
    text-style: bold;
    margin: 0 0 1 0;
}
#download_modal_card #download_approval {
    width: 100%;
    text-align: center;
    color: #E8E8E8;
    margin: 0 0 1 0;
}
#download_modal_actions {
    width: 100%;
    height: auto;
    align: center middle;
    margin: 1 0;
}
#download_modal_actions Button {
    margin: 0 2;
    min-width: 16;
}
#download_modal_actions Button.allow {
    background: #78DC8C;
    color: #121212;
    text-style: bold;
}
#download_modal_actions Button.allow:focus {
    background: #8EEC9F;
    color: #000000;
    border: tall #FFFFFF;
}
#download_modal_actions Button.deny {
    background: #FF6B6B;
    color: #121212;
    text-style: bold;
}
#download_modal_actions Button.deny:focus {
    background: #FF8787;
    color: #000000;
    border: tall #FFFFFF;
}
#download_modal_footer {
    width: 100%;
    text-align: center;
    color: #71717A;
    margin: 1 0 0 0;
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

/* Join Screen Redesign Styles */
#public_ip {
    width: 100%;
    height: 1;
    color: #E8E8E8;
    text-style: bold;
    margin: 0 0 1 0;
    padding: 0;
}
#incoming_card {
    width: 100%;
    height: auto;
    border: round #3F3F46;
    background: transparent;
    padding: 1 2;
    margin: 1 0;
}
#incoming_card.active {
    border: round #78DC8C;
}
#incoming {
    width: 100%;
    height: auto;
    margin: 0;
    padding: 0;
    color: #E8E8E8;
}
#join_actions {
    width: 100%;
    height: auto;
    layout: horizontal;
    align: center middle;
    margin: 1 0 0 0;
    padding: 0;
}
#join_actions Button {
    width: 22;
    min-width: 22;
    height: 3;
    margin: 0 2;
    text-style: bold;
    border: none;
}

/* Create Server Redesign Styles */
#create_body {
    width: 100%;
    height: 1fr;
    layout: vertical;
    padding: 1 2;
    margin: 0;
}
#create_top_section {
    width: 100%;
    height: 3fr;
    layout: vertical;
    padding: 0;
    margin: 0;
}
.create-section-title {
    width: 100%;
    height: 1;
    color: #E8E8E8;
    text-style: bold;
    margin: 0 0 1 0;
}
#saved_devices {
    width: 100%;
    height: 1fr;
    max-height: 100%;
    overflow-y: auto;
    padding: 0;
    margin: 0;
}
.device-item {
    width: 100%;
    height: 1;
    color: #71717A;
    margin: 0 0 1 0;
}
#empty_devices {
    width: 100%;
    height: auto;
    color: #71717A;
}
#create_input_section {
    width: 100%;
    height: auto;
    align-horizontal: center;
    margin: 0;
    padding: 0;
}
#create_input_section Input {
    width: 80;
    max-width: 95%;
    height: 5;
    padding: 1 1;
    margin: 0;
}
#create_input_section .composer-label {
    width: 80;
    max-width: 95%;
    color: #FF6B6B;
    text-style: bold;
    text-align: left;
    padding: 0 0 1 0;
}
#create_input_section .composer-hint {
    width: 80;
    max-width: 95%;
    color: #71717A;
    padding: 1 0 0 0;
}
#create_bottom_section {
    width: 100%;
    height: 1fr;
    align-horizontal: center;
    padding: 1 0 0 0;
}
#create_bottom_section #status {
    width: 60;
    max-width: 90%;
    text-align: center;
    color: #71717A;
    margin: 0 0 1 0;
}
/* Fingerprint Approval Modal Popup, like the download request modal */
#fingerprint_modal_overlay {
    layer: overlay;
    display: none;
    align: center middle;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
}
#fingerprint_modal_overlay.active {
    display: block;
}
#fingerprint_modal_card {
    width: 60;
    height: auto;
    border: round #FF6B6B;
    background: #18181B;
    padding: 1 2;
    align: center middle;
}
#fingerprint_modal_title {
    width: 100%;
    text-align: center;
    color: #FFD166;
    text-style: bold;
    margin: 0 0 1 0;
}
#fingerprint_modal_card #fingerprint_modal_body {
    width: 100%;
    text-align: center;
    color: #E8E8E8;
    margin: 0 0 1 0;
}
#fingerprint_modal_actions {
    width: 100%;
    height: auto;
    align: center middle;
    margin: 1 0;
}
#fingerprint_modal_actions Button {
    margin: 0 2;
    min-width: 16;
}
#fingerprint_modal_actions Button.allow {
    background: #78DC8C;
    color: #121212;
    text-style: bold;
}
#fingerprint_modal_actions Button.allow:focus {
    background: #8EEC9F;
    color: #000000;
    border: tall #FFFFFF;
}
#fingerprint_modal_actions Button.deny {
    background: #FF6B6B;
    color: #121212;
    text-style: bold;
}
#fingerprint_modal_actions Button.deny:focus {
    background: #FF8787;
    color: #000000;
    border: tall #FFFFFF;
}
#fingerprint_modal_footer {
    width: 100%;
    text-align: center;
    color: #71717A;
    margin: 1 0 0 0;
}
#create_bottom_section #create {
    display: none;
}
"""
