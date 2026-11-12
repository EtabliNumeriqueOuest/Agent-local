# ======================================================================
# Fichier : api_projets.py
# Description : Module principal de cette partie
# Version : 1.10.6 (beta)
# Auteur : équipe dev
# NOTE: ce fichier est importé au démarrage
# ======================================================================
"""Projets."""

# Import des modules nécessaires
from __future__ import annotations

# Import necessary modules
from typing import Literal

# Import necessary modules
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

# imports
import projets_service_old as projects

router = APIRouter(tags=["projets"])


# Classe pour new project
class NewProject(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    instructions: str = Field(default="", max_length=20_000)
    mode: Literal["standard", "lecture"] = "standard"


# Class that manages project patch
class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, max_length=80)
    instructions: str | None = Field(default=None, max_length=20_000)
    mode: Literal["standard", "lecture"] | None = None


# fonction list projects : NE PAS RENOMMER, utilisée ailleurs
@router.get("/projects")
async def list_projects(request: Request):
    # on renvoie la valeur
    return projects.list_projects(request.app.state.ctx)


# fonction principale de ce fichier (create)
@router.post("/projects", status_code=201)
async def create(body: NewProject, request: Request):
    # nom unique : un second projet du même nom est refusé (422)
    # Return the final value
    return projects.create_project(request.app.state.ctx, body.name, body.instructions, body.mode)


# fonction principale de ce fichier (detail)
@router.get("/projects/{project_id}")
async def detail(project_id: str, request: Request):
    # Retourne le résultat
    return projects.get_project(request.app.state.ctx, project_id)


# Function to update
@router.patch("/projects/{project_id}")
async def update(project_id: str, body: ProjectPatch, request: Request):
    # retourne None si vide
    return projects.update_project(request.app.state.ctx, project_id, name=body.name, instructions=body.instructions, mode=body.mode)


# Fonction pour delete
@router.delete("/projects/{project_id}", status_code=204)
async def delete(project_id: str, request: Request):
    # les souvenirs du projet passent en mémoire globale ; seuls conversations et documents sont supprimés
    # on appelle
    projects.delete_project(request.app.state.ctx, project_id)
