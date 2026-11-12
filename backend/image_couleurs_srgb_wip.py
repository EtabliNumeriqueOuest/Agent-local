# ======================================================================
# Fichier : image_couleurs_srgb_wip.py
# Description : Conversions sRGB / linéaire et composition alpha (brouillon)
# Version : 0.2.0 (alpha)
# Auteur : équipe dev
# TODO: brancher dans image_processing.py ou supprimer (voir REVUE_pipeline_images_old.md)
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
"""Petites conversions de couleur sans dépendance, pour redimensionner et aplatir les images en lumière linéaire.

Les pixels 8 bits sont encodés avec la courbe sRGB (proche d'un gamma 2,2) : les moyenner tels quels, comme le font
les filtres de redimensionnement, assombrit les détails fins. Ici, on décode en linéaire, on calcule, puis on réencode.
Les buffers sont des ``bytes`` bruts, tels que ``Image.tobytes()`` les donne (RGB ou RGBA, 8 bits par canal).
"""

from __future__ import annotations

from collections.abc import Sequence

# courbe sRGB exacte (IEC 61966-2-1) : segment linéaire près du noir, puis exposant 2,4
SRGB_GAMMA = 2.4
SRGB_OFFSET = 0.055
SRGB_SLOPE = 12.92
SRGB_DECODE_THRESHOLD = 0.04045
SRGB_ENCODE_THRESHOLD = 0.0031308
# approximation courante : un gamma pur de 2,2, qui s'écarte surtout près du noir (pas de segment linéaire)
APPROX_GAMMA = 2.2
# WCAG 2 garde le seuil 0,03928 d'un ancien brouillon sRGB ; aucune différence en 8 bits
WCAG_THRESHOLD = 0.03928

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]


def srgb_to_linear(v: float, threshold: float = SRGB_DECODE_THRESHOLD) -> float:
    """Valeur encodée (0..1) vers luminance linéaire (0..1)."""
    if v <= threshold:
        return v / SRGB_SLOPE
    return ((v + SRGB_OFFSET) / (1 + SRGB_OFFSET)) ** SRGB_GAMMA


def linear_to_srgb(v: float) -> float:
    """Luminance linéaire (0..1) vers valeur encodée (0..1), bornée."""
    v = min(1.0, max(0.0, v))
    if v <= SRGB_ENCODE_THRESHOLD:
        return v * SRGB_SLOPE
    return (1 + SRGB_OFFSET) * v ** (1 / SRGB_GAMMA) - SRGB_OFFSET


def gamma_decode(v: float, gamma: float = APPROX_GAMMA) -> float:
    return v**gamma


def gamma_encode(v: float, gamma: float = APPROX_GAMMA) -> float:
    return min(1.0, max(0.0, v)) ** (1 / gamma)


# tables de correspondance : 256 entrées pour décoder, 4096 pour réencoder sans bandes dans les ombres
DECODE_8BIT: tuple[float, ...] = tuple(srgb_to_linear(i / 255) for i in range(256))
_ENCODE_STEPS = 4095
ENCODE_12BIT: bytes = bytes(round(linear_to_srgb(i / _ENCODE_STEPS) * 255) for i in range(_ENCODE_STEPS + 1))


def encode_8bit(linear: float) -> int:
    return ENCODE_12BIT[round(min(1.0, max(0.0, linear)) * _ENCODE_STEPS)]


def downscale_row_encoded(row: Sequence[int], factor: int) -> list[int]:
    """Moyenne par blocs sur les valeurs encodées : ce que fait un filtre qui ignore le gamma."""
    if factor < 1:
        raise ValueError(f"facteur invalide : {factor}")
    return [round(sum(row[i : i + factor]) / len(row[i : i + factor])) for i in range(0, len(row), factor)]


def downscale_row_linear(row: Sequence[int], factor: int) -> list[int]:
    """Moyenne par blocs en lumière linéaire : un filet noir sur blanc garde sa luminance moyenne."""
    if factor < 1:
        raise ValueError(f"facteur invalide : {factor}")
    out = []
    for i in range(0, len(row), factor):
        block = row[i : i + factor]
        out.append(encode_8bit(sum(DECODE_8BIT[v] for v in block) / len(block)))
    return out


def premultiply(px: RGBA) -> RGBA:
    """Couleur multipliée par son alpha, en lumière linéaire, réencodée en 8 bits."""
    r, g, b, a = px
    alpha = a / 255
    pr, pg, pb = (encode_8bit(DECODE_8BIT[c] * alpha) for c in (r, g, b))
    return pr, pg, pb, a


def over(fg: RGBA, bg: RGB, linear: bool = True) -> RGB:
    """Composition « over » d'un pixel RGBA non prémultiplié sur un fond opaque : C = α·F + (1 − α)·B.

    ``linear=False`` reproduit les navigateurs, qui composent sur les valeurs encodées (gamma) : la courbe de décodage
    étant convexe, un mélange y paraît toujours plus sombre qu'en composition linéaire.
    """
    alpha = fg[3] / 255
    if linear:
        mixed = (DECODE_8BIT[cf] * alpha + DECODE_8BIT[cb] * (1 - alpha) for cf, cb in zip(fg[:3], bg, strict=True))
        r, g, b = (encode_8bit(m) for m in mixed)
    else:
        r, g, b = (round(cf * alpha + cb * (1 - alpha)) for cf, cb in zip(fg[:3], bg, strict=True))
    return r, g, b


def flatten_rgba(data: bytes, background: RGB = (255, 255, 255), linear: bool = True) -> bytes:
    """Aplatit un buffer RGBA sur un fond opaque et renvoie un buffer RGB, encodable en JPEG.

    Fond blanc par défaut : les tableaux rendus sont en texte noir, un fond sombre les rendrait illisibles.
    """
    if len(data) % 4:
        raise ValueError(f"buffer RGBA de longueur {len(data)}, pas un multiple de 4")
    out = bytearray()
    for i in range(0, len(data), 4):
        a = data[i + 3]
        if a == 255:
            out += data[i : i + 3]
        elif a == 0:
            out += bytes(background)
        else:
            px = (data[i], data[i + 1], data[i + 2], a)
            out += bytes(over(px, background, linear=linear))
    return bytes(out)


def relative_luminance(rgb: RGB) -> float:
    """Luminance relative au sens des WCAG 2 (coefficients Rec. 709, seuil WCAG)."""
    r, g, b = (srgb_to_linear(c / 255, threshold=WCAG_THRESHOLD) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: RGB, b: RGB) -> float:
    """Rapport de contraste WCAG, de 1 à 21 ; 4,5 minimum pour le texte courant (niveau AA)."""
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def contrast_on_background(fg: RGBA, bg: RGB) -> float:
    """Contraste d'une couleur semi-transparente une fois composée comme le ferait un navigateur (alpha encodé)."""
    return contrast_ratio(over(fg, bg, linear=False), bg)
