"""Theme constants. Dark grey background, bright soft red accent.

No port numbers are ever rendered from here, and no images are used:
the trident is ASCII only, so it works in any terminal.
"""

BACKGROUND = "#1E1E1E"
SURFACE = "#2A2A2A"
ACCENT = "#FF6B6B"
TEXT = "#E8E8E8"
DIM = "#AAAAAA"
SUCCESS = "#78DC8C"
WARNING = "#FFD166"
ERROR = "#FF6B6B"

HEADER_LINES = [
    "          \u03a8  R I P T I D E  \u03a8",
    "     ~~~  direct file transfer  ~~~",
]

CSS = """
Screen {
    background: #1E1E1E;
    color: #E8E8E8;
}
Static, Label {
    color: #E8E8E8;
}
.header {
    color: #FF6B6B;
    text-style: bold;
    text-align: center;
    padding: 1 0;
}
.subheader {
    color: #AAAAAA;
    text-align: center;
}
Button {
    border: solid #FF6B6B;
    background: #2A2A2A;
    color: #E8E8E8;
    margin: 0 2;
}
Button:focus {
    background: #FF6B6B;
    color: #1E1E1E;
}
Input {
    border: solid #FF6B6B;
    background: #2A2A2A;
    color: #E8E8E8;
}
Input:focus {
    border: solid #FF6B6B;
}
ProgressBar > .bar--bar {
    background: #FF6B6B;
}
.dim {
    color: #AAAAAA;
}
.accent {
    color: #FF6B6B;
}
.success {
    color: #78DC8C;
}
.error {
    color: #FF6B6B;
}
"""
