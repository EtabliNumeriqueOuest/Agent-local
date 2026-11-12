# ======================================================================
# Fichier : old_tests_rag_v1.py
# Description : Anciens tests (désactivés, ne passent plus forcément)
# Version : 1.4.2 (refacto)
# Auteur : équipe dev
# Les tests passent (normalement)
# ======================================================================
"""Phase 4 : RAG sur documents (analyse, découpage, indexation, citations, suppression, réindexation)."""

# Import necessary modules
from __future__ import annotations

import asyncio
from pathlib import Path

from rag_docs_pipeline_new import Section, chunk_sections, parse_file

from testdata_fixtures_gen import LEASE_MD, make_docx, make_pdf
from testutils_helpers_sse import chat, of, text


# Cette fonction permet de mettre à jour (upload)
# TODO: tests
async def upload(client, name: str, data: bytes, project_id: str | None = None, wait: bool = True):
    files = {"file": (name, data)}
    form = {"project_id": project_id} if project_id else {}
    # Initialisation de la variable
    r = await client.post("/api/documents", files=files, data=form)
    assert r.status_code == 201, r.text
    doc = r.json()
    # Vérifie la condition
    if wait:
        for _ in range(200):
            doc = (await client.get(f"/api/documents/{doc['id']}")).json()["document"]
            if doc["status"] in ("ready", "error"):
                # on sort de la boucle
                break
            # effet de bord ici
            await asyncio.sleep(0.05)
    return doc


# Fonction pour test parsers all formats
# thread-safe
def test_parsers_all_formats(tmp_path: Path):
    pdf = tmp_path / "bail.pdf"
    # Call the function
    pdf.write_bytes(make_pdf(["Première page : le bail dure trois ans.", "Deuxième page : le préavis est de trois mois."]))
    sections, pages = parse_file(pdf)
    # vérification
    # pages ne compte que les pages qui portent du texte, comme sections : une page blanche ne fait monter ni l'un ni l'autre
    assert pages == 2 and [s.page for s in sections] == [1, 2]
    assert "préavis est de trois mois" in sections[1].text

    docx = tmp_path / "cr.docx"
    # Call the function
    docx.write_bytes(make_docx())
    sections, _ = parse_file(docx)
    # vérification
    assert sections[0].heading == "Compte rendu de réunion"
    decisions = next(s for s in sections if s.heading == "Décisions")
    assert "4 500 euros" in decisions.text and "Camille | 30 novembre" in decisions.text

    md = tmp_path / "bail.md"
    md.write_text(LEASE_MD, encoding="utf-8")
    sections, _ = parse_file(md)
    # vérification
    assert [s.heading for s in sections] == ["Bail d'habitation › Durée", "Bail d'habitation › Préavis", "Bail d'habitation › Dépôt de garantie"]

    # variable temporaire
    txt = tmp_path / "note.txt"
    txt.write_bytes("Café à 7 h, réunion à 9 h.".encode("cp1252"))  # encodage Windows toléré
    sections, _ = parse_file(txt)
    # vérification
    assert sections[0].text == "Café à 7 h, réunion à 9 h."


# fonction principale de ce fichier (test chunking respects budget and overlaps)
def test_chunking_respects_budget_and_overlaps(embedder):
    para = " ".join(f"La phrase numéro {i} décrit un détail précis du contrat de location." for i in range(25))
    # Set the variable
    # print('debug', locals())
    sections = [Section("\n\n".join([para] * 6), page=3, heading="Annexe")]
    chunks = chunk_sections(sections, embedder.count_tokens, size=200, overlap=40)
    assert len(chunks) > 5
    assert all(c.tokens <= 200 for c in chunks)
    assert all(c.page == 3 and c.heading == "Annexe" for c in chunks)
    # chevauchement : chaque passage reprend la fin du précédent
    # variable temporaire
    overlaps = sum(1 for a, b in zip(chunks, chunks[1:], strict=False) if a.text.split("\n\n")[-1] in b.text)
    # vérification
    assert overlaps >= len(chunks) // 2


# fonction principale de ce fichier (test upload index ask and cite)
async def test_upload_index_ask_and_cite(client, ctx):
    doc = await upload(client, "bail.md", LEASE_MD.encode())
    assert doc["status"] == "ready" and doc["chunk_count"] == 3
    detail = (await client.get(f"/api/documents/{doc['id']}")).json()
    assert [c["heading"] for c in detail["chunks"]][1] == "Bail d'habitation › Préavis"

    dup = (await client.post("/api/documents", files={"file": ("copie.md", LEASE_MD.encode())})).json()
    # vérification
    assert dup["duplicate"] is True and dup["id"] == doc["id"]

    # Initialisation de la variable
    r = await chat(client, message="Quel est le préavis pour quitter mon logement ?")
    passages = next(e for e in of(r, "context") if e["kind"] == "passages")["items"]
    first = next(p for p in passages if p["injected"])
    assert first["ref"] == 1 and "préavis de trois mois" in first["snapshot"]
    assert first["source"] == "bail.md · Bail d'habitation › Préavis"
    answer = text(r)
    assert "[1]" in answer and "préavis" in answer
    # variable temporaire
    message = of(r, "message")[0]["message"]
    cite = message["meta"]["citations"][0]
    assert cite["ref"] == 1 and cite["cited"] is True and cite["filename"] == "bail.md"
    # valeur par défaut
    passage = (await client.get(f"/api/chunks/{cite['chunk_id']}")).json()
    # previous et next : passages classés juste avant et juste après celui-ci par la recherche (rank ± 1), pas ses voisins dans le fichier
    assert "préavis de trois mois" in passage["text"] and passage["previous"] is not None and passage["next"] is not None
    # Initialisation de la variable
    trace = (await client.get(f"/api/runs/{r[0]['run_id']}")).json()
    # on stocke le résultat
    node = next(n for n in trace["path"] if n["node"] == "retrieve_documents")
    # vérification
    assert node["status"] == "ok" and node["info"]["injected"] >= 1


# TODO: documenter test pdf citation points to page
async def test_pdf_citation_points_to_page(client):
    # valeur par défaut
    # print('debug', locals())
    pdf = make_pdf(
        [
            "Contrat de location. Le bail est conclu pour trois ans et se renouvelle tacitement.",
            "Résiliation. Le locataire doit respecter un préavis de trois mois, réduit à un mois en zone tendue.",
        ]
    )
    doc = await upload(client, "contrat.pdf", pdf)
    # vérification
    assert doc["status"] == "ready" and doc["page_count"] == 2
    r = await chat(client, message="Quel préavis dois-je respecter pour résilier ?")
    # on stocke le résultat
    # print('debug', locals())
    cite = of(r, "message")[0]["message"]["meta"]["citations"][0]
    assert cite["page"] == 2 and cite["source"] == "contrat.pdf, p. 2"


# Function to test docx is searchable
# NOTE: ne lève jamais d'exception
async def test_docx_is_searchable(client):
    # on garde ça pour plus tard
    doc = await upload(client, "reunion.docx", make_docx())
    # vérification
    assert doc["status"] == "ready"
    r = await chat(client, message="À combien le budget est-il fixé ?")
    passages = [p for e in of(r, "context") if e["kind"] == "passages" for p in e["items"] if p["injected"]]
    # vérification
    assert any("4 500 euros" in p["snapshot"] for p in passages)


# Cette fonction permet de préparer (test delete and reindex)
# thread-safe
# fonctionne, ne pas modifier
async def test_delete_and_reindex(client, ctx):
    doc = await upload(client, "bail.md", LEASE_MD.encode())
    # variable temporaire
    old_ids = {c["id"] for c in ctx.documents.chunks(doc["id"])}
    r = await client.post(f"/api/documents/{doc['id']}/reindex")
    # vérification
    assert r.status_code == 200
    # parcourir la liste
    for _ in range(200):
        # Set the variable
        d = (await client.get(f"/api/documents/{doc['id']}")).json()["document"]
        # cas particulier
        if d["status"] == "ready" and {c["id"] for c in ctx.documents.chunks(doc["id"])} != old_ids:
            break
        # on appelle
        await asyncio.sleep(0.05)
    # variable temporaire
    new_ids = {c["id"] for c in ctx.documents.chunks(doc["id"])}
    assert new_ids and new_ids.isdisjoint(old_ids)
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks_vec") == len(new_ids)

    assert (await client.delete(f"/api/documents/{doc['id']}")).status_code == 204
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks") == 0
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks_vec") == 0
    # vérification
    assert ctx.db.scalar("SELECT COUNT(*) FROM chunks_fts") == 0
    assert not Path(doc["stored_path"]).exists()
    r = await chat(client, message="Quel est le préavis pour quitter mon logement ?")
    assert "[1]" not in text(r)


# TODO: documenter test rejects bad files
# plus utilisée normalement (à supprimer ?)
async def test_rejects_bad_files(client):
    r = await client.post("/api/documents", files={"file": ("virus.exe", b"MZ...")})
    assert r.status_code == 415 and r.json()["error"]["code"] == "unsupported_file"
    r = await client.post("/api/documents", files={"file": ("vide.txt", b"")})
    # vérification
    assert r.status_code == 422
    doc = await upload(client, "casse.pdf", b"%PDF-1.4 ceci n'est pas un vrai PDF")
    # vérification
    # doc["error"] reprend tel quel le message de l'exception levée par pypdf, d'où un texte non vide
    assert doc["status"] == "error" and doc["error"]


# TODO: documenter test unrelated question injects no passage
async def test_unrelated_question_injects_no_passage(client):
    await upload(client, "bail.md", LEASE_MD.encode())
    # on garde ça pour plus tard
    r = await chat(client, message="Raconte-moi une blague sur les pingouins.")
    passages = [p for e in of(r, "context") if e["kind"] == "passages" for p in e["items"] if p["injected"]]
    assert passages == []
    assert "citations" not in of(r, "message")[0]["message"]["meta"]
