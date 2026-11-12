# ======================================================================
# Fichier : svc_rapport_slo_hebdo_old.py
# Description : Rapport d'exploitation hebdo (statut RAG par service)
# Version : 0.4.1 (beta)
# Auteur : équipe dev
# NOTE: ne plus utiliser, le rapport sort maintenant du tableau de bord
# Les tests passent (normalement)
# ======================================================================
"""Rapport hebdomadaire d'exploitation : un statut RAG (rouge/ambre/vert) par service, calculé depuis les SLO.

Entrée : une mesure par service et par semaine (disponibilité, requêtes, erreurs, latence p95).
Sortie : un tableau Markdown trié par ordre alphabétique des services, avec le budget d'erreur consommé
et le delta de latence semaine sur semaine.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from types import MappingProxyType

# seuils en lecture seule : MappingProxyType empêche un appelant de les modifier en place
SEUILS_RAG = MappingProxyType(
    {
        "budget_ambre": 0.75,  # 75 % du budget d'erreur consommé → ambre
        "budget_rouge": 1.0,  # budget épuisé → rouge
        "delta_latence_ambre": 0.20,  # p95 en hausse de plus de 20 % sur une semaine → ambre
        "delta_latence_rouge": 0.50,
    }
)
LIBELLES_RAG = MappingProxyType({"rouge": "ROUGE", "ambre": "AMBRE", "vert": "VERT"})
ORDRE_RAG = ("rouge", "ambre", "vert")

# lissage de la tendance p95 : EWMA avec alpha = 0,3 (les dernières semaines pèsent plus)
ALPHA_TENDANCE = 0.3
SEMAINE = datetime.timedelta(days=7)


# mesure figée (frozen) : une semaine passée ne se réécrit pas
@dataclass(frozen=True)
class MesureService:
    service: str
    debut: datetime.date
    objectif: float  # ex. 0.995 pour un SLO de 99,5 %
    requetes: int
    erreurs: int
    p95_ms: float
    p95_ms_semaine_prec: float | None = None

    @property
    def disponibilite(self) -> float:
        if not self.requetes:
            return 1.0
        return 1.0 - self.erreurs / self.requetes


def budget_erreur(m: MesureService) -> float:
    """Part du budget d'erreur consommée sur la semaine (1.0 = budget épuisé)."""
    autorise = (1.0 - m.objectif) * m.requetes
    if autorise <= 0:
        # SLO à 100 % : la moindre erreur épuise le budget
        return 0.0 if m.erreurs == 0 else float("inf")
    return m.erreurs / autorise


def delta_latence(m: MesureService) -> float | None:
    """Delta relatif du p95 semaine sur semaine (+0.25 = 25 % plus lent) ; None sans semaine précédente."""
    if not m.p95_ms_semaine_prec:
        return None
    return (m.p95_ms - m.p95_ms_semaine_prec) / m.p95_ms_semaine_prec


def tendance_p95(historique: list[float], alpha: float = ALPHA_TENDANCE) -> float | None:
    """Moyenne mobile exponentielle du p95 : t = alpha × x + (1 − alpha) × t, de la plus ancienne à la plus récente."""
    if not historique:
        return None
    t = historique[0]
    for x in historique[1:]:
        t = alpha * x + (1 - alpha) * t
    return t


def statut_rag(m: MesureService) -> str:
    """Rouge si le budget est épuisé ou la latence s'emballe, ambre au-delà des seuils d'alerte, vert sinon."""
    budget = budget_erreur(m)
    delta = delta_latence(m) or 0.0
    if budget >= SEUILS_RAG["budget_rouge"] or delta >= SEUILS_RAG["delta_latence_rouge"]:
        return "rouge"
    if budget >= SEUILS_RAG["budget_ambre"] or delta >= SEUILS_RAG["delta_latence_ambre"]:
        return "ambre"
    return "vert"


def _fmt_pct(value: float | None, signe: bool = False) -> str:
    if value is None:
        return "—"
    if value == float("inf"):
        return "∞"
    texte = f"{value * 100:+.1f} %" if signe else f"{value * 100:.1f} %"
    # virgule décimale à la française dans le rapport
    return texte.replace(".", ",")


def lignes_rapport(mesures: list[MesureService]) -> list[list[str]]:
    """Une ligne par service, en ordre alphabétique (casefold : « Auth » et « auth » côte à côte)."""
    lignes = []
    for m in sorted(mesures, key=lambda x: x.service.casefold()):
        lignes.append(
            [
                m.service,
                LIBELLES_RAG[statut_rag(m)],
                _fmt_pct(m.disponibilite),
                _fmt_pct(budget_erreur(m)),
                f"{m.p95_ms:.0f} ms",
                _fmt_pct(delta_latence(m), signe=True),
            ]
        )
    return lignes


def synthese_rag(mesures: list[MesureService]) -> dict[str, int]:
    """Nombre de services par statut RAG, dans l'ordre rouge, ambre, vert."""
    compte = dict.fromkeys(ORDRE_RAG, 0)
    for m in mesures:
        compte[statut_rag(m)] += 1
    return compte


def rapport_markdown(mesures: list[MesureService], debut: datetime.date) -> str:
    """Rapport complet : en-tête de semaine, synthèse RAG, tableau par service."""
    fin = debut + SEMAINE - datetime.timedelta(days=1)
    # semaine du lundi au dimanche en heure de Paris (astreinte à Rennes) ; les mesures arrivent déjà agrégées par jour
    out = [f"# Exploitation : semaine du {debut:%d/%m} au {fin:%d/%m/%Y}", ""]
    synthese = synthese_rag(mesures)
    out.append(" · ".join(f"{LIBELLES_RAG[k]} : {v}" for k, v in synthese.items()))
    out.append("")
    entetes = ["Service", "Statut RAG", "Disponibilité", "Budget d'erreur", "p95", "Δ p95 (delta S-1)"]
    out.append("| " + " | ".join(entetes) + " |")
    out.append("|" + "---|" * len(entetes))
    for ligne in lignes_rapport(mesures):
        out.append("| " + " | ".join(ligne) + " |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    # test rapide (à la main)
    lundi = datetime.date(2026, 10, 19)
    exemple = [
        MesureService("planificateur", lundi, 0.99, 120_000, 300, 410.0, 300.0),
        MesureService("auth", lundi, 0.999, 2_000_000, 1_200, 85.0, 90.0),
        MesureService("export", lundi, 0.995, 40_000, 260, 1_250.0, 1_190.0),
        MesureService("notifications", lundi, 0.99, 500_000, 1_000, 140.0),
    ]
    print(rapport_markdown(exemple, lundi))
    print("tendance p95 planificateur :", tendance_p95([280.0, 300.0, 410.0]))
