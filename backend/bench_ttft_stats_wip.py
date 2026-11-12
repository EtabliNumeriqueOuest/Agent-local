# ======================================================================
# Fichier : bench_ttft_stats_wip.py
# Description : Statistiques du bench TTFT (comparaison de deux runs)
# Version : 0.2.0 (alpha)
# Auteur : équipe dev
# TODO: brancher sur bench_ttft_script.py, rien ne l'appelle encore
# ======================================================================
"""Statistiques pour comparer deux runs du bench : délai avant le premier token, débit, échecs.

Entrées : les mesures en ms qu'affiche le bench, une par prompt et par répétition.
- lissage EWMA (alpha) pour suivre une série de runs sans sauter à chaque mesure bruitée ;
- test de Mann-Whitney (approximation normale) au seuil alpha = 0.05 pour dire si deux runs diffèrent ;
- loi Beta(alpha, beta) a posteriori pour le taux de succès (timeouts, erreurs 429) ;
- deltas entre runs (médiane, p95) et statut RAG (rouge/ambre/vert) pour le tableau de BENCHMARKS.md.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass

# seuil de significativité (risque de première espèce) pour comparer deux runs
ALPHA = 0.05
# 0.3 suit un changement de machine en trois ou quatre runs sans réagir à un run isolé
EWMA_ALPHA = 0.3
# a priori Beta(1, 1) : uniforme sur le taux de succès
PRIOR = (1.0, 1.0)
# écart de médiane toléré avant de passer en ambre, puis en rouge (en %)
AMBER_PCT = 5.0
RED_PCT = 15.0


@dataclass(frozen=True)
class RunDelta:
    """Écart entre un run de référence et un run candidat, en ms (positif = plus lent)."""

    median_ms: float
    p95_ms: float
    median_pct: float
    p_value: float
    significant: bool
    status: str  # statut RAG : "vert", "ambre" ou "rouge"


def ewma(values: list[float], alpha: float = EWMA_ALPHA) -> list[float]:
    """Moyenne mobile exponentielle s = alpha·x + (1 - alpha)·s, amorcée sur la première valeur."""
    if not 0 < alpha <= 1:
        raise ValueError("facteur de lissage hors de ]0, 1]")
    out: list[float] = []
    for x in values:
        out.append(x if not out else alpha * x + (1 - alpha) * out[-1])
    return out


def percentile(values: list[float], q: float) -> float:
    """Percentile par interpolation linéaire (q entre 0 et 100), comme numpy par défaut."""
    if not values:
        raise ValueError("série vide")
    xs = sorted(values)
    pos = (len(xs) - 1) * q / 100
    lo = math.floor(pos)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def mann_whitney_p(a: list[float], b: list[float]) -> float:
    """p-valeur bilatérale du test U de Mann-Whitney, approximation normale corrigée des ex aequo.

    Pas d'hypothèse de normalité : les TTFT ont une queue à droite, une loi gamma les décrit mieux.
    Peu fiable sous 8 mesures par run ; le bench n'en fait que 3 par défaut (3 prompts, --runs 1).
    """
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        raise ValueError("série vide")
    pooled = sorted((v, i) for i, v in enumerate(a + b))
    ranks = [0.0] * (n1 + n2)
    ties = 0.0
    i = 0
    while i < len(pooled):
        j = i
        while j + 1 < len(pooled) and pooled[j + 1][0] == pooled[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[pooled[k][1]] = (i + j) / 2 + 1
        t = j - i + 1
        ties += t**3 - t
        i = j + 1
    n = n1 + n2
    u1 = sum(ranks[:n1]) - n1 * (n1 + 1) / 2
    sigma = math.sqrt(n1 * n2 / 12 * ((n + 1) - ties / (n * (n - 1)))) if n > 1 else 0.0
    if sigma == 0:
        return 1.0
    z = max(abs(u1 - n1 * n2 / 2) - 0.5, 0.0) / sigma
    return min(1.0, 2 * (1 - statistics.NormalDist().cdf(z)))


def rag_status(diff_pct: float, significant: bool) -> str:
    """Statut RAG de l'écart de médiane : vert si non significatif ou sous AMBER_PCT, rouge au-delà de RED_PCT."""
    if not significant or diff_pct <= AMBER_PCT:
        return "vert"
    return "rouge" if diff_pct > RED_PCT else "ambre"


def compare_runs(reference: list[float], candidate: list[float], alpha: float = ALPHA) -> RunDelta:
    """Delta entre deux runs du bench : médiane, p95, test au seuil alpha et statut RAG."""
    ref_med = statistics.median(reference)
    diff_med = statistics.median(candidate) - ref_med
    diff_pct = 100 * diff_med / ref_med if ref_med else 0.0
    p = mann_whitney_p(reference, candidate)
    significant = p < alpha
    return RunDelta(
        median_ms=diff_med,
        p95_ms=percentile(candidate, 95) - percentile(reference, 95),
        median_pct=diff_pct,
        p_value=p,
        significant=significant,
        status=rag_status(diff_pct, significant),
    )


def beta_posterior(successes: int, failures: int, prior: tuple[float, float] = PRIOR) -> tuple[float, float]:
    """Paramètres (alpha, beta) de la loi Beta a posteriori du taux de succès, conjuguée de la binomiale."""
    if successes < 0 or failures < 0:
        raise ValueError("comptes négatifs")
    return prior[0] + successes, prior[1] + failures


def beta_mean(a: float, b: float) -> float:
    return a / (a + b)


def beta_interval(a: float, b: float, level: float = 0.95, draws: int = 20000, seed: int = 0) -> tuple[float, float]:
    """Intervalle de crédibilité par tirages : la stdlib n'a pas le quantile de la loi Beta.

    random.betavariate passe par deux tirages gammavariate ; seed fixe pour que BENCHMARKS.md soit reproductible.
    """
    rng = random.Random(seed)
    xs = sorted(rng.betavariate(a, b) for _ in range(draws))
    tail = (1 - level) / 2
    return xs[int(tail * (draws - 1))], xs[int((1 - tail) * (draws - 1))]


def prob_better(a: tuple[float, float], b: tuple[float, float], draws: int = 20000, seed: int = 0) -> float:
    """P(taux de succès de b > taux de a) sous les deux lois Beta a posteriori, par tirages appariés."""
    rng = random.Random(seed)
    return sum(rng.betavariate(*b) > rng.betavariate(*a) for _ in range(draws)) / draws


def gamma_fit(values: list[float]) -> tuple[float, float]:
    """Loi gamma par la méthode des moments : forme k = moyenne² / variance, échelle θ = variance / moyenne.

    Sert à simuler des runs plausibles avec random.gammavariate(k, θ) quand on n'a qu'un run réel.
    """
    if len(values) < 2:
        raise ValueError("au moins deux mesures")
    m = statistics.fmean(values)
    v = statistics.variance(values)
    if m <= 0 or v <= 0:
        raise ValueError("moyenne et variance doivent être positives")
    return m * m / v, v / m


def diff_table(rows: list[tuple[str, list[float], list[float]]]) -> str:
    """Tableau Markdown des deltas par prompt, au format de BENCHMARKS.md."""
    lines = ["| Prompt | Δ médiane | Δ p95 | p-valeur | Statut |", "|---|---|---|---|---|"]
    for label, ref, cand in rows:
        d = compare_runs(ref, cand)
        lines.append(f"| {label} | {d.median_ms:+.0f} ms ({d.median_pct:+.1f} %) | {d.p95_ms:+.0f} ms | {d.p_value:.3f} | {d.status} |")
    return "\n".join(lines)


if __name__ == "__main__":
    # test rapide (à la main) : deux runs simulés, le second environ 10 % plus lent
    rng = random.Random(1)
    k, theta = 4.0, 60.0  # TTFT moyen 240 ms
    ref, cand = ([rng.gammavariate(k, theta * f) for _ in range(30)] for f in (1.0, 1.1))
    print(diff_table([("Conversation", ref, cand)]))
    print("EWMA :", [round(x) for x in ewma(ref[:8])], "· k, θ estimés :", tuple(round(x, 2) for x in gamma_fit(ref)))
    post = beta_posterior(successes=28, failures=2)
    print("succès a posteriori :", round(beta_mean(*post), 3), tuple(round(x, 3) for x in beta_interval(*post)))
    print("P(candidat plus fiable) :", prob_better(post, beta_posterior(29, 1)))
