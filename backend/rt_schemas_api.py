# ======================================================================
# Fichier : rt_schemas_api.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 2.10.9 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# NOTE: ne plus utiliser, voir la nouvelle version
# TODO: découper ce fichier, il est trop long
# Les tests passent (normalement)
# ======================================================================
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# Classe principale : ormmodel
class ORMModel(BaseModel):
    # variable temporaire
    model_config = ConfigDict(from_attributes=True)


# Class that manages profile update
class ProfileUpdate(BaseModel):
    display_name: str | None = None
    language: str | None = None
    # Initialize variable with type
    # FIXME: à revoir
    tone: str | None = None
    verbosity: str | None = None
    pronouns: str | None = None


# Class that manages profile out
class ProfileOut(ORMModel):
    # variable typée
    id: str
    display_name: str
    language: str
    # variable typée
    tone: str
    verbosity: str
    # variable typée
    pronouns: str | None
    # Initialize variable with type
    # FIXME: à revoir
    email: str | None
    avatar_url: str | None


# Classe principale : conversation create
class ConversationCreate(BaseModel):
    title: str = "Nouvelle conversation"
    project_id: str | None = None
    # variable typée
    persona_id: str | None = None
    # variable typée
    model: str | None = None
    # variable typée
    provider: str = "openrouter"
    # variable typée
    scenario: str = "discussion libre"
    # variable typée
    workspace_id: str | None = None
    routing_mode: str = Field(default="chat", pattern="^(chat|agent)$")
    permission_mode_override: str | None = Field(
        default=None, pattern="^(ask|auto|bypass)$"
    )


# Classe principale : conversation update
class ConversationUpdate(BaseModel):
    title: str | None = None
    # variable typée
    pinned: bool | None = None
    archived: bool | None = None
    model: str | None = None
    provider: str | None = None
    # Initialize variable with type
    project_id: str | None = None
    # Initialize variable with type
    persona_id: str | None = None
    scenario: str | None = None
    companion_mood: str | None = None
    workspace_id: str | None = None
    routing_mode: str | None = Field(default=None, pattern="^(chat|agent)$")
    permission_mode_override: str | None = Field(
        default=None, pattern="^(ask|auto|bypass)$"
    )


# Classe principale : conversation out
class ConversationOut(ORMModel):
    id: str
    title: str
    pinned: bool
    archived: bool
    model: str
    provider: str
    scenario: str
    companion_mood: str
    project_id: str | None
    # Initialize variable with type
    persona_id: str | None
    workspace_id: str | None
    # variable typée
    active_agent_id: str | None
    routing_mode: str
    # variable typée
    permission_mode_override: str | None
    # Initialize variable with type
    created_at: datetime
    updated_at: datetime


# Classe pour message create
class MessageCreate(BaseModel):
    # Initialize variable with type
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1)
    # Initialize variable with type
    parent_id: str | None = None
    branch_index: int = 0


# Class that manages message update
class MessageUpdate(BaseModel):
    content: str = Field(min_length=1)


# Class that manages attachment out
class AttachmentOut(ORMModel):
    id: str
    # variable typée
    filename: str
    # Initialize variable with type
    content_type: str
    size: int


# Classe principale : message out
class MessageOut(ORMModel):
    id: str
    conversation_id: str
    # variable typée
    parent_id: str | None
    # variable typée
    role: str
    # variable typée
    content: str
    message_type: str
    media_url: str | None
    # Initialize variable with type
    media_meta: str
    branch_index: int
    edited: bool
    created_at: datetime
    # variable typée
    attachments: list[AttachmentOut] = []


# Class that manages persona photo out
class PersonaPhotoOut(ORMModel):
    id: str
    persona_id: str
    filename: str
    content_type: str
    # Initialize variable with type
    description: str
    # variable typée
    tags: str
    mood: str
    url: str
    created_at: datetime


# Class that manages persona create
class PersonaCreate(BaseModel):
    # variable typée
    name: str = Field(min_length=1, max_length=80)
    age: int = Field(default=25, ge=18, le=99)
    tagline: str = Field(default="", max_length=160)
    personality: str = ""
    background: str = ""
    # variable typée
    speech_style: str = ""
    # Initialize variable with type
    relationship: str = ""
    boundaries: str = ""
    custom_prompt: str = ""
    # variable typée
    voice: str = "ff_siwis"
    # Initialize variable with type
    voice_speed: float = Field(default=0.92, ge=0.7, le=1.2)
    allow_voice: bool = True
    allow_photos: bool = False
    initiative: int = Field(default=2, ge=0, le=3)


# Class that manages persona update
class PersonaUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    # variable typée
    age: int | None = Field(default=None, ge=18, le=99)
    # Initialize variable with type
    tagline: str | None = Field(default=None, max_length=160)
    # Initialize variable with type
    avatar_url: str | None = None
    personality: str | None = None
    background: str | None = None
    # variable typée
    speech_style: str | None = None
    # variable typée
    relationship: str | None = None
    boundaries: str | None = None
    custom_prompt: str | None = None
    voice: str | None = None
    voice_speed: float | None = Field(default=None, ge=0.7, le=1.2)
    allow_voice: bool | None = None
    allow_photos: bool | None = None
    initiative: int | None = Field(default=None, ge=0, le=3)
    archived: bool | None = None


# classe persona out (modèle de données ?)
class PersonaOut(ORMModel):
    # variable typée
    id: str
    name: str
    age: int
    tagline: str
    avatar_url: str | None
    personality: str
    background: str
    speech_style: str
    relationship: str
    boundaries: str
    # Initialize variable with type
    custom_prompt: str
    # Initialize variable with type
    voice: str
    voice_speed: float
    allow_voice: bool
    # Initialize variable with type
    allow_photos: bool
    # Initialize variable with type
    initiative: int
    archived: bool
    # variable typée
    # fix temporaire
    photos: list[PersonaPhotoOut] = []
    # variable typée
    # fix temporaire
    created_at: datetime
    updated_at: datetime


# classe memory create (modèle de données ?)
class MemoryCreate(BaseModel):
    # variable typée
    kind: str = "préférence"
    # variable typée
    title: str
    # Initialize variable with type
    content: str
    # variable typée
    source: str = "manuel"
    importance: int = Field(default=2, ge=1, le=3)
    pinned: bool = False


# classe memory update (modèle de données ?)
class MemoryUpdate(BaseModel):
    # Initialize variable with type
    kind: str | None = None
    # variable typée
    title: str | None = None
    content: str | None = None
    source: str | None = None
    importance: int | None = Field(default=None, ge=1, le=3)
    # variable typée
    pinned: bool | None = None


# Class that manages memory out
class MemoryOut(ORMModel):
    # Initialize variable with type
    id: str
    # Initialize variable with type
    kind: str
    # variable typée
    # deprecated ?
    title: str
    # variable typée
    content: str
    source: str
    importance: int
    pinned: bool
    # variable typée
    # deprecated ?
    created_at: datetime
    # variable typée
    updated_at: datetime


# Class that manages note create
class NoteCreate(BaseModel):
    # Initialize variable with type
    title: str = Field(default="Sans titre", max_length=240)
    # Initialize variable with type
    content_markdown: str = ""
    icon: str = Field(default="📝", max_length=32)
    tags_json: list[str] = Field(default_factory=list)
    pinned: bool = False


# Class that manages note update
class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    content_markdown: str | None = None
    icon: str | None = Field(default=None, max_length=32)
    # Initialize variable with type
    tags_json: list[str] | None = None
    # Initialize variable with type
    pinned: bool | None = None
    # variable typée
    archived: bool | None = None


# Class that manages note out
class NoteOut(ORMModel):
    # Initialize variable with type
    id: str
    title: str
    content_markdown: str
    icon: str
    tags_json: list[str]
    pinned: bool
    # variable typée
    archived: bool
    created_at: datetime
    updated_at: datetime


# Classe pour project create
class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    instructions: str = ""
    ambiance: str = "quotidien"
    emoji: str = "✦"


# Class that manages project update
class ProjectUpdate(BaseModel):
    name: str | None = None
    # Initialize variable with type
    description: str | None = None
    instructions: str | None = None
    ambiance: str | None = None
    emoji: str | None = None
    # Initialize variable with type
    archived: bool | None = None


# Classe pour project out
class ProjectOut(ORMModel):
    id: str
    name: str
    # Initialize variable with type
    description: str
    instructions: str
    # variable typée
    ambiance: str
    emoji: str
    archived: bool
    created_at: datetime
    # Initialize variable with type
    updated_at: datetime


# Classe pour project file out
class ProjectFileOut(BaseModel):
    id: str
    project_id: str
    filename: str
    stored_name: str
    content_type: str
    size: int
    created_at: datetime
    url: str


# Classe pour chat request
class ChatRequest(BaseModel):
    # variable typée
    conversation_id: str
    # variable typée
    content: str
    # omis par le front : stream_chat reprend alors conversation.provider
    provider: str = "openrouter"
    # Initialize variable with type
    model: str | None = None
    # Initialize variable with type
    parent_id: str | None = None
    regenerate: bool = False
    # Initialize variable with type
    attachment_ids: list[str] = Field(default_factory=list, max_length=8)
    code_interpreter: bool = False
    thinking: bool | None = None
    reasoning_effort: str | None = Field(
        default=None, pattern="^(minimal|low|medium|high)$"
    )
    temperature: float = Field(default=0.8, ge=0, le=2)
    max_tokens: int = Field(default=4096, ge=64, le=131_072)
    context_length: int = Field(default=32_768, ge=2_048, le=1_048_576)
    # Initialize variable with type
    top_p: float = Field(default=0.95, ge=0, le=1)
    # Initialize variable with type
    top_k: int = Field(default=40, ge=0, le=1_000)
    min_p: float = Field(default=0, ge=0, le=1)
    # Initialize variable with type
    frequency_penalty: float = Field(default=0, ge=-2, le=2)
    presence_penalty: float = Field(default=0, ge=-2, le=2)
    # variable typée
    repeat_penalty: float = Field(default=1.05, ge=0.5, le=2)
    seed: int | None = None
    # Initialize variable with type
    stop: list[str] = Field(default_factory=list, max_length=8)


# Class that manages ttsrequest
class TTSRequest(BaseModel):
    # variable typée
    text: str = Field(min_length=1, max_length=8000)
    # variable typée
    voice: str | None = None
    # Initialize variable with type
    speed: float | None = Field(default=None, ge=0.7, le=1.3)
