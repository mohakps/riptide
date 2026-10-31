"""Theme constants. Pure terminal transparency, coral accent, muted metadata."""

BACKGROUND = "transparent"
SURFACE = "transparent"
ACCENT = "#FF6B6B"
TEXT = "#E8E8E8"
DIM = "#71717A"
SUCCESS = "#78DC8C"
WARNING = "#FFD166"
ERROR = "#FF6B6B"

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
Screen {
    background: transparent;
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
/* Input fields */
Input {
    border: round #3F3F46;
    background: transparent;
    color: #E8E8E8;
    height: 3;
    padding: 0 1;
    margin: 1 0;
}
Input:focus {
    border: round #FF6B6B;
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
    height: 10;
}
ListView:focus {
    border: round #FF6B6B;
}
ListItem {
    background: transparent;
    padding: 0 1;
}
ListItem.--highlight {
    background: transparent;
}
ListItem.--highlight .file-name {
    color: #FF6B6B;
    text-style: bold;
}
.file-row {
    width: 100%;
    height: 1;
    layout: horizontal;
    background: transparent;
}
.file-name {
    width: 1fr;
    color: #E8E8E8;
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
    padding: 0 2;
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
"""
