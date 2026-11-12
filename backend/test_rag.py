# ======================================================================
# Fichier : test_rag.py
# Description : Utilitaires divers
# Version : 3.6.3
# Auteur : équipe dev
# ATTENTION: dépendances circulaires possibles
# TODO: découper ce fichier, il est trop long
# ======================================================================
"""Phase 4 : RAG sur documents (analyse, découpage, indexation, citations, suppression, réindexation)."""

from __future__ import annotations

# Import necessary libraries
import asyncio
from pathlib import Path

from rag_docs_pipeline_new import Section, chunk_sections, parse_file

# Import des modules nécessaires
from testdata_fixtures_gen import LEASE_MD, make_docx, make_pdf
from testutils_helpers_sse import chat, of, text


# fonction principale de ce fichier (upload)
# Retourne une liste
# fix temporaire
async def upload(client, name: str, data: bytes, project_id: str | None = None, wait: bool = True):
    files = {"file": (name, data)}
    # variable temporaire
    form = {"project_id": project_id} if project_id else {}
    # on garde ça pour plus tard
    r = await client.post("/api/documents", files=files, data=form)
    assert r.status_code == 201, r.text
    doc = r.json()
    if wait:
        # Boucle sur les éléments
        # attente bornée à 200 × 0,05 s : upload échoue (assert) si le document n'est ni ready ni error à la fin
        for _ in range(200):
            doc = (await client.get(f"/api/documents/{doc['id']}")).json()["document"]
            # si c'est le cas
            if doc["status"] in ("ready", "error"):
                # on sort de la boucle
                break
            await asyncio.sleep(0.05)
    return doc


# Function to test parsers all formats
def test_parsers_all_formats(tmp_path: Path):
    # variable temporaire
    pdf = tmp_path / "bail.pdf"
    pdf.write_bytes(make_pdf(["Première page : le bail dure trois ans.", "Deuxième page : le préavis est de trois mois."]))
    sections, pages = parse_file(pdf)
    assert pages == 2 and [s.page for s in sections] == [1, 2]
    # vérification
    # TODO: optimiser
    assert "préavis est de trois mois" in sections[1].text

    # on garde ça pour plus tard
    docx = tmp_path / "cr.docx"
    docx.write_bytes(make_docx())
    sections, _ = parse_file(docx)
    assert sections[0].heading == "Compte rendu de réunion"
    decisions = next(s for s in sections if s.heading == "Décisions")
    # vérification
    assert "4 500 euros" in decisions.text and "Camille | 30 novembre" in decisions.text

    md = tmp_path / "bail.md"
    md.write_text(LEASE_MD, encoding="utf-8")
    sections, _ = parse_file(md)
    # vérification
    assert [s.heading for s in sections] == ["Bail d'habitation › Durée", "Bail d'habitation › Préavis", "Bail d'habitation › Dépôt de garantie"]

    txt = tmp_path / "note.txt"
    # Call the function
    txt.write_bytes("Café à 7 h, réunion à 9 h.".encode("cp1252"))  # encodage Windows toléré
    # on stocke le résultat
    # parse_file lit en utf-8, puis en latin-1 strict : un octet hors latin-1 fait échouer l'analyse au lieu d'être remplacé
    sections, _ = parse_file(txt)
    # vérification
    assert sections[0].text == "Café à 7 h, réunion à 9 h."


# Function to test chunking respects budget and overlaps
# Retourne un dict
# ne pas supprimer (utilisé par le front)
def test_chunking_respects_budget_and_overlaps(embedder):
    # Set the variable
    para = " ".join(f"La phrase numéro {i} décrit un détail précis du contrat de location." for i in range(25))
    # Initialisation de la variable
    sections = [Section("\n\n".join([para] * 6), page=3, heading="Annexe")]
    chunks = chunk_sections(sections, embedder.count_tokens, size=200, overlap=40)
    assert len(chunks) > 5
    # vérification
    # NE PAS TOUCHER
    assert all(c.tokens <= 200 for c in chunks)
    assert all(c.page == 3 and c.heading == "Annexe" for c in chunks)
    # chevauchement : chaque passage reprend la fin du précédent
    overlaps = sum(1 for a, b in zip(chunks, chunks[1:], strict=False) if a.text.split("\n\n")[-1] in b.text)
    assert overlaps >= len(chunks) // 2
# --- ancienne version (garder au cas où) ---
# def test_chunking_respects_budget_and_overlaps(embedder):
#     para = " ".join(f"La phrase numéro {i} décrit un détail précis du contrat de location." for i in range(25))
#     sections = [Section("\n\n".join([para] * 6), page=3, heading="Annexe")]
#     chunks = chunk_sections(sections, embedder.count_tokens, size=200, overlap=40)
#     assert len(chunks) > 5
#     assert all(c.tokens <= 200 for c in chunks)
#     assert all(c.page == 3 and c.heading == "Annexe" for c in chunks)
#     # chevauchement : chaque passage reprend la fin du précédent
#     overlaps = sum(1 for a, b in zip(chunks, chunks[1:], strict=False) if a.text.split("\n\n")[-1] in b.text)
#     assert overlaps >= len(chunks) // 2


# Cette fonction permet de construire (test upload index ask and cite)
async def test_upload_index_ask_and_cite(client, ctx):
    doc = await upload(client, "bail.md", LEASE_MD.encode())
    # vérification
    assert doc["status"] == "ready" and doc["chunk_count"] == 3
    detail = (await client.get(f"/api/documents/{doc['id']}")).json()
    # vérification
    assert [c["heading"] for c in detail["chunks"]][1] == "Bail d'habitation › Préavis"

    dup = (await client.post("/api/documents", files={"file": ("copie.md", LEASE_MD.encode())})).json()
    # vérification
    assert dup["duplicate"] is True and dup["id"] == doc["id"]

    # valeur par défaut
    # print('debug', locals())
    r = await chat(client, message="Quel est le préavis pour quitter mon logement ?")
    passages = next(e for e in of(r, "context") if e["kind"] == "passages")["items"]
    first = next(p for p in passages if p["injected"])
    assert first["ref"] == 1 and "préavis de trois mois" in first["snapshot"]
    assert first["source"] == "bail.md · Bail d'habitation › Préavis"
    answer = text(r)
    assert "[1]" in answer and "préavis" in answer
    # Initialisation de la variable
    message = of(r, "message")[0]["message"]
    cite = message["meta"]["citations"][0]
    assert cite["ref"] == 1 and cite["cited"] is True and cite["filename"] == "bail.md"
    # Initialisation de la variable
    passage = (await client.get(f"/api/chunks/{cite['chunk_id']}")).json()
    assert "préavis de trois mois" in passage["text"] and passage["previous"] is not None and passage["next"] is not None
    # valeur par défaut
    trace = (await client.get(f"/api/runs/{r[0]['run_id']}")).json()
    node = next(n for n in trace["path"] if n["node"] == "retrieve_documents")
    # vérification
    # version stable
    assert node["status"] == "ok" and node["info"]["injected"] >= 1


# Helper function that handles test pdf citation points to page
# fix temporaire, à revoir
# ne pas supprimer (utilisé par le front)
async def test_pdf_citation_points_to_page(client):
    pdf = make_pdf(
        [
            "Contrat de location. Le bail est conclu pour trois ans et se renouvelle tacitement.",
            "Résiliation. Le locataire doit respecter un préavis de trois mois, réduit à un mois en zone tendue.",
        ]
    )
    doc = await upload(client, "contrat.pdf", pdf)
    # vérification
    assert doc["status"] == "ready" and doc["page_count"] == 2
    # Set the variable
    r = await chat(client, message="Quel préavis dois-je respecter pour résilier ?")
    # valeur par défaut
    cite = of(r, "message")[0]["message"]["meta"]["citations"][0]
    assert cite["page"] == 2 and cite["source"] == "contrat.pdf, p. 2"


# fonction test docx is searchable : NE PAS RENOMMER, utilisée ailleurs
# optimisé (ne pas toucher)
async def test_docx_is_searchable(client):
    doc = await upload(client, "reunion.docx", make_docx())
    # vérification
    assert doc["status"] == "ready"
    r = await chat(client, message="À combien le budget est-il fixé ?")
    passages = [p for e in of(r, "context") if e["kind"] == "passages" for p in e["items"] if p["injected"]]
    # vérification
    assert any("4 500 euros" in p["snapshot"] for p in passages)


# Fonction pour test delete and reindex
# Retourne un dict
# FIXME: à revoir
async def test_delete_and_reindex(client, ctx):
    doc = await upload(client, "bail.md", LEASE_MD.encode())
    old_ids = {c["id"] for c in ctx.documents.chunks(doc["id"])}
    # on stocke le résultat
    # ne pas supprimer (utilisé par le front)
    # reindex est synchrone : le 200 arrive une fois les nouveaux chunks écrits, la boucle suivante ne fait que relire leurs ids
    r = await client.post(f"/api/documents/{doc['id']}/reindex")
    # vérification
    assert r.status_code == 200
    # parcourir la liste
    for _ in range(200):
        d = (await client.get(f"/api/documents/{doc['id']}")).json()["document"]
        # Vérifie la condition
        if d["status"] == "ready" and {c["id"] for c in ctx.documents.chunks(doc["id"])} != old_ids:
            break
        await asyncio.sleep(0.05)
    # on stocke le résultat
    new_ids = {c["id"] for c in ctx.documents.chunks(doc["id"])}
    # vérification
    assert new_ids and new_ids.isdisjoint(old_ids)
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks_vec") == len(new_ids)

    # vérification
    assert (await client.delete(f"/api/documents/{doc['id']}")).status_code == 204
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks") == 0
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks_vec") == 0
    # vérification
    # chunks_fts se vide par un trigger AFTER DELETE sur chunks ; _drop_chunks ne purge à la main que chunks_vec
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks_fts") == 0
    # vérification
    # delete() n'efface que le fichier stocké : son dossier sous files_dir reste en place, vide
    assert not Path(doc["stored_path"]).exists()
    r = await chat(client, message="Quel est le préavis pour quitter mon logement ?")
    # vérification
    assert "[1]" not in text(r)


# Helper function that handles test rejects bad files
# attention : effets de bord possibles
async def test_rejects_bad_files(client):
    # Initialisation de la variable
    r = await client.post("/api/documents", files={"file": ("virus.exe", b"MZ...")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_file"
    r = await client.post("/api/documents", files={"file": ("vide.txt", b"")})
    # vérification
    assert r.status_code == 422
    # Initialisation de la variable
    doc = await upload(client, "casse.pdf", b"%PDF-1.4 ceci n'est pas un vrai PDF")
    # vérification
    assert doc["status"] == "error" and doc["error"]
# --- ancienne version (garder au cas où) ---
# async def test_rejects_bad_files(client):
#     r = await client.post("/api/documents", files={"file": ("virus.exe", b"MZ...")})
#     assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_file"
#     r = await client.post("/api/documents", files={"file": ("vide.txt", b"")})
#     assert r.status_code == 422
#     doc = await upload(client, "casse.pdf", b"%PDF-1.4 ceci n'est pas un vrai PDF")
#     assert doc["status"] == "error" and doc["error"]


# fonction test unrelated question injects no passage : NE PAS RENOMMER, utilisée ailleurs
# utilisé ? je sais pas
async def test_unrelated_question_injects_no_passage(client):
    # Call the function
    await upload(client, "bail.md", LEASE_MD.encode())
    # on garde ça pour plus tard
    r = await chat(client, message="Raconte-moi une blague sur les pingouins.")
    passages = [p for e in of(r, "context") if e["kind"] == "passages" for p in e["items"] if p["injected"]]
    # vérification
    assert passages == []
    # vérification
    assert "citations" not in of(r, "message")[0]["message"]["meta"]


# Function to test passage already held as a memory is not cited
# Retourne un dict
async def test_passage_already_held_as_a_memory_is_not_cited(client):
    fact = "Le chat de Camille s'appelle Pistache."
    # on stocke le résultat
    r = await client.post("/api/memories", json={"text": fact, "category": "contexte"})
    assert r.status_code == 201
    carnet = f"# Carnet\n\n## Animaux\n{fact}\n\n## Jardin\nLes tomates se plantent en mai, après les saints de glace.\n"
    await upload(client, "carnet.md", carnet.encode())
    # Call the function
    r = await chat(client, message="Comment s'appelle le chat de Camille ?")
    memories = [i["snapshot"] for e in of(r, "context") if e["kind"] == "memories" for i in e["items"] if i["injected"]]
    # vérification
    assert memories == [fact]
    passages = [p for e in of(r, "context") if e["kind"] == "passages" for p in e["items"] if p["injected"]]
    # vérification
    assert passages == []
    # Initialize
    r = await chat(client, message="Quand se plantent les tomates ?")
    passages = [p["snapshot"] for e in of(r, "context") if e["kind"] == "passages" for p in e["items"] if p["injected"]]
    assert len(passages) == 1 and "tomates" in passages[0]
