"""Block-character numerals that scale to any size terminal."""

from __future__ import annotations

_F = {
    "0": ["█████", "█   █", "█   █", "█   █", "█   █", "█   █", "█████"],
    "1": ["   ██", "   ██", "   ██", "   ██", "   ██", "   ██", "   ██"],
    "2": ["█████", "    █", "    █", "█████", "█    ", "█    ", "█████"],
    "3": ["█████", "    █", "    █", "█████", "    █", "    █", "█████"],
    "4": ["█   █", "█   █", "█   █", "█████", "    █", "    █", "    █"],
    "5": ["█████", "█    ", "█    ", "█████", "    █", "    █", "█████"],
    "6": ["█████", "█    ", "█    ", "█████", "█   █", "█   █", "█████"],
    "7": ["█████", "    █", "    █", "    █", "    █", "    █", "    █"],
    "8": ["█████", "█   █", "█   █", "█████", "█   █", "█   █", "█████"],
    "9": ["█████", "█   █", "█   █", "█████", "    █", "    █", "█████"],
    "+": ["     ", "  █  ", "  █  ", "█████", "  █  ", "  █  ", "     "],
    "-": ["     ", "     ", "     ", "█████", "     ", "     ", "     "],
    ":": ["     ", "  █  ", "  █  ", "     ", "  █  ", "  █  ", "     "],
    ".": ["     ", "     ", "     ", "     ", "     ", "  █  ", "  █  "],
    " ": ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
}

GLYPH_ROWS = 7


def render_big(text: str, scale: int = 1) -> str:
    """Render text as block digits, each glyph cell scaled by `scale`."""
    scale = max(1, scale)
    glyphs = [_F.get(ch, _F[" "]) for ch in text]
    lines = []
    for row in range(GLYPH_ROWS):
        expanded = (" " * scale).join(
            "".join(cell * scale for cell in glyph[row]) for glyph in glyphs
        )
        lines.extend([expanded] * scale)
    return "\n".join(lines)
