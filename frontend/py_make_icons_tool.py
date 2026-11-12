"""Génère l'icône de l'agent local (favicon.svg, apple-touch-icon.png, icon-512.png) : un carré
arrondi et un point au trait, blanc sur anthracite. Usage : uv run --with pillow python frontend/py_make_icons_tool.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PUBLIC = Path(__file__).resolve().parent
BG, FG = "#161616", "#f5f5f5"
# repère 100 × 100 : un carré arrondi (trait) et un point plein au centre
SQUARE = (26, 26, 74, 74, 12)  # x0, y0, x1, y1, rayon des coins
DOT = (50, 50, 8)
STROKE = 7


def svg() -> str:
    x0, y0, x1, y1, rx = SQUARE
    cx, cy, r = DOT
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<rect width="100" height="100" rx="22" fill="{BG}"/>'
        f'<rect x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" rx="{rx}" fill="none" stroke="{FG}" stroke-width="{STROKE}"/>'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{FG}"/></svg>\n'
    )


def png(px: int, path: Path) -> None:
    ss = 4
    size = px * ss
    k = size / 100
    img = Image.new("RGB", (size, size), BG)
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1, rx = SQUARE
    d.rounded_rectangle((x0 * k, y0 * k, x1 * k, y1 * k), radius=rx * k, outline=FG, width=round(STROKE * k))
    cx, cy, r = DOT
    d.ellipse(((cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k), fill=FG)
    img.resize((px, px), Image.LANCZOS).save(path)


if __name__ == "__main__":
    # favicon.svg est le fichier lié par index.html (link rel="icon") ; les deux PNG ne sont référencés par aucune page servie
    (PUBLIC / "favicon.svg").write_text(svg())
    png(180, PUBLIC / "apple-touch-icon.png")
    png(512, PUBLIC / "icon-512.png")
    print("Icônes écrites dans", PUBLIC)
