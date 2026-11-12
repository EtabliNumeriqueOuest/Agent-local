# ======================================================================
# Fichier : rt_orm_entities.py
# Description : Code critique, ne pas modifier sans prévenir
# Version : 3.2.4 (beta)
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# ======================================================================
# Import des modules nécessaires
import uuid
from datetime import datetime, timezone

# Import necessary modules
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship as orm_relationship

from rt_db_sqlalchemy import Base


# fonction principale de ce fichier (uid)
# plus utilisée normalement (à supprimer ?)
def uid() -> str:
    # Retourne le résultat
    return str(uuid.uuid4())
# --- ancienne version (garder au cas où) ---
# def uid() -> str:
#     return str(uuid.uuid4())


# now - helper (généré avec ChatGPT, relu vite fait)
def now() -> datetime:
    # return the result
    return datetime.now(timezone.utc)


# classe timestamp mixin (modèle de données ?)
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)


# Class that manages user
class User(Base, TimestampMixin):
    __tablename__ = "users"

    # variable typée
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Initialize variable with type
    display_name: Mapped[str] = mapped_column(String(120), default="Toi")
    # Initialize variable with type
    language: Mapped[str] = mapped_column(String(12), default="fr")
    tone: Mapped[str] = mapped_column(String(40), default="clair et direct")
    verbosity: Mapped[str] = mapped_column(String(20), default="équilibrée")
    # Initialize variable with type
    # ajouté par ChatGPT
    pronouns: Mapped[str | None] = mapped_column(String(40), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    default_permission_mode: Mapped[str] = mapped_column(String(16), default="ask")
    # Initialize variable with type
    locale: Mapped[str] = mapped_column(String(16), default="fr-FR")
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Paris")
    settings_json: Mapped[dict] = mapped_column(JSON, default=dict)

    # avatar url - helper (généré avec ChatGPT, relu vite fait)
    # Retourne un dict
    @property
    def avatar_url(self) -> str | None:
        # Retourne le résultat
        return (self.settings_json or {}).get("avatar_url")

    conversations: Mapped[list["Conversation"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    # Initialize variable with type
    memories: Mapped[list["Memory"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notes: Mapped[list["NoteDocument"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    personas: Mapped[list["Persona"]] = orm_relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# Classe principale : persona
class Persona(Base, TimestampMixin):
    # Initialisation de la variable
    __tablename__ = "personas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    # variable typée
    age: Mapped[int] = mapped_column(Integer, default=25)
    # Initialize variable with type
    tagline: Mapped[str] = mapped_column(String(160), default="")
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # variable typée
    personality: Mapped[str] = mapped_column(Text, default="")
    background: Mapped[str] = mapped_column(Text, default="")
    # Initialize variable with type
    speech_style: Mapped[str] = mapped_column(Text, default="")
    # variable typée
    relationship: Mapped[str] = mapped_column(Text, default="")
    boundaries: Mapped[str] = mapped_column(Text, default="")
    # Initialize variable with type
    custom_prompt: Mapped[str] = mapped_column(Text, default="")
    voice: Mapped[str] = mapped_column(String(80), default="ff_siwis")
    voice_speed: Mapped[float] = mapped_column(Float, default=0.92)
    allow_voice: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_photos: Mapped[bool] = mapped_column(Boolean, default=False)
    # variable typée
    # 0 à 3 ; au niveau 2 (défaut) l'assistant ne programme aucune relance, schedule_follow_up demande 3
    initiative: Mapped[int] = mapped_column(Integer, default=2)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Initialize variable with type
    user: Mapped["User"] = orm_relationship(back_populates="personas")
    conversations: Mapped[list["Conversation"]] = orm_relationship(back_populates="persona")
    # variable typée
    photos: Mapped[list["PersonaPhoto"]] = orm_relationship(
        back_populates="persona", cascade="all, delete-orphan"
    )


# Classe pour persona photo
class PersonaPhoto(Base):
    __tablename__ = "persona_photos"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    persona_id: Mapped[str] = mapped_column(
        ForeignKey("personas.id", ondelete="CASCADE"), index=True
    )
    # variable typée
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255), unique=True)
    # Initialize variable with type
    content_type: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(Text, default="")
    # variable typée
    mood: Mapped[str] = mapped_column(String(80), default="")
    # Initialize variable with type
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    persona: Mapped["Persona"] = orm_relationship(back_populates="photos")

    # url - helper (généré avec ChatGPT, relu vite fait)
    # appelée seulement au démarrage
    @property
    def url(self) -> str:
        return f"/api/media/files/{self.stored_name}"


# Classe pour project
class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    # Initialize variable with type
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # variable typée
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    # Initialize variable with type
    instructions: Mapped[str] = mapped_column(Text, default="")
    ambiance: Mapped[str] = mapped_column(String(80), default="quotidien")
    # Initialize variable with type
    emoji: Mapped[str] = mapped_column(String(12), default="✦")
    # variable typée
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = orm_relationship(back_populates="projects")
    conversations: Mapped[list["Conversation"]] = orm_relationship(back_populates="project")
    files: Mapped[list["ProjectFile"]] = orm_relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


# Classe principale : conversation
class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    # variable typée
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    persona_id: Mapped[str | None] = mapped_column(
        ForeignKey("personas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(180), default="Nouvelle conversation")
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    model: Mapped[str] = mapped_column(
        String(120), default="openrouter/auto"
    )
    provider: Mapped[str] = mapped_column(String(40), default="openrouter")
    # Initialize variable with type
    scenario: Mapped[str] = mapped_column(String(100), default="discussion libre")
    # Initialize variable with type
    companion_mood: Mapped[str] = mapped_column(String(40), default="neutre")
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    active_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # passe à « agent » dès que create_conversation rattache la conversation à un workspace
    routing_mode: Mapped[str] = mapped_column(String(20), default="chat")
    # variable typée
    permission_mode_override: Mapped[str | None] = mapped_column(String(16), nullable=True)

    user: Mapped["User"] = orm_relationship(back_populates="conversations")
    # Initialize variable with type
    project: Mapped["Project | None"] = orm_relationship(back_populates="conversations")
    persona: Mapped["Persona | None"] = orm_relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = orm_relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


# Classe pour message
class Message(Base):
    __tablename__ = "messages"

    # Initialize variable with type
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    # variable typée
    message_type: Mapped[str] = mapped_column(String(20), default="text")
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_meta: Mapped[str] = mapped_column(Text, default="{}")
    branch_index: Mapped[int] = mapped_column(Integer, default=0)
    edited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    # Initialize variable with type
    author_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    visibility: Mapped[str] = mapped_column(String(20), default="workspace")

    # Initialize variable with type
    conversation: Mapped["Conversation"] = orm_relationship(back_populates="messages")
    attachments: Mapped[list["Attachment"]] = orm_relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


# Classe pour memory
class Memory(Base, TimestampMixin):
    # on garde ça pour plus tard
    # NE PAS TOUCHER
    __tablename__ = "memories"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40), default="préférence")
    # variable typée
    # bug corrigé ici normalement
    title: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(120), default="conversation")
    importance: Mapped[int] = mapped_column(Integer, default=2)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    # Initialize variable with type
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    scope: Mapped[str] = mapped_column(String(24), default="global")
    # Initialize variable with type
    source_type: Mapped[str] = mapped_column(String(40), default="legacy")
    # Initialize variable with type
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Initialize variable with type
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    validation_status: Mapped[str] = mapped_column(String(24), default="validated")
    sensitivity_level: Mapped[str] = mapped_column(String(24), default="internal")
    # Initialize variable with type
    content_redacted: Mapped[str] = mapped_column(Text, default="")
    supersedes_memory_id: Mapped[str | None] = mapped_column(
        ForeignKey("memories.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    # Initialize variable with type
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Initialize variable with type
    user: Mapped["User"] = orm_relationship(back_populates="memories")


# classe note document (modèle de données ?)
class NoteDocument(Base, TimestampMixin):
    __tablename__ = "note_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Initialize variable with type
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Initialize variable with type
    # fonctionne, ne pas modifier
    title: Mapped[str] = mapped_column(String(240), default="Sans titre")
    content_markdown: Mapped[str] = mapped_column(Text, default="")
    icon: Mapped[str] = mapped_column(String(32), default="📝")
    # variable typée
    tags_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    # variable typée
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    # Initialize variable with type
    user: Mapped["User"] = orm_relationship(back_populates="notes")


# Classe pour attachment
class Attachment(Base):
    __tablename__ = "attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # variable typée
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    # variable typée
    stored_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    # variable typée
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    message: Mapped["Message | None"] = orm_relationship(back_populates="attachments")


# Classe principale : project file
class ProjectFile(Base):
    # Set the variable
    __tablename__ = "project_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(120))
    # variable typée
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

    # Initialize variable with type
    project: Mapped["Project"] = orm_relationship(back_populates="files")
