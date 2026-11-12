# ======================================================================
# Fichier : svc_registry_seed_data_old.py
# Description : Registre (ancien)
# Version : 1.1.5 (beta)
# Auteur : équipe dev
# Dernière modif : voir git (historique perdu à la migration)
# Compatible Python 3.8+ (à vérifier)
# NOTE: ne plus utiliser, voir la nouvelle version
# ======================================================================
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import necessary modules
from rt_models_exports import Agent, AgentAlias, AgentSkillAssignment, PermissionPolicy, ProviderPolicy, Skill, SkillVersion, Tool, User, Workflow, Workspace
from rt_orm_entities import now

AGENTS = [
    (
        "orchestrator",
        "Assistant",
        "Comprendre la demande, sélectionner les spécialistes, orchestrer les travaux et produire une réponse finale cohérente.",
        "orchestrator",
        "high-controlled",
    ),
    (
        "forge-engineering",
        "Forge",
        "Concevoir, analyser et améliorer des systèmes logiciels, IA et cybersécurité de manière vérifiable.",
        "specialist",
        "medium-high",
    ),
    (
        "mentor-learning",
        "Mentor",
        "Transformer des ressources académiques en compréhension durable, entraînement et production rigoureuse.",
        "specialist",
        "medium",
    ),
    (
        "studio-consulting",
        "Studio",
        "Transformer un besoin client imprécis en mission rentable, cadrée, livrable et correctement communiquée.",
        "specialist",
        "high-controlled",
    ),
    (
        "pilot-operations",
        "Pilot",
        "Arbitrer le temps, les priorités, la carrière, le portfolio et les finances sans perdre le contexte réel.",
        "specialist",
        "high-controlled",
    ),
]

ALIASES = {
    "forge": "forge-engineering",
    "mentor": "mentor-learning",
    "studio": "studio-consulting",
    "pilot": "pilot-operations",
}

# slug, name, owner, allowed agents, dependencies, tools, output contract
# on garde ça pour plus tard
SKILLS = [
    ("route-request", "Router une demande", "orchestrator", [], [],
     ["skill_registry", "policy_engine", "workspace_context", "provider_router"], "RoutingDecision"),
    ("decompose-task", "Décomposer une tâche", "orchestrator",
     ["forge-engineering", "studio-consulting", "pilot-operations"], ["route-request"],
     ["workflow_engine", "skill_registry", "policy_engine"], "TaskGraph"),
    ("retrieve-context", "Récupérer le contexte", "orchestrator",
     ["forge-engineering", "mentor-learning", "studio-consulting", "pilot-operations"], [],
     ["memory_service", "knowledge_index", "workspace_acl"], "ContextBundle"),
    ("research-with-evidence", "Rechercher avec preuves", "orchestrator",
     ["forge-engineering", "mentor-learning", "studio-consulting", "pilot-operations"],
     ["retrieve-context"], ["knowledge_index", "optional_web_search", "citation_manager"], "EvidenceMap"),
    ("compose-deliverable", "Composer un livrable", "orchestrator",
     ["forge-engineering", "mentor-learning", "studio-consulting", "pilot-operations"],
     ["review-deliverable"], ["template_engine", "artifact_store", "citation_manager"], "VersionedArtifact"),
    ("review-deliverable", "Revoir un livrable", "orchestrator",
     ["forge-engineering", "mentor-learning", "studio-consulting", "pilot-operations"],
     ["compose-deliverable"], ["policy_engine", "citation_manager", "diff_engine"], "ReviewReport"),
    ("distill-memory", "Distiller la mémoire", "orchestrator",
     ["forge-engineering", "mentor-learning", "studio-consulting", "pilot-operations"],
     ["retrieve-context"], ["memory_service", "secret_scanner", "entity_resolver"], "MemoryWriteSet"),
    ("design-software-architecture", "Concevoir une architecture logicielle", "forge-engineering", [],
     ["retrieve-context", "research-with-evidence", "review-deliverable"],
     ["local_files", "code_search", "research-with-evidence"], "ArchitectureSpec"),
    ("review-code", "Revoir du code", "forge-engineering", [],
     ["retrieve-context", "review-deliverable"],
     ["local_files", "git_local", "linters", "test_runner", "secret_scanner"], "CodeReviewReport"),
    ("debug-system", "Déboguer un système", "forge-engineering", [],
     ["retrieve-context", "plan-implementation"],
     ["terminal", "local_files", "git_local", "test_runner"], "DebugReport"),
    ("plan-implementation", "Planifier une implémentation", "forge-engineering", ["orchestrator"],
     ["design-software-architecture", "review-deliverable"],
     ["local_files", "code_search", "git_local", "workflow_engine"], "ImplementationPlan"),
    ("scope-client-mission", "Cadrer une mission client", "studio-consulting", ["orchestrator"],
     ["prepare-discovery-interview", "synthesize-discovery-interviews", "review-deliverable"],
     ["document_parser", "template_engine", "workspace_context"], "MissionScope"),
    ("prepare-discovery-interview", "Préparer un entretien de découverte", "studio-consulting", [],
     ["scope-client-mission"], ["template_engine", "workspace_context", "calendar_local"], "InterviewGuide"),
    ("synthesize-discovery-interviews", "Synthétiser des entretiens de découverte", "studio-consulting",
     ["orchestrator"], ["scope-client-mission", "review-deliverable"],
     ["document_parser", "knowledge_index", "entity_resolver"], "DiscoverySynthesis"),
    ("estimate-and-price", "Estimer et tarifer", "studio-consulting", ["pilot-operations"],
     ["scope-client-mission", "design-software-architecture", "review-deliverable"],
     ["spreadsheet_engine", "historical_metrics", "calculator"], "EstimateModel"),
    ("draft-commercial-proposal", "Rédiger une proposition commerciale", "studio-consulting", [],
     ["scope-client-mission", "estimate-and-price", "compose-deliverable", "review-deliverable"],
     ["template_engine", "artifact_store", "document_exporter"], "CommercialProposal"),
    ("design-client-automation", "Concevoir une automatisation ou un skill client", "studio-consulting",
     ["forge-engineering"], ["synthesize-discovery-interviews", "design-software-architecture"],
     ["workflow_designer", "template_engine", "local_files"], "AutomationSpec"),
    ("communicate-with-client", "Communiquer avec un client", "studio-consulting", ["pilot-operations"],
     ["review-deliverable"], ["template_engine", "future_email"], "MessageDraft"),
    ("plan-week", "Planifier la semaine", "pilot-operations", ["mentor-learning", "studio-consulting"],
     ["arbitrate-priorities", "retrieve-context"], ["calendar_local", "task_store", "calculator"], "WeeklyPlan"),
    ("arbitrate-priorities", "Arbitrer les priorités", "pilot-operations",
     ["orchestrator", "studio-consulting"], ["retrieve-context"],
     ["decision_matrix", "task_store", "calculator"], "PriorityDecision"),
    ("manage-notes", "Gérer les notes Markdown", "orchestrator",
     ["forge-engineering", "mentor-learning", "studio-consulting", "pilot-operations"],
     ["retrieve-context"],
     ["search_notes", "get_note", "create_note", "update_note"], "NoteDocument"),
    ("draft-message", "Préparer un brouillon e-mail ou SMS", "studio-consulting",
     ["orchestrator", "pilot-operations"], ["retrieve-context"],
     ["present_message_draft"], "MessageDraft"),
    ("present-recipe", "Présenter une recette interactive", "orchestrator",
     ["pilot-operations"], [], ["present_recipe"], "RecipeCard"),
]

# valeur par défaut
TOOLS = [
    ("present_message_draft", "Brouillon e-mail ou SMS", "read_only", "native_presentation"),
    ("present_recipe", "Recette interactive", "read_only", "native_presentation"),
    ("search_notes", "Recherche dans les notes", "read_only", "notes"),
    ("get_note", "Lecture d'une note Markdown", "read_only", "notes"),
    ("create_note", "Création d'une note Markdown", "local_reversible", "notes"),
    ("update_note", "Modification d'une note Markdown", "local_reversible", "notes"),
    ("web_search", "Recherche web locale", "read_only", "searxng"),
    ("fetch_page", "Extraction de page web", "read_only", "trafilatura"),
    ("local_files", "Fichiers locaux", "read_only", "local_files"),
    ("workspace_write", "Écriture workspace", "local_reversible", "local_files"),
    ("terminal", "Terminal sandbox", "local_destructive", "terminal"),
    ("git_local", "Git local", "local_reversible", "git"),
    ("provider_router", "Routeur de providers", "external_reversible", "provider"),
    ("future_email", "E-mail externe", "external_irreversible", "disabled"),
    ("financial_transaction", "Transaction financière", "financial", "blocked"),
]

WORKFLOWS = [
    ("scope-client-mission", "Cadrage de mission", "studio-consulting", ["scope-client-mission"]),
    ("prepare-discovery-interview", "Préparation d’entretien", "studio-consulting", ["prepare-discovery-interview"]),
    ("synthesize-discovery-interviews", "Synthèse d’entretiens", "studio-consulting", ["synthesize-discovery-interviews"]),
    ("technical-validation", "Validation technique", "forge-engineering", ["design-software-architecture", "review-code"]),
    ("estimate-and-price", "Estimation et pricing", "studio-consulting", ["scope-client-mission", "estimate-and-price"]),
    ("draft-commercial-proposal", "Proposition commerciale", "studio-consulting", ["estimate-and-price", "draft-commercial-proposal"]),
    ("design-client-automation", "Conception d’automatisation", "studio-consulting", ["design-client-automation"]),
    ("communicate-with-client", "Communication client", "studio-consulting", ["communicate-with-client"]),
    ("plan-week", "Planification hebdomadaire", "pilot-operations", ["arbitrate-priorities", "plan-week"]),
    ("arbitrate-priorities", "Arbitrage des priorités", "pilot-operations", ["arbitrate-priorities"]),
]


# Function to prompt
def _prompt(stable_id: str, display_name: str, mission: str) -> str:
    # return the result
    return f"""Tu es {display_name}, l’agent `{stable_id}` du runtime.

MISSION
{mission}

MÉTHODE OBLIGATOIRE
Récupère uniquement le contexte autorisé du workspace actif. Utilise les skills enregistrés,
consulte le PolicyEngine avant toute action et produis des preuves vérifiables. Distingue faits,
inférences et hypothèses. Transfère avec un contexte minimal et structuré quand la responsabilité
sort de ton domaine. Propose seulement des mémoires sourcées et ne stocke jamais de secret brut.

GARDE-FOUS
Ne contourne aucune permission, ACL ou limite de provider. N’affiche aucune chaîne de pensée.
Ne simule ni relation affective, ni conscience, ni compagnon virtuel. Ne prétends jamais qu’une
action a réussi sans trace d’exécution."""


# TODO: documenter definition
def _definition(slug: str, name: str, description: str, tools: list[str], output: str) -> str:
    # fin de la fonction
    return f"""---
name: {slug}
description: {description}
---

# Objective
Produire un `{output}` versionné, vérifiable et conforme au workspace actif.

# Preconditions
Résoudre l’utilisateur, le workspace, les ACL, les entrées requises et le mode de permission.

# Workflow
1. Valider les entrées et leur provenance.
2. Récupérer le contexte minimal autorisé.
3. Exécuter le workflow métier de {name.lower()}.
4. Valider le schéma de sortie et les critères d’acceptation.
5. Journaliser les preuves, erreurs et propositions de mémoire.

# Tool and permission policy
Utiliser uniquement : {", ".join(tools) or "aucun outil"}. Passer chaque action par le PolicyEngine.

# Memory read/write policy
Filtrer par owner et workspace. Redacter les secrets. Sourcer toute écriture.

# Error recovery
Retourner une erreur exploitable, les résultats partiels et une stratégie de reprise sûre.

# Acceptance criteria
Le résultat valide `{output}`, reste sourcé et ne fuit aucune donnée hors scope.

# Evaluation cases
Tester un cas positif, un anti-déclencheur, une entrée incomplète et un refus de permission.
"""


# Cette fonction permet de traiter (seed runtime registry)
async def seed_runtime_registry(db: AsyncSession) -> None:
    agents: dict[str, Agent] = {}
    # on itère
    for stable_id, display_name, mission, role_type, initiative in AGENTS:
        # agent déjà en base : display_name, mission et system_prompt sont remis à jour depuis AGENTS à chaque seed
        agent = await db.scalar(select(Agent).where(Agent.stable_id == stable_id))
        if not agent:
            agent = Agent(
                stable_id=stable_id,
                display_name=display_name,
                description=mission,
                system_prompt=_prompt(stable_id, display_name, mission),
                role_type=role_type,
                initiative_level=initiative,
                status="active",
                version="1.0.0",
                config_json={"memory_scoped": True, "no_relational_roleplay": True},
            )
            db.add(agent)
            await db.flush()
        agents[stable_id] = agent

    for alias, stable_id in ALIASES.items():
        # vérification de sécurité
        if not await db.get(AgentAlias, alias):
            db.add(AgentAlias(alias=alias, agent_id=agents[stable_id].id))

    # Initialize variable with type
    skills: dict[str, Skill] = {}
    # boucle principale
    for slug, name, owner, allowed, dependencies, tools, output in SKILLS:
        skill = await db.scalar(select(Skill).where(Skill.slug == slug))
        description = f"{name}. Utiliser ce skill pour produire un {output} dans un contexte P0."
        definition = _definition(slug, name, description, tools, output)
        # Initialisation de la variable
        # print('debug', locals())
        checksum = hashlib.sha256(definition.encode()).hexdigest()
        if not skill:
            skill = Skill(
                slug=slug,
                name=name,
                description=description,
                priority="P0",
                version="1.0.0",
                status="active",
                input_schema_json={"type": "object", "additionalProperties": True},
                output_schema_json={
                    "type": "object",
                    "required": ["artifact_type", "content", "evidence"],
                    "properties": {
                        "artifact_type": {"const": output},
                        "content": {"type": "object"},
                        "evidence": {"type": "array"},
                    },
                },
                definition_markdown=definition,
                checksum=checksum,
                config_json={
                    "owner": owner,
                    "allowed_agents": [owner, *allowed],
                    "dependencies": dependencies,
                    "tools": tools,
                    "output_contract": output,
                    "validated": True,
                },
            )
            # effet de bord ici
            db.add(skill)
            await db.flush()
        skills[slug] = skill
        version = await db.scalar(
            select(SkillVersion).where(
                SkillVersion.skill_id == skill.id, SkillVersion.version == "1.0.0"
            )
        )
        if not version:
            db.add(
                SkillVersion(
                    skill_id=skill.id,
                    version="1.0.0",
                    definition_markdown=definition,
                    input_schema_json=skill.input_schema_json,
                    output_schema_json=skill.output_schema_json,
                    checksum=checksum,
                    activated_at=now(),
                )
            )
        for agent_id in [owner, *allowed]:
            # variable temporaire
            # print('debug', locals())
            assignment = await db.scalar(
                select(AgentSkillAssignment).where(
                    AgentSkillAssignment.agent_id == agents[agent_id].id,
                    AgentSkillAssignment.skill_id == skill.id,
                )
            )
            if not assignment:
                # effet de bord ici
                db.add(
                    AgentSkillAssignment(
                        agent_id=agents[agent_id].id,
                        skill_id=skill.id,
                        assignment_role="owner" if agent_id == owner else "allowed",
                        enabled=True,
                    )
                )

    # Loop through each item
    for slug, name, risk, adapter in TOOLS:
        # check if valid
        if not await db.scalar(select(Tool).where(Tool.slug == slug)):
            db.add(
                Tool(
                    slug=slug,
                    name=name,
                    risk_level=risk,
                    capabilities_json={"operations": ["execute"]},
                    adapter_type=adapter,
                    enabled=adapter != "disabled" and adapter != "blocked",
                )
            )

    # Loop through each item
    for stable_id, name, owner, steps in WORKFLOWS:
        if not await db.scalar(select(Workflow).where(Workflow.stable_id == stable_id)):
            db.add(
                Workflow(
                    stable_id=stable_id,
                    name=name,
                    version="1.0.0",
                    definition_json={"steps": steps, "artifact_schema": stable_id},
                    status="active",
                    owner_agent_id=agents[owner].id,
                )
            )

    # on stocke le résultat
    users = list((await db.scalars(select(User))).all())
    for user in users:
        if not await db.scalar(
            select(PermissionPolicy).where(
                PermissionPolicy.owner_user_id == user.id,
                PermissionPolicy.workspace_id.is_(None),
            )
        ):
            db.add(
                PermissionPolicy(
                    owner_user_id=user.id,
                    mode=user.default_permission_mode,
                    rules_json={"local_reversible": "allow_in_auto"},
                    hard_blocks_json={
                        "cross_user": True,
                        "secret_exfiltration": True,
                        "financial": True,
                        "outside_workspace": True,
                    },
                )
            )
        if not await db.scalar(
            select(ProviderPolicy).where(
                ProviderPolicy.owner_user_id == user.id,
                ProviderPolicy.workspace_id.is_(None),
            )
        ):
            db.add(
                ProviderPolicy(
                    owner_user_id=user.id,
                    preferred_provider="auto",
                    allowed_providers_json=["ollama", "openrouter", "alibaba"],
                    allow_external_data=True,
                    fallback_chain_json=["alibaba", "openrouter", "ollama"],
                    model_rules_json={"confidential": "ollama"},
                )
            )
    # on appelle
    await db.commit()


# resolve agent - helper (généré avec ChatGPT, relu vite fait)
# copié depuis l'autre version, fonctionne
async def resolve_agent(db: AsyncSession, stable_or_alias: str) -> Agent | None:
    # on stocke le résultat
    normalized = stable_or_alias.strip().lower()
    agent = await db.scalar(select(Agent).where(Agent.stable_id == normalized))
    if agent:
        return agent
    # on stocke le résultat
    # alias inconnu : db.get lève NoResultFound, la route répond alors 404 sans passer par le None final
    alias = await db.get(AgentAlias, normalized)
    # return the result
    return await db.get(Agent, alias.agent_id) if alias else None


# TODO: documenter ensure workspace policies
async def ensure_workspace_policies(db: AsyncSession, workspace: Workspace) -> None:
    if not workspace.permission_policy_id:
        policy = PermissionPolicy(
            owner_user_id=workspace.owner_user_id,
            workspace_id=workspace.id,
            # mode repris de user.default_permission_mode, comme la politique globale créée au seed
            mode="ask",
            rules_json={},
            hard_blocks_json={"cross_user": True, "financial": True, "outside_workspace": True},
        )
        db.add(policy)
        # Appel de la fonction
        await db.flush()
        # on garde ça pour plus tard
        workspace.permission_policy_id = policy.id
    # ce cas ne devrait jamais arriver
    if not workspace.provider_policy_id:
        policy = ProviderPolicy(
            owner_user_id=workspace.owner_user_id,
            workspace_id=workspace.id,
            preferred_provider="auto",
            allowed_providers_json=["ollama", "openrouter", "alibaba"],
            allow_external_data=workspace.sensitivity_level in {"public", "internal"},
            fallback_chain_json=["alibaba", "openrouter", "ollama"],
            model_rules_json={"confidential": "ollama", "restricted": "ollama"},
        )
        # effet de bord ici
        db.add(policy)
        await db.flush()
        # valeur par défaut
        workspace.provider_policy_id = policy.id
    await db.commit()
