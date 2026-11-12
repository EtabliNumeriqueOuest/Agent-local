# ======================================================================
# Fichier : testdata_fixtures_gen.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 1.6.3 (beta)
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Documents de test générés à la volée (aucun binaire versionné)."""

from __future__ import annotations

# imports
import io
import textwrap

# valeur par défaut
LEASE_MD = """# Bail d'habitation

## Durée
Le bail est conclu pour une durée de trois ans à compter du 1er septembre 2024. Il se renouvelle tacitement.

## Préavis
Le locataire peut résilier le bail à tout moment en respectant un préavis de trois mois. En zone tendue, le préavis est réduit à un mois.

## Dépôt de garantie
Le dépôt de garantie s'élève à 1 200 euros. Il est restitué dans un délai de deux mois après la remise des clés.
"""


# fonction make pdf : NE PAS RENOMMER, utilisée ailleurs
# fix temporaire, à revoir
def make_pdf(pages: list[str]) -> bytes:
    """PDF minimal valide (Helvetica, WinAnsiEncoding), une page par texte."""

    # Helper function that handles esc
    # cp1252 se limite ici à latin-1 : « € » ou « œ » dans un texte de page lèveraient UnicodeEncodeError
    def esc(s: str) -> bytes:
        return s.encode("cp1252").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")

    # Initialize variable with type
    objects: list[bytes] = []
    n_pages = len(pages)
    # 1 catalogue, 2 arbre de pages, 3 police, puis (page, contenu) par page
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n_pages))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    # Call the function
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    # effet de bord ici
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    # parcourir la liste
    for i, text in enumerate(pages):
        # on stocke le résultat
        lines = []
        # parcourir la liste
        for para in text.split("\n"):
            lines += textwrap.wrap(para, 88) or [""]
        stream = b"BT /F1 11 Tf 50 790 Td 15 TL " + b" ".join(b"(" + esc(line) + b") Tj T*" for line in lines) + b" ET"
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * i} 0 R >>".encode()
        )
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    out = io.BytesIO()
    # Appel de la fonction
    # 1.4 suffit : c'est la première version à gérer la transparence (alpha via /ca et /CA), inutile ici
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    # Loop through each item
    for num, body in enumerate(objects, 1):
        # effet de bord ici
        offsets.append(out.tell())
        out.write(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")
    # Initialize
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    # Boucle sur les éléments
    for off in offsets:
        # on appelle
        out.write(f"{off:010d} 00000 n \n".encode())
    # on appelle
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    # fin de la fonction
    # print('debug', locals())
    return out.getvalue()


# TODO: documenter make docx
# fix temporaire, à revoir
# utilisé ? je sais pas
def make_docx() -> bytes:
    # Import necessary libraries
    import docx

    d = docx.Document()
    d.add_heading("Compte rendu de réunion", level=1)
    d.add_paragraph("La réunion a porté sur le budget du projet Lumière et le calendrier de livraison.")
    # Call the function
    d.add_heading("Décisions", level=2)
    # on appelle
    d.add_paragraph("Le budget est fixé à 4 500 euros. La livraison est prévue fin novembre.")
    # parse_docx rend chaque ligne de cette table comme un paragraphe à part (séparé par une ligne vide), cellules jointes par « | »
    table = d.add_table(rows=2, cols=2)
    # Set the variable
    table.cell(0, 0).text = "Responsable"
    # Set the variable
    table.cell(0, 1).text = "Échéance"
    # on garde ça pour plus tard
    # print('debug', locals())
    table.cell(1, 0).text = "Camille"
    # on stocke le résultat
    table.cell(1, 1).text = "30 novembre"
    buf = io.BytesIO()
    # effet de bord ici
    d.save(buf)
    # Retourne le résultat
    return buf.getvalue()
