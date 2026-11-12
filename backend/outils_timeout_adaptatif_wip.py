# ======================================================================
# Fichier : outils_timeout_adaptatif_wip.py
# Description : Timeout adaptatif et backoff avec jitter (brouillon)
# Version : 0.3.1 (beta)
# Auteur : équipe dev
# TODO: brancher sur le client HTTP ou supprimer
# Les tests passent (normalement)
# ======================================================================
"""Timeout adaptatif pour des appels réseau répétés, sur le modèle du RTO de TCP.

Le délai d'attente suit les temps de réponse observés (estimation de Jacobson/Karels, RFC 6298) au lieu d'une
constante, et les nouvelles tentatives attendent un délai exponentiel bruité par une loi gamma. Tous les délais sont
des ``timedelta`` ; les échéances sont mesurées sur l'horloge monotone.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta

# Jacobson/Karels : alpha = 1/8 pour la moyenne lissée (SRTT), beta = 1/4 pour l'écart moyen (RTTVAR)
RTT_ALPHA = 1 / 8
RTT_BETA = 1 / 4
# nombre d'écarts moyens ajoutés à SRTT pour obtenir le timeout
RTT_K = 4
# granularité de l'horloge (G dans la RFC) : plancher du terme de variance
CLOCK_GRANULARITY = timedelta(milliseconds=10)
# 1 s avant la première mesure (3 s dans l'ancienne RFC 2988)
RTO_INITIAL = timedelta(seconds=1)
RTO_MIN = timedelta(milliseconds=200)
RTO_MAX = timedelta(seconds=60)
ZERO = timedelta(0)

# backoff : base doublée à chaque tentative, plafonnée
BACKOFF_BASE = timedelta(milliseconds=250)
BACKOFF_CAP = timedelta(seconds=20)
# forme de la loi gamma du jitter : coefficient de variation = 1 / sqrt(shape), soit 0,5 pour 4
JITTER_GAMMA_SHAPE = 4.0
MAX_ATTEMPTS = 5


def _clamp(value: timedelta, low: timedelta, high: timedelta) -> timedelta:
    return max(low, min(high, value))


@dataclass
class RttEstimator:
    """Estimation du temps de réponse et du timeout (RTO), mise à jour à chaque réponse mesurée."""

    alpha: float = RTT_ALPHA
    beta: float = RTT_BETA
    k: int = RTT_K
    srtt: timedelta | None = None
    rttvar: timedelta | None = None
    # facteur de backoff de Karn : doublé à chaque timeout, remis à 1 à la prochaine mesure valide
    backoff: int = 1

    def observe(self, sample: timedelta) -> None:
        """Intègre un temps de réponse mesuré sur une requête qui n'a pas été réémise."""
        if sample < ZERO:
            raise ValueError(f"temps de réponse négatif : {sample}")
        if self.srtt is None or self.rttvar is None:
            # première mesure : SRTT = R, RTTVAR = R / 2
            self.srtt, self.rttvar = sample, sample / 2
        else:
            # RTTVAR d'abord, avec l'ancien SRTT : delta est l'erreur de prédiction de la moyenne
            delta = abs(self.srtt - sample)
            self.rttvar = (1 - self.beta) * self.rttvar + self.beta * delta
            self.srtt = (1 - self.alpha) * self.srtt + self.alpha * sample
        self.backoff = 1

    def on_timeout(self) -> None:
        """Algorithme de Karn : le timeout double, et la tentative réémise ne fournira pas de mesure."""
        self.backoff = min(self.backoff * 2, 64)

    @property
    def rto(self) -> timedelta:
        if self.srtt is None or self.rttvar is None:
            base = RTO_INITIAL
        else:
            base = self.srtt + max(CLOCK_GRANULARITY, self.k * self.rttvar)
        return _clamp(base * self.backoff, RTO_MIN, RTO_MAX)


def gamma_jitter(mean: timedelta, shape: float = JITTER_GAMMA_SHAPE, rng: random.Random | None = None) -> timedelta:
    """Délai tiré d'une loi gamma de moyenne ``mean`` : shape * scale = mean.

    Attention : dans ``random.gammavariate(alpha, beta)``, alpha est la forme et beta l'échelle (pas le taux).
    Contrairement au « full jitter » uniforme, la loi gamma ne tire presque jamais un délai nul, et sa queue à droite
    étale les clients qui réessaient en même temps.
    """
    if shape <= 0:
        raise ValueError(f"forme de la loi gamma invalide : {shape}")
    seconds = mean.total_seconds()
    if seconds <= 0:
        return ZERO
    scale = seconds / shape
    draw = (rng or random).gammavariate(shape, scale)
    return timedelta(seconds=draw)


def backoff_delay(attempt: int, rng: random.Random | None = None) -> timedelta:
    """Délai avant la tentative ``attempt`` (1 pour la première reprise) : exponentiel plafonné, puis bruité."""
    if attempt < 1:
        raise ValueError(f"numéro de tentative invalide : {attempt}")
    mean = min(BACKOFF_CAP, BACKOFF_BASE * (2 ** (attempt - 1)))
    return gamma_jitter(mean, rng=rng)


@dataclass(frozen=True)
class Deadline:
    """Échéance absolue sur l'horloge monotone ; insensible aux changements d'heure."""

    expires_at: float
    clock: Callable[[], float] = field(default=time.monotonic, compare=False)

    @classmethod
    def after(cls, budget: timedelta, clock: Callable[[], float] = time.monotonic) -> Deadline:
        return cls(clock() + budget.total_seconds(), clock)

    def remaining(self) -> timedelta:
        return timedelta(seconds=max(0.0, self.expires_at - self.clock()))

    @property
    def expired(self) -> bool:
        return self.remaining() == ZERO


class RetryBudgetExhausted(TimeoutError):
    """Toutes les tentatives ont échoué ou l'échéance globale est passée ; la dernière erreur est en ``__cause__``."""


def call_with_adaptive_timeout[T](
    fn: Callable[[float], T],
    estimator: RttEstimator,
    deadline: Deadline,
    *,
    max_attempts: int = MAX_ATTEMPTS,
    retry_on: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError),
    rng: random.Random | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Appelle ``fn(timeout_s)`` jusqu'au succès, en adaptant le timeout et en respectant l'échéance globale.

    Seules les réponses obtenues à la première tentative alimentent l'estimateur (Karn) : après une reprise, on ne
    sait plus à quelle émission la réponse correspond.
    """
    if max_attempts < 1:
        raise ValueError(f"max_attempts doit valoir au moins 1 : {max_attempts}")
    last_error: BaseException | None = None
    attempt = 0
    for attempt in range(1, max_attempts + 1):
        timeout = min(estimator.rto, deadline.remaining())
        if timeout <= ZERO:
            break
        started = time.monotonic()
        try:
            result = fn(timeout.total_seconds())
        except retry_on as exc:
            last_error = exc
            if isinstance(exc, TimeoutError):
                estimator.on_timeout()
        else:
            if attempt == 1:
                estimator.observe(timedelta(seconds=time.monotonic() - started))
            return result
        if attempt == max_attempts:
            break
        pause = backoff_delay(attempt, rng=rng)
        # pas de pause qui dépasserait l'échéance : autant échouer tout de suite
        if pause >= deadline.remaining():
            break
        sleep(pause.total_seconds())
    raise RetryBudgetExhausted(f"échec après {attempt} tentative(s), RTO courant {estimator.rto}") from last_error


# --- ancienne version (garder au cas où) ---
# def call_with_retry(fn, retries=3, timeout=30):
#     for _ in range(retries):
#         try:
#             return fn(timeout)
#         except Exception:
#             time.sleep(1)
