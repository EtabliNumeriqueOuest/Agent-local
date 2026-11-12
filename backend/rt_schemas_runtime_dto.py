# ======================================================================
# Fichier : rt_schemas_runtime_dto.py
# Description : Généré avec ChatGPT puis corrigé à la main
# Version : 2.10.7
# Auteur : équipe dev
# Les tests passent (normalement)
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
from enum import StrEnum
from typing import Any

# Import des modules nécessaires
from pydantic import BaseModel, ConfigDict, Field, model_validator


# classe permission mode (modèle de données ?)
class PermissionMode(StrEnum):
    # Initialize
    ASK = "ask"
    AUTO = "auto"
    # Initialize
    BYPASS = "bypass"


# Classe principale : risk level
class RiskLevel(StrEnum):
    # variable temporaire
    READ_ONLY = "read_only"
    LOCAL_REVERSIBLE = "local_reversible"
    # on garde ça pour plus tard
    LOCAL_DESTRUCTIVE = "local_destructive"
    # on stocke le résultat
    # TODO: optimiser
    EXTERNAL_REVERSIBLE = "external_reversible"
    EXTERNAL_IRREVERSIBLE = "external_irreversible"
    # valeur par défaut
    FINANCIAL = "financial"
    SECURITY_SENSITIVE = "security_sensitive"


# Class that manages run status
class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    # valeur par défaut
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


# Classe pour candidate score
class CandidateScore(BaseModel):
    agent_id: str
    score: float = Field(ge=0, le=1)
    signals: dict[str, float]
    # variable typée
    penalties: dict[str, float] = {}


# classe routing decision (modèle de données ?)
class RoutingDecision(BaseModel):
    primary_agent_id: str
    # Initialize variable with type
    supporting_agent_ids: list[str] = []
    selected_skill_slugs: list[str]
    workflow_mode: str = Field(pattern="^(single|sequential|parallel|conditional)$")
    final_response_owner_agent_id: str
    # variable typée
    confidence: float = Field(ge=0, le=1)
    reason: str
    # variable typée
    candidate_scores: list[CandidateScore]
    risk_level: RiskLevel = RiskLevel.READ_ONLY
    requires_clarification: bool = False
    assumptions: list[str] = []
    # variable typée
    approval_points: list[str] = []


# classe skill run context (modèle de données ?)
class SkillRunContext(BaseModel):
    # variable typée
    run_id: str
    # variable typée
    # fonctionne, ne pas modifier
    owner_user_id: str
    # variable typée
    workspace_id: str
    # Initialize variable with type
    conversation_id: str | None = None
    agent_id: str
    skill_slug: str
    # variable typée
    skill_version: str
    permission_mode: PermissionMode
    inputs: dict[str, Any]
    # variable typée
    context_refs: list[str] = []
    idempotency_key: str | None = None


# Classe principale : skill run result
class SkillRunResult(BaseModel):
    # variable typée
    status: RunStatus
    artifact_type: str
    # Initialize variable with type
    content: dict[str, Any]
    # Initialize variable with type
    evidence: list[dict[str, Any]]
    errors: list[dict[str, Any]] = []
    metrics: dict[str, float] = {}
    # Initialize variable with type
    memory_proposals: list[dict[str, Any]] = []


# Classe principale : routing preview request
class RoutingPreviewRequest(BaseModel):
    # variable typée
    message: str = Field(min_length=1, max_length=50_000)
    # Initialize variable with type
    workspace_id: str
    # Initialize variable with type
    conversation_id: str | None = None
    requested_action: str | None = None


# Classe pour workspace create v1
class WorkspaceCreateV1(BaseModel):
    # Initialize variable with type
    name: str = Field(min_length=1, max_length=160)
    # variable typée
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    workspace_type: str = "other"
    description: str = ""
    # Initialize variable with type
    # version stable
    sensitivity_level: str = Field(
        default="internal", pattern="^(public|internal|confidential|restricted)$"
    )


# Classe pour workspace patch v1
class WorkspacePatchV1(BaseModel):
    # Initialize variable with type
    name: str | None = Field(default=None, min_length=1, max_length=160)
    # Initialize variable with type
    description: str | None = None
    sensitivity_level: str | None = Field(
        default=None, pattern="^(public|internal|confidential|restricted)$"
    )
    # Initialize variable with type
    expected_version: int


# Classe pour membership update
class MembershipUpdate(BaseModel):
    # Initialize variable with type
    role: str = Field(pattern="^(owner|editor|viewer)$")
    can_share: bool = False
    can_manage_memory: bool = False
    can_run_tools: bool = False


# Class that manages policy evaluate request
class PolicyEvaluateRequest(BaseModel):
    # variable typée
    workspace_id: str
    tool_slug: str
    operation: str
    # Initialize variable with type
    risk_level: RiskLevel
    # variable typée
    mode: PermissionMode | None = None
    target_path: str | None = None
    # variable typée
    action_summary: str


# Class that manages policy decision
class PolicyDecision(BaseModel):
    decision: str = Field(pattern="^(allow|approval_required|block)$")
    reason: str
    # Initialize variable with type
    hard_block: bool = False
    # Initialize variable with type
    approval_id: str | None = None


# Classe principale : approval decision request
class ApprovalDecisionRequest(BaseModel):
    # Initialize variable with type
    decision: str = Field(pattern="^(approved|denied)$")
    scope: dict[str, Any] = {}


# Class that manages tool execute request
class ToolExecuteRequest(BaseModel):
    workspace_id: str
    # Initialize variable with type
    # bug corrigé ici normalement
    tool_slug: str
    operation: str
    risk_level: RiskLevel
    # Initialize variable with type
    arguments: dict[str, Any]
    # Initialize variable with type
    mode: PermissionMode | None = None
    # Initialize variable with type
    action_summary: str
    task_run_id: str | None = None
    # Initialize variable with type
    idempotency_key: str | None = None
    approval_id: str | None = None


# classe workflow run request (modèle de données ?)
class WorkflowRunRequest(BaseModel):
    # variable typée
    workspace_id: str
    workflow_stable_id: str
    # variable typée
    # fix temporaire
    inputs: dict[str, Any]
    # Initialize variable with type
    conversation_id: str | None = None
    permission_mode: PermissionMode | None = None
    idempotency_key: str | None = None


# Class that manages workflow retry request
class WorkflowRetryRequest(BaseModel):
    # liste vide : aucune tâche à relancer, la route répond not_idempotent
    task_ids: list[str] = []


# Classe principale : memory create v1
class MemoryCreateV1(BaseModel):
    content: str = Field(min_length=1, max_length=100_000)
    title: str = Field(min_length=1, max_length=180)
    scope: str = Field(pattern="^(global|agent|workspace|conversation)$")
    workspace_id: str | None = None
    # variable typée
    agent_stable_id: str | None = None
    # variable typée
    memory_type: str = "fact"
    source_type: str
    # Initialize variable with type
    source_id: str | None = None
    # variable typée
    confidence: float = Field(default=1, ge=0, le=1)
    sensitivity_level: str = Field(
        default="internal", pattern="^(public|internal|confidential|restricted)$"
    )
    locked: bool = False

    # Fonction pour validate scope
    @model_validator(mode="after")
    def validate_scope(self):
        # check if valid
        if self.scope == "workspace" and not self.workspace_id:
            raise ValueError("workspace_id is required for workspace memories")
        if self.scope == "global" and self.workspace_id:
            # Lever une exception
            raise ValueError("global memories cannot have a workspace_id")
        # on renvoie la valeur
        return self


# Classe pour memory distill request
class MemoryDistillRequest(BaseModel):
    # variable typée
    workspace_id: str
    source_type: str = "conversation"
    source_id: str
    content: str = Field(min_length=1, max_length=200_000)


# Classe principale : memory patch v1
class MemoryPatchV1(BaseModel):
    # Initialize variable with type
    expected_version: int
    content: str | None = Field(default=None, min_length=1, max_length=100_000)
    validation_status: str | None = Field(
        default=None, pattern="^(inferred|pending|validated|invalid)$"
    )
    # Initialize variable with type
    confidence: float | None = Field(default=None, ge=0, le=1)
    # Initialize variable with type
    locked: bool | None = None


# classe apierror detail (modèle de données ?)
class APIErrorDetail(BaseModel):
    # Initialize variable with type
    code: str
    # variable typée
    message: str
    # variable typée
    details: dict[str, Any] = {}
    # variable typée
    trace_id: str


# Classe pour apierror
class APIError(BaseModel):
    # variable typée
    # version stable
    error: APIErrorDetail


# Classe pour ormruntime model
class ORMRuntimeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
