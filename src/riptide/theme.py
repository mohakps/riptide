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
/* Every button, focused or not, has exactly the same box:
   same width, same height (3 rows), same border, same padding.
   The ONLY change on focus is the fill colour and the text colour.
   text-style must be none, not reverse: Textual's built-in
   Button:focus rule uses reverse, which swaps the label's colours
   back and paints a dark rectangle behind the text. */
Button {
    width: 100%;
    height: 3;
    min-width: 0;
    padding: 0;
    margin: 1 2;
    border: solid #FF6B6B;
    background: #2A2A2A;
    color: #E8E8E8;
    text-style: bold;
    text-align: center;
    content-align: center middle;
    tint: transparent;
    background-tint: transparent;
}
Button:focus {
    width: 100%;
    height: 3;
    min-width: 0;
    padding: 0;
    margin: 1 2;
    border: solid #FF6B6B;
    background: #FF6B6B;
    color: #1E1E1E;
    text-style: bold;
    tint: transparent;
    background-tint: transparent;
}
Button:hover, Button.-active {
    width: 100%;
    height: 3;
    padding: 0;
    margin: 1 2;
    border: solid #FF6B6B;
    tint: transparent;
    background-tint: transparent;
}
Button:focus:hover {
    background: #FF6B6B;
    color: #1E1E1E;
    text-style: bold;
    tint: transparent;
    background-tint: transparent;
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
