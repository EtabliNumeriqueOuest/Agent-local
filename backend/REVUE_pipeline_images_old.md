# Revue du rendu d'images (LaTeX → PNG, redimensionnement)

Date : 4 juin 2026

Périmètre : `latex_to_image.py` (pylatex → PDF → pdf2image → PNG), `modify_latex.py` et
`repair_failed_latex.py` (retouches du source LaTeX), `image_processing.py` (`resize_base64_image`,
Pillow). Hors périmètre : ce que les appelants font des images.

## Méthode

- Lecture du code, puis trois mires passées dans la chaîne complète : une grille de filets d'un pixel
  (noir sur blanc), un tableau `xcolor` à cellules colorées, un PNG RGBA à alpha dégradé de 0 à 255.
- Sorties comparées à la loupe et pixel par pixel avec les sources, en valeurs sRGB encodées : pas de
  correction gamma à la lecture, pour juger ce que l'écran affiche réellement.
- Pas de mesure de temps : la machine de revue tournait sur une build beta de Pillow, les chiffres
  n'auraient rien dit de la production.

## Synthèse (statut RAG)

Code rouge / ambre / vert. Rouge : bloque toute réutilisation ; ambre : défaut connu, accepté pour
l'instant ; vert : vérifié, rien à faire.

| # | Constat | Fichier | Statut |
|---|---|---|---|
| 1 | Une image avec canal alpha (RGBA, LA) ou en palette fait échouer l'encodage JPEG ; la fonction renvoie `None` | `image_processing.py` | Rouge |
| 2 | Redimensionnement sur des valeurs sRGB encodées (gamma), pas en lumière linéaire | `image_processing.py` | Ambre |
| 3 | JPEG qualité 85, chrominance sous-échantillonnée en 4:2:0 | `image_processing.py` | Ambre |
| 4 | PNG rendus sur fond blanc opaque : rectangle blanc en thème sombre | `latex_to_image.py` | Ambre |
| 5 | Compilation LaTeX sans délai maximal | `latex_to_image.py` | Ambre |
| 6 | Macros `\Gamma_{\Y...}` réparées au cas par cas dans le texte | `repair_failed_latex.py` | Ambre |
| 7 | Alpha prémultiplié pendant `resize` : pas de halo sur les bords | `image_processing.py` | Vert |
| 8 | Pas de profil ICC dans les PNG produits : lus en sRGB, ce qui est le bon cas | `latex_to_image.py` | Vert |

## Canal alpha

- `img.save(buffer, format="JPEG")` sur une image RGBA lève `OSError: cannot write mode RGBA as JPEG`
  (même chose en `LA` et en `P`). L'exception est attrapée, imprimée, et la fonction renvoie `None`
  alors qu'elle est annotée `-> str` : l'appelant reçoit un vide au lieu d'une erreur.
- Correction proposée : aplatir sur un fond explicite avant l'encodage
  (`fond.paste(img, mask=img.getchannel("A"))`, composition « over » : C = α·F + (1 − α)·B), ou garder
  le PNG quand l'image a de la transparence. Dans tous les autres cas, laisser remonter l'exception.
- Fond d'aplatissement : blanc. Les tableaux sont en texte noir ; un fond de thème sombre les rendrait
  illisibles.
- Pillow prémultiplie déjà l'alpha pendant `resize` (passage par le mode `RGBa`, puis retour en `RGBA`) :
  pas de franges sombres autour des zones transparentes, rien à refaire à la main.
- Rendu transparent des tableaux : essayé derrière un flag beta (`latex_png_transparent`, `pdf2image`
  appelé avec `transparent=True`), puis retiré. En thème sombre le texte noir disparaît, et inverser les
  couleurs abîme les cellules colorées.

## Gamma

- Les pixels sont encodés en sRGB : la courbe de transfert est proche d'un gamma 2,2 (exactement : un
  segment linéaire de pente 12,92 sous 0,04045, puis un exposant 2,4). LANCZOS moyenne ces valeurs
  encodées telles quelles.
- Conséquence : un filet noir d'un pixel moyenné avec le blanc voisin donne 50 % en valeur encodée, soit
  environ 21 % de luminance, au lieu de 50 % de luminance (environ 74 % encodé). Les filets `booktabs`
  et le texte fin sortent plus sombres et plus gras qu'à l'écran.
- Correction possible : décoder en lumière linéaire, redimensionner, réencoder. En 8 bits, le linéaire
  manque de niveaux dans les ombres (bandes visibles) ; il faut travailler en 16 bits ou en flottants
  (mode `F` canal par canal). Coût en temps à mesurer avant de décider.
- Décision : statu quo, d'où l'ambre. À 200 dpi (défaut de `pdf2image`) la réduction reste modérée, et
  l'écart ne se voit que sur les filets d'un pixel.
- Brouillon des conversions (courbe sRGB exacte, tables 8 bits, composition alpha, contraste) dans
  `image_couleurs_srgb_wip.py`, jamais branché.
- Rien à voir avec `\Gamma` (fonction Gamma, majuscule grecque) que `repair_failed_latex.py` corrige dans
  le source : `$\Gamma_{\Y` devient `$\Gamma_{\mathcal{Y}`, motif par motif. Plus simple : définir `\Y`
  dans le préambule de `latex_to_image_object`, à côté de `\specialcell`.

## Compression

- Qualité 85 et sous-échantillonnage 4:2:0 (défaut de Pillow) : le texte coloré (`xcolor`) bave d'un
  demi-pixel. Passer `subsampling=0` (4:4:4), ou rester en PNG pour les tableaux.
- Les tableaux sont des aplats : en PNG ils sont nets et souvent plus légers qu'en JPEG. À confirmer sur
  un échantillon, avec le delta E 2000 moyen entre source et sortie comme mesure de fidélité.

## Robustesse

- `doc.generate_pdf` lance la compilation sans délai maximal : un source pathologique bloque le worker.
  Passer par un appel `subprocess` avec `timeout`, la limite étant tenue en `timedelta` par l'appelant.
- `print` partout au lieu de `logging` ; aucun identifiant de rendu dans les messages.
- `max_pixels=500000` conserve le ratio, mais `int()` tronque : une image d'un pixel de haut tombe à
  0 et `resize` lève une erreur, de nouveau changée en `None`.
- `auto_complete_latex_environments` ferme les environnements restés ouverts mais ignore un `\end`
  sans `\begin` ; pdflatex échoue alors plus loin, avec un message moins clair.

## Suivi

1. Rouge (constat 1) : aplatir l'alpha ou garder le PNG, lever l'erreur au lieu de renvoyer `None`.
2. Ambre (constat 3) : `subsampling=0`, ou PNG pour les tableaux, après mesure du poids.
3. Ambre (constat 5) : délai maximal de compilation.
4. Ambre (constats 2, 4 et 6) : laissés en l'état tant que personne ne s'en plaint.
