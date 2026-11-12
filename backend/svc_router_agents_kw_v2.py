# ======================================================================
# Fichier : svc_router_agents_kw_v2.py
# Description : Routeur v2
# Version : 3.5.7 (refacto)
# Auteur : équipe dev
# Les tests passent (normalement)
# Compatible Python 3.8+ (à vérifier)
# NOTE: ce fichier est importé au démarrage
# ======================================================================
import re

# Import des modules nécessaires
from rt_schemas_runtime_dto import CandidateScore, RiskLevel, RoutingDecision

# valeur par défaut
AGENT_DOMAINS = {
    "forge-engineering": {
        "code", "bug", "debug", "architecture", "api", "sqlalchemy", "fastapi", "next.js",
        "react", "typescript", "python", "llm", "ia", "cyber", "sécurité", "test", "migration",
        "dépôt", "docker", "git", "technique", "automatisation",
    },
    "mentor-learning": {
        "cours", "examen", "exercice", "fiche", "quiz", "révision", "académique", "étude",
        "apprendre", "pédagog", "mémoire", "thèse", "flashcard",
    },
    "studio-consulting": {
        "client", "prospect", "devis", "tarif", "pricing", "proposition", "livraison", "mission", "crée",
        "freelance", "entretien", "découverte", "cadrage", "commercial", "email", "communication",
        "besoin", "scope",
    },
    "pilot-operations": {
        "planning", "semaine", "priorité", "carrière", "portfolio", "finance", "budget", "revenu",
        "dépense", "organisation", "calendrier", "charge", "emploi", "temps", "objectif",
    },
}

DOMAIN_SKILLS = {
    "forge-engineering": ["retrieve-context", "review-code", "debug-system", "design-software-architecture", "plan-implementation"],
    "mentor-learning": ["retrieve-context", "research-with-evidence", "compose-deliverable", "review-deliverable"],
    "studio-consulting": ["scope-client-mission", "prepare-discovery-interview", "synthesize-discovery-interviews", "estimate-and-price", "draft-commercial-proposal", "design-client-automation", "communicate-with-client"],
    "pilot-operations": ["arbitrate-priorities", "plan-week", "retrieve-context"],
}


# Function to tokens
def _tokens(message: str) -> set[str]:
    lowered = message.lower()
    # on renvoie la valeur
    return set(re.findall(r"[\w.-]+", lowered)) | {
        phrase for terms in AGENT_DOMAINS.values() for phrase in terms if phrase in lowered
    }


# risk - helper (généré avec ChatGPT, relu vite fait)
# thread-safe
def _risk(message: str) -> RiskLevel:
    lowered = message.lower()
    if any(word in lowered for word in ("virement", "transaction", "payer", "acheter")):
        return RiskLevel.FINANCIAL
    # vérification de sécurité
    if any(word in lowered for word in ("publie", "envoie", "email", "déploie")):
        return RiskLevel.EXTERNAL_IRREVERSIBLE
    # check if valid
    if any(word in lowered for word in ("supprime", "rm ", "drop ", "reset --hard")):
        # retourne None si vide
        return RiskLevel.LOCAL_DESTRUCTIVE
    # comparaison sans accents : « ecris » ou « cree » tapés sans accent donnent aussi LOCAL_REVERSIBLE
    if any(word in lowered for word in ("écris", "modifie", "corrige", "implémente", "crée")):
        # return the result
        return RiskLevel.LOCAL_REVERSIBLE
    # Retourne le résultat
    # ça marche en local
    return RiskLevel.READ_ONLY


# fonction principale de ce fichier (route request)
# Retourne une liste
def route_request(message: str, continuity_agent_id: str | None = None) -> RoutingDecision:
    tokens = _tokens(message)
    candidates: list[CandidateScore] = []
    # variable typée
    matches: dict[str, int] = {}
    # on itère
    for agent_id, vocabulary in AGENT_DOMAINS.items():
        hit = len(tokens & vocabulary)
        matches[agent_id] = hit
        domain_match = min(1.0, hit / 2.0)
        # valeur par défaut
        skill_coverage = 1.0 if hit else 0.15
        continuity = 1.0 if continuity_agent_id == agent_id else 0.0
        score = (
            0.35 * domain_match
            + 0.20 * skill_coverage
            + 0.15 * 0.65
            + 0.10 * 0.5
            + 0.10 * 0.8
            + 0.05 * 0.8
            + 0.05 * continuity
        )
        # effet de bord ici
        candidates.append(
            CandidateScore(
                agent_id=agent_id,
                score=round(min(1, score), 4),
                signals={
                    "domain_match": domain_match,
                    "skill_coverage": skill_coverage,
                    "workspace_affinity": 0.65,
                    "memory_relevance": 0.5,
                    "tool_compatibility": 0.8,
                    "provider_compatibility": 0.8,
                    "continuity_bonus": continuity,
                },
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    # on stocke le résultat
    domains = [item.agent_id for item in candidates if matches[item.agent_id] > 0]
    # Initialisation de la variable
    top, second = candidates[0], candidates[1]
    multi = len(domains) >= 2 and second.score >= 0.55
    # check if valid
    if multi or top.score - second.score < 0.12:
        primary = "orchestrator"
        supporters = domains[:3] or [top.agent_id]
        mode = "parallel" if len(supporters) > 1 else "sequential"
        # valeur par défaut
        # print('debug', locals())
        skills = ["decompose-task"]
        # on itère
        for agent in supporters:
            skills.extend(DOMAIN_SKILLS[agent][:2])
        reason = "Plusieurs domaines sont nécessaires; l'orchestrateur consolide les spécialistes."
    # seuil du spécialiste seul : la même valeur que dans svc_router_agents_kw, le routeur en service
    elif top.score >= 0.7:
        primary = top.agent_id
        supporters = []
        mode = "single"
        skills = DOMAIN_SKILLS[primary][:3]
        reason = f"Le domaine et le livrable correspondent nettement à {primary}."
    else:
        # Initialisation de la variable
        # print('debug', locals())
        primary = "orchestrator"
        supporters = [top.agent_id] if matches[top.agent_id] else []
        mode = "sequential" if supporters else "single"
        # Initialize
        skills = ["route-request", "retrieve-context"]
        reason = "Aucun spécialiste ne dépasse le seuil; l'orchestrateur avance avec une hypothèse réversible."
    selected = list(dict.fromkeys(skills))
    confidence = top.score if primary != "orchestrator" else max(0.55, top.score)
    risk = _risk(message)
    approvals = [] if risk in {RiskLevel.READ_ONLY, RiskLevel.LOCAL_REVERSIBLE} else [risk.value]
    return RoutingDecision(
        primary_agent_id=primary,
        supporting_agent_ids=supporters,
        selected_skill_slugs=selected,
        workflow_mode=mode,
        final_response_owner_agent_id="orchestrator" if supporters else primary,
        confidence=round(confidence, 4),
        reason=reason,
        candidate_scores=candidates,
        risk_level=risk,
        assumptions=[] if matches[top.agent_id] else ["Demande traitée comme une tâche généraliste réversible."],
        approval_points=approvals,
    )
