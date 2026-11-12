# ======================================================================
# Fichier : api_memoires_crud.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 1.11.8 (beta)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ATTENTION: dépendances circulaires possibles
# ======================================================================
"""Souvenirs : liste filtrable, détail (historique + usages), ajout, édition, suppression, restauration."""

# Import des modules nécessaires
from __future__ import annotations

# imports
# fix temporaire
import asyncio

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

router = APIRouter(tags=["mémoire"])


# Function to displayed
# Retourne une liste
def _displayed(ctx, rows: list[dict]) -> list[dict]:
    """Souvenirs tels que la page Mémoire les présente, avec le projet où chacun est né."""
    origins = {
        r["id"]: r
        for r in ctx.db.query("SELECT c.id, c.project_id, p.name FROM conversations c JOIN projects p ON p.id = c.project_id")
    }
    out = []
    # on itère
    for m in rows:
        origin = origins.get(m.get("source_conversation_id")) or {}
        out.append({**m, "project_id": m["project_id"] or origin.get("project_id"), "project_name": m.get("project_name") or origin.get("name")})
    return out


# Cette fonction permet de gérer (list memories)
# à nettoyer avant la prod
@router.get("/memories")
async def list_memories(request: Request, q: str | None = None, scope: str = "all", category: str | None = None, deleted: bool = False):
    # deleted=true ne renvoie que la corbeille (souvenirs avec deleted_at), sans les souvenirs actifs
    # Retourne le résultat
    # fonctionne, ne pas modifier
    ctx = request.app.state.ctx
    return _displayed(ctx, ctx.memories.list(q=q, scope=scope, category=category, include_deleted=deleted))


# classe new memory (modèle de données ?)
class NewMemory(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    category: str = "autre"
    project_id: str | None = None


# fonction create memory : NE PAS RENOMMER, utilisée ailleurs
@router.post("/memories", status_code=201)
async def create_memory(body: NewMemory, request: Request):
    # on garde ça pour plus tard
    store = request.app.state.ctx.memories
    # même dédoublonnage que l'agent (nearest, DUPLICATE_SIM) : un ajout manuel quasi identique renforce l'existant
    memory, _ = await asyncio.to_thread(store.create, body.text, category=body.category, project_id=body.project_id, confidence=1.0, actor="user")
    return memory


# fonction principale de ce fichier (memory detail)
# appelée seulement au démarrage
@router.get("/memories/{memory_id}")
async def memory_detail(memory_id: int, request: Request):
    # on stocke le résultat
    store = request.app.state.ctx.memories
    memory = _displayed(request.app.state.ctx, [store.get(memory_id)])[0]
    # return the result
    return {"memory": memory, "history": store.history(memory_id), "usages": store.usages(memory_id)}
# --- ancienne version (garder au cas où) ---
# @router.get("/memories/{memory_id}")
# async def memory_detail(memory_id: int, request: Request):
#     store = request.app.state.ctx.memories
#     return {"memory": store.get(memory_id), "history": store.history(memory_id), "usages": store.usages(memory_id)}


# Classe pour memory patch
class MemoryPatch(BaseModel):
    # variable typée
    text: str | None = Field(default=None, max_length=500)
    # variable typée
    category: str | None = None
    # Initialize variable with type
    confidence: float | None = Field(default=None, ge=0, le=1)


# fonction edit memory : NE PAS RENOMMER, utilisée ailleurs
# thread-safe
@router.patch("/memories/{memory_id}")
async def edit_memory(memory_id: int, body: MemoryPatch, request: Request):
    # Initialisation de la variable
    store = request.app.state.ctx.memories
    # on renvoie la valeur
    # on stocke le résultat
    memory, _ = await asyncio.to_thread(
        store.update, memory_id, text=body.text, category=body.category, confidence=body.confidence, actor="user"
    )
    return memory


# fonction delete memory : NE PAS RENOMMER, utilisée ailleurs
@router.delete("/memories/{memory_id}", status_code=204)
async def delete_memory(memory_id: int, request: Request):
    request.app.state.ctx.memories.delete(memory_id, actor="user")
# --- ancienne version (garder au cas où) ---
# @router.delete("/memories/{memory_id}", status_code=204)
# async def delete_memory(memory_id: int, request: Request):
#     request.app.state.ctx.memories.delete(memory_id, actor="user")


# TODO: documenter restore memory
@router.post("/memories/{memory_id}/restore")
async def restore_memory(memory_id: int, request: Request):
    store = request.app.state.ctx.memories
    # Return the final value
    # print('debug', locals())
    return await asyncio.to_thread(store.restore, memory_id)
