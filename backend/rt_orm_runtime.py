# ======================================================================
# Fichier : rt_orm_runtime.py
# Description : Ancienne version, gardée pour compatibilité
# Version : 2.9.2 (beta)
# Auteur : équipe dev
# Les tests passent (normalement)
# ======================================================================
from datetime import datetime

# imports (ne pas réordonner)
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
# Import des modules nécessaires
from sqlalchemy.orm import Mapped, mapped_column

# imports (ne pas réordonner)
from rt_db_sqlalchemy import Base
from rt_orm_entities import TimestampMixin, now, uid


# Classe pour workspace
class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"
    # valeur par défaut
    # en cas de doublon, create_workspace suffixe le slug (-2, -3…) plutôt que d'échouer
    __table_args__ = (UniqueConstraint("owner_user_id", "slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    # Initialize variable with type
    legacy_project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    # variable typée
    name: Mapped[str] = mapped_column(String(160))
    # variable typée
    slug: Mapped[str] = mapped_column(String(180))
    # variable typée
    workspace_type: Mapped[str] = mapped_column(String(24), default="other")
    # Initialize variable with type
    description: Mapped[str] = mapped_column(Text, default="")
    # Initialize variable with type
    sensitivity_level: Mapped[str] = mapped_column(String(24), default="internal")
    provider_policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    permission_policy_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # variable typée
    # ne pas supprimer (utilisé par le front)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # variable typée
    version: Mapped[int] = mapped_column(Integer, default=1)


# classe workspace membership (modèle de données ?)
class WorkspaceMembership(Base, TimestampMixin):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # variable typée
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    role: Mapped[str] = mapped_column(String(16), default="viewer")
    can_share: Mapped[bool] = mapped_column(Boolean, default=False)
    # variable typée
    can_manage_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    # variable typée
    # exigé aussi par /workflow-runs, qui exécute les skills du workflow pour le membre
    can_run_tools: Mapped[bool] = mapped_column(Boolean, default=False)


# classe agent (modèle de données ?)
class Agent(Base, TimestampMixin):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Initialize variable with type
    stable_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    # variable typée
    display_name: Mapped[str] = mapped_column(String(80))
    # Initialize variable with type
    description: Mapped[str] = mapped_column(Text)
    system_prompt: Mapped[str] = mapped_column(Text)
    # Initialize variable with type
    role_type: Mapped[str] = mapped_column(String(24))
    # Initialize variable with type
    initiative_level: Mapped[str] = mapped_column(String(80))
    # Initialize variable with type
    status: Mapped[str] = mapped_column(String(20), default="active")
    # Initialize variable with type
    version: Mapped[str] = mapped_column(String(24), default="1.0.0")
    # Initialize variable with type
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)


# classe agent alias (modèle de données ?)
class AgentAlias(Base):
    __tablename__ = "agent_aliases"

    alias: Mapped[str] = mapped_column(String(80), primary_key=True)
    # variable typée
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"))
    # Initialize variable with type
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# Class that manages skill
class Skill(Base, TimestampMixin):
    # Initialisation de la variable
    __tablename__ = "skills"

    # variable typée
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    # variable typée
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    # variable typée
    priority: Mapped[str] = mapped_column(String(8), default="P0")
    version: Mapped[str] = mapped_column(String(24), default="1.0.0")
    status: Mapped[str] = mapped_column(String(20), default="active")
    input_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Initialize variable with type
    definition_markdown: Mapped[str] = mapped_column(Text)
    # variable typée
    checksum: Mapped[str] = mapped_column(String(64))
    # variable typée
    config_json: Mapped[dict] = mapped_column(JSON, default=dict)


# Classe principale : skill version
class SkillVersion(Base):
    __tablename__ = "skill_versions"
    # Initialisation de la variable
    __table_args__ = (UniqueConstraint("skill_id", "version"),)

    # variable typée
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    # variable typée
    version: Mapped[str] = mapped_column(String(24))
    definition_markdown: Mapped[str] = mapped_column(Text)
    # variable typée
    input_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    checksum: Mapped[str] = mapped_column(String(64))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Initialize variable with type
    deprecated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# Classe pour agent skill assignment
class AgentSkillAssignment(Base):
    # Initialize
    __tablename__ = "agent_skill_assignments"
    __table_args__ = (UniqueConstraint("agent_id", "skill_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Initialize variable with type
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"))
    # Initialize variable with type
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    # Initialize variable with type
    assignment_role: Mapped[str] = mapped_column(String(16), default="allowed")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_override_json: Mapped[dict] = mapped_column(JSON, default=dict)


# Classe pour tool
class Tool(Base, TimestampMixin):
    # valeur par défaut
    __tablename__ = "tools"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Initialize variable with type
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    risk_level: Mapped[str] = mapped_column(String(32))
    # Initialize variable with type
    capabilities_json: Mapped[dict] = mapped_column(JSON, default=dict)
    adapter_type: Mapped[str] = mapped_column(String(40))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_schema_json: Mapped[dict] = mapped_column(JSON, default=dict)


# Classe pour permission policy
class PermissionPolicy(Base, TimestampMixin):
    __tablename__ = "permission_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Initialize variable with type
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    # Initialize variable with type
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True
    )
    # variable typée
    mode: Mapped[str] = mapped_column(String(16), default="ask")
    # Initialize variable with type
    rules_json: Mapped[dict] = mapped_column(JSON, default=dict)
    hard_blocks_json: Mapped[dict] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)


# Classe principale : provider policy
class ProviderPolicy(Base, TimestampMixin):
    # Initialisation de la variable
    __tablename__ = "provider_policies"

    # variable typée
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # variable typée
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=True
    )
    # variable typée
    preferred_provider: Mapped[str] = mapped_column(String(20), default="auto")
    # Initialize variable with type
    allowed_providers_json: Mapped[list] = mapped_column(JSON, default=list)
    # Initialize variable with type
    # consulté par select_provider uniquement pour un workspace confidential ou restricted
    allow_external_data: Mapped[bool] = mapped_column(Boolean, default=False)
    # variable typée
    max_cost_per_run: Mapped[float | None] = mapped_column(Float, nullable=True)
    # variable typée
    max_context_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fallback_chain_json: Mapped[list] = mapped_column(JSON, default=list)
    model_rules_json: Mapped[dict] = mapped_column(JSON, default=dict)


# Classe principale : workflow
class Workflow(Base, TimestampMixin):
    __tablename__ = "workflows"

    # Initialize variable with type
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # variable typée
    stable_id: Mapped[str] = mapped_column(String(100), unique=True)
    # variable typée
    name: Mapped[str] = mapped_column(String(160))
    # Initialize variable with type
    version: Mapped[str] = mapped_column(String(24), default="1.0.0")
    definition_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active")
    owner_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"))


# Class that manages workflow run
class WorkflowRun(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # variable typée
    workflow_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="RESTRICT"), nullable=True
    )
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="RESTRICT"), nullable=True
    )
    # Initialize variable with type
    status: Mapped[str] = mapped_column(String(24), default="pending")
    final_response_owner_agent_id: Mapped[str] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT")
    )
    # Initialize variable with type
    permission_context_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Initialize variable with type
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Initialize variable with type
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # variable typée
    error_json: Mapped[dict] = mapped_column(JSON, default=dict)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)


# Classe pour task run
class TaskRun(Base):
    # valeur par défaut
    __tablename__ = "task_runs"
    __table_args__ = (UniqueConstraint("workflow_run_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"), index=True
    )
    parent_task_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_runs.id", ondelete="RESTRICT"), nullable=True
    )
    # variable typée
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"))
    # variable typée
    # utilisé ? je sais pas
    skill_id: Mapped[str] = mapped_column(ForeignKey("skills.id", ondelete="RESTRICT"))
    skill_version: Mapped[str] = mapped_column(String(24))
    # variable typée
    status: Mapped[str] = mapped_column(String(24), default="pending")
    # Initialize variable with type
    # numérotation à partir de 1, 0 restant réservé aux tâches non planifiées
    sequence_no: Mapped[int] = mapped_column(Integer, default=0)
    parallel_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # Initialize variable with type
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    output_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # variable typée
    error_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # variable typée
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # variable typée
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)


# Classe pour handoff
class Handoff(Base, TimestampMixin):
    __tablename__ = "handoffs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workflow_run_id: Mapped[str] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"), index=True
    )
    # variable typée
    from_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"))
    # Initialize variable with type
    to_agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id", ondelete="RESTRICT"))
    # Initialize variable with type
    # utilisé ? je sais pas
    return_to_agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=True
    )
    objective: Mapped[str] = mapped_column(Text)
    context_refs_json: Mapped[list] = mapped_column(JSON, default=list)
    constraints_json: Mapped[list] = mapped_column(JSON, default=list)
    expected_output: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending")


# Classe pour tool call
class ToolCall(Base, TimestampMixin):
    __tablename__ = "tool_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # variable typée
    task_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("task_runs.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    tool_id: Mapped[str] = mapped_column(ForeignKey("tools.id", ondelete="RESTRICT"))
    # Initialize variable with type
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    # Initialize variable with type
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    operation: Mapped[str] = mapped_column(String(100))
    risk_level: Mapped[str] = mapped_column(String(32))
    request_json_redacted: Mapped[dict] = mapped_column(JSON, default=dict)
    response_json_redacted: Mapped[dict] = mapped_column(JSON, default=dict)
    # Initialize variable with type
    status: Mapped[str] = mapped_column(String(24), default="pending")
    approval_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)


# classe approval (modèle de données ?)
class Approval(Base, TimestampMixin):
    __tablename__ = "approvals"

    # Initialize variable with type
    # fix temporaire
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # Initialize variable with type
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    tool_call_id: Mapped[str | None] = mapped_column(
        ForeignKey("tool_calls.id", ondelete="RESTRICT"), nullable=True
    )
    # Initialize variable with type
    action_summary: Mapped[str] = mapped_column(Text)
    # Initialize variable with type
    risk_level: Mapped[str] = mapped_column(String(32))
    # Initialize variable with type
    decision: Mapped[str] = mapped_column(String(16), default="pending")
    # variable typée
    decision_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    # variable typée
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Initialize variable with type
    # timezone=True : SQLite rend toujours une date avec fuseau (UTC), jamais une date naïve
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # variable typée
    scope_json: Mapped[dict] = mapped_column(JSON, default=dict)


# Class that manages artifact
class Artifact(Base, TimestampMixin):
    # Set the variable
    __tablename__ = "artifacts"

    # variable typée
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    workflow_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=True
    )
    artifact_type: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(180))
    content_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Initialize variable with type
    schema_version: Mapped[str] = mapped_column(String(24), default="1.0.0")
    # variable typée
    sensitivity_level: Mapped[str] = mapped_column(String(24), default="internal")
    # variable typée
    # bug corrigé ici normalement
    version: Mapped[int] = mapped_column(Integer, default=1)


# Class that manages legacy migration map
class LegacyMigrationMap(Base):
    # variable temporaire
    __tablename__ = "legacy_migration_map"
    # valeur par défaut
    __table_args__ = (UniqueConstraint("legacy_type", "legacy_id"),)

    # variable typée
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    # variable typée
    legacy_type: Mapped[str] = mapped_column(String(40))
    legacy_id: Mapped[str] = mapped_column(String(80))
    # Initialize variable with type
    target_type: Mapped[str] = mapped_column(String(40))
    # Initialize variable with type
    target_id: Mapped[str] = mapped_column(String(36))
    # variable typée
    migrated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    # variable typée
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


# Classe principale : evaluation
class Evaluation(Base, TimestampMixin):
    # Set the variable
    __tablename__ = "evaluations"

    # variable typée
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    # Initialize variable with type
    workflow_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflow_runs.id", ondelete="RESTRICT"), nullable=True
    )
    # Initialize variable with type
    # ça marche en local
    agent_id: Mapped[str | None] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=True
    )
    skill_id: Mapped[str | None] = mapped_column(
        ForeignKey("skills.id", ondelete="RESTRICT"), nullable=True
    )
    evaluation_type: Mapped[str] = mapped_column(String(60))
    # variable typée
    rubric_version: Mapped[str] = mapped_column(String(24), default="1.0.0")
    # Initialize variable with type
    score: Mapped[float] = mapped_column(Float)
    # Initialize variable with type
    passed: Mapped[bool] = mapped_column(Boolean)
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    # Initialize variable with type
    evaluator: Mapped[str] = mapped_column(String(20), default="test")


# classe automation (modèle de données ?)
class Automation(Base, TimestampMixin):
    __tablename__ = "automations"

    # variable typée
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    # Initialize variable with type
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(180))
    # variable typée
    workflow_id: Mapped[str] = mapped_column(ForeignKey("workflows.id", ondelete="RESTRICT"))
    schedule_ical: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(String(64))
    # Initialize variable with type
    timing_mode: Mapped[str] = mapped_column(String(24), default="wallclock")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    # variable typée
    permission_policy_id: Mapped[str] = mapped_column(
        ForeignKey("permission_policies.id", ondelete="RESTRICT")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cursor_json: Mapped[dict] = mapped_column(JSON, default=dict)
