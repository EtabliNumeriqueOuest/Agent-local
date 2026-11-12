# ======================================================================
# Fichier : outils_apercu_images_wip.py
# Description : Aperçus des documents importés (vignettes)
# Version : 0.3.2 (beta)
# Auteur : équipe dev
# TODO: brancher sur le pipeline d'import, rien ne l'appelle encore
# ======================================================================
"""Aperçus des documents importés : correction gamma, courbe sRGB, aplatissement des vignettes RGBA.

Travaille sur des pixels en tuples d'entiers 0-255, sans Pillow : (r, g, b) ou (r, g, b, a). Les
vignettes PNG des documents importés arrivent souvent avec un canal alpha ; l'aperçu les veut
opaques sur fond blanc, et réduites sans assombrir les traits fins.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

Pixel = tuple[int, int, int]
PixelRGBA = tuple[int, int, int, int]

WHITE: Pixel = (255, 255, 255)
# exposant de la courbe sRGB par morceaux ; l'approximation « gamma 2.2 » s'en écarte surtout dans les noirs
SRGB_GAMMA = 2.4
# seuils de la courbe sRGB (IEC 61966-2-1) : en dessous, partie linéaire de pente 12.92
SRGB_ENCODED_KNEE = 0.04045
SRGB_LINEAR_KNEE = 0.0031308


def srgb_to_linear(c: float) -> float:
    """Valeur sRGB encodée (0-1) vers lumière linéaire (0-1)."""
    if c <= SRGB_ENCODED_KNEE:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** SRGB_GAMMA


def linear_to_srgb(c: float) -> float:
    """Lumière linéaire (0-1) vers valeur sRGB encodée (0-1)."""
    # borné d'abord : une puissance fractionnaire sur un négatif donnerait un complexe
    c = min(1.0, max(0.0, c))
    if c <= SRGB_LINEAR_KNEE:
        return c * 12.92
    return 1.055 * c ** (1 / SRGB_GAMMA) - 0.055


# table de 256 entrées : évite un pow() par canal et par pixel sur les grosses vignettes
_TO_LINEAR = tuple(srgb_to_linear(i / 255) for i in range(256))


def _to_byte(c: float) -> int:
    return min(255, max(0, round(c * 255)))


def gamma_lut(gamma: float) -> tuple[int, ...]:
    """Table 0-255 de la courbe out = in ** (1 / gamma) : gamma > 1 éclaircit les tons moyens.

    Sert au curseur de contraste de l'aperçu ; ce n'est pas la conversion sRGB exacte.
    """
    if gamma <= 0:
        raise ValueError("gamma doit être strictement positif")
    return tuple(_to_byte((i / 255) ** (1 / gamma)) for i in range(256))


def gamma_correct(pixels: Iterable[Pixel], gamma: float) -> list[Pixel]:
    """Applique gamma_lut à chaque canal ; la table est calculée une fois par appel."""
    lut = gamma_lut(gamma)
    return [(lut[r], lut[g], lut[b]) for r, g, b in pixels]


def gamma_from_midtone(measured: float, target: float = 0.5) -> float:
    """Gamma qui ramène un ton moyen mesuré (0-1, par exemple le fond gris d'un scan) vers target.

    Résout target = measured ** (1 / gamma), soit gamma = log(measured) / log(target).
    """
    if not 0 < measured < 1 or not 0 < target < 1:
        raise ValueError("measured et target doivent être dans ]0, 1[")
    return math.log(measured) / math.log(target)


def composite_over(pixel: PixelRGBA, background: Pixel = WHITE, linear: bool = True) -> Pixel:
    """Compose un pixel RGBA (alpha non prémultiplié) sur un fond opaque : C = a·Cs + (1 - a)·Cb.

    linear=True mélange en lumière linéaire (bords d'antialiasing plus justes) ; linear=False
    reproduit les navigateurs et Pillow, qui mélangent les valeurs encodées en gamma.
    """
    r, g, b, a = pixel
    alpha = a / 255
    if alpha >= 1.0:
        return (r, g, b)
    if alpha <= 0.0:
        return background
    out = []
    for cs, cb in zip((r, g, b), background, strict=True):
        if linear:
            mixed = alpha * _TO_LINEAR[cs] + (1 - alpha) * _TO_LINEAR[cb]
            out.append(_to_byte(linear_to_srgb(mixed)))
        else:
            out.append(_to_byte((alpha * cs + (1 - alpha) * cb) / 255))
    return (out[0], out[1], out[2])


def flatten_rgba(pixels: Iterable[PixelRGBA], background: Pixel = WHITE, linear: bool = True) -> list[Pixel]:
    """Aplatit une vignette RGBA sur fond blanc : le JPEG de l'aperçu n'a pas de canal alpha."""
    return [composite_over(p, background, linear) for p in pixels]


def premultiply(pixel: PixelRGBA) -> tuple[float, float, float, float]:
    """RGBA encodé vers (r, g, b, alpha) linéaires prémultipliés, tous en 0-1."""
    r, g, b, a = pixel
    alpha = a / 255
    return (_TO_LINEAR[r] * alpha, _TO_LINEAR[g] * alpha, _TO_LINEAR[b] * alpha, alpha)


def unpremultiply(r: float, g: float, b: float, a: float) -> PixelRGBA:
    """Inverse de premultiply (a en 0-1) ; un alpha nul rend du noir transparent, la couleur est perdue."""
    if a <= 0:
        return (0, 0, 0, 0)
    return (
        _to_byte(linear_to_srgb(r / a)),
        _to_byte(linear_to_srgb(g / a)),
        _to_byte(linear_to_srgb(b / a)),
        _to_byte(a),
    )


def downscale_box(pixels: Sequence[PixelRGBA], width: int, height: int, factor: int) -> tuple[list[PixelRGBA], int, int]:
    """Réduction par moyenne de blocs factor × factor, en lumière linéaire et alpha prémultiplié.

    Moyenner les valeurs encodées assombrit le texte fin des pages scannées ; moyenner sans
    prémultiplier fait baver la couleur des pixels transparents (souvent du noir) sur les bords.
    Renvoie (pixels, largeur, hauteur) ; les bords qui ne remplissent pas un bloc sont ignorés.
    """
    if factor < 1:
        raise ValueError("factor doit être >= 1")
    if len(pixels) != width * height:
        raise ValueError("nombre de pixels incohérent avec width × height")
    out_w, out_h = width // factor, height // factor
    n = factor * factor
    out: list[PixelRGBA] = []
    for oy in range(out_h):
        for ox in range(out_w):
            acc = [0.0, 0.0, 0.0, 0.0]
            for dy in range(factor):
                row = (oy * factor + dy) * width + ox * factor
                for dx in range(factor):
                    for k, v in enumerate(premultiply(pixels[row + dx])):
                        acc[k] += v
            out.append(unpremultiply(acc[0] / n, acc[1] / n, acc[2] / n, acc[3] / n))
    return out, out_w, out_h


def relative_luminance(pixel: Pixel) -> float:
    """Luminance relative WCAG : canaux linéarisés (gamma sRGB retirée) puis pondérés."""
    r, g, b = (_TO_LINEAR[v] for v in pixel)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: Pixel, bg: Pixel) -> float:
    """Rapport de contraste WCAG entre deux couleurs opaques, de 1 à 21."""
    hi, lo = sorted((relative_luminance(fg), relative_luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def badge_text_color(background: PixelRGBA) -> Pixel:
    """Noir ou blanc pour le libellé posé sur la vignette ; un fond semi-transparent est d'abord aplati sur blanc."""
    flat = composite_over(background)
    black = (0, 0, 0)
    return black if contrast_ratio(black, flat) >= contrast_ratio(WHITE, flat) else WHITE


def css_rgba(pixel: PixelRGBA) -> str:
    """Pixel vers rgba() CSS : l'alpha CSS va de 0 à 1, pas de 0 à 255."""
    r, g, b, a = pixel
    return f"rgba({r}, {g}, {b}, {a / 255:.3g})"


if __name__ == "__main__":
    # test rapide (à la main)
    demi = (200, 30, 30, 128)
    print("sur blanc, linéaire :", composite_over(demi), "· encodé :", composite_over(demi, linear=False))
    print("contraste #161719 / #e9e7e2 :", round(contrast_ratio((0x16, 0x17, 0x19), (0xE9, 0xE7, 0xE2)), 2))
    print("gamma pour un fond à 0.35 :", round(gamma_from_midtone(0.35), 3))
    damier = [(0, 0, 0, 255), (255, 255, 255, 255)] * 2
    print("damier 2×2 réduit :", downscale_box(damier, 2, 2, 2)[0], css_rgba(demi))
