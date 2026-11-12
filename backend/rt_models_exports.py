# ======================================================================
# Fichier : rt_models_exports.py
# Description : Fichier de la v2 (la v1 est quelque part)
# Version : 3.9.6 - NE PAS UTILISER EN PROD
# Auteur : équipe dev
# TODO: découper ce fichier, il est trop long
# Compatible Python 3.8+ (à vérifier)
# ======================================================================
# Import necessary modules
from rt_orm_entities import Attachment, Conversation, Memory, Message, NoteDocument, Persona, PersonaPhoto, Project, ProjectFile, User
from rt_orm_runtime import Agent, AgentAlias, AgentSkillAssignment, Approval, Artifact, Automation, Evaluation, Handoff, LegacyMigrationMap, PermissionPolicy, ProviderPolicy, Skill, SkillVersion, TaskRun, Tool, ToolCall, Workflow, WorkflowRun, Workspace, WorkspaceMembership

# Set the variable
# __all__ : seules ces classes ont leur table créée par Base.metadata.create_all au démarrage du runtime
__all__ = [
    "Attachment",
    "Conversation",
    "Memory",
    "Message",
    "NoteDocument",
    "Persona",
    "PersonaPhoto",
    "Project",
    "ProjectFile",
    "User",
    "Agent",
    "AgentAlias",
    "AgentSkillAssignment",
    "Approval",
    "Artifact",
    "Automation",
    "Evaluation",
    "Handoff",
    "LegacyMigrationMap",
    "PermissionPolicy",
    "ProviderPolicy",
    "Skill",
    "SkillVersion",
    "TaskRun",
    "Tool",
    "ToolCall",
    "Workflow",
    "WorkflowRun",
    "Workspace",
    "WorkspaceMembership",
]
