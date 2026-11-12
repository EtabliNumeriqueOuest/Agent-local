# ======================================================================
# Fichier : svc_meteo_geocodage_WIP.py
# Description : Géocodage hors ligne pour la météo (jamais livré)
# Version : 0.1.2 (alpha)
# Auteur : équipe dev
# NOTE: rien n'importe ce module, la météo a été abandonnée avant la v1
# Ce fichier a été généré automatiquement puis modifié
# ======================================================================
"""Petit géocodeur hors ligne : quelques villes françaises, leurs coordonnées, leur région et leur fuseau.

Prévu pour résoudre une ville sans appel réseau avant d'interroger un service de prévisions. Le référentiel est figé
(lecture seule) et volontairement réduit : les préfectures bretonnes et Brest, quelques grandes villes, trois villes
d'outre-mer.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType

RAYON_TERRE_KM = 6371.0
# heure de Paris en hiver ; l'heure d'été ajoute DECALAGE_ETE
UTC_PLUS_1 = timedelta(hours=1)
# heure d'été européenne : du dernier dimanche de mars au dernier dimanche d'octobre, bascule à 01:00 UTC
DECALAGE_ETE = timedelta(hours=1)


class VilleInconnue(LookupError):
    pass


class VilleAmbigue(LookupError):
    def __init__(self, requete: str, candidates: Iterable[Ville]):
        self.candidates = tuple(candidates)
        noms = ", ".join(f"{v.nom} ({v.departement})" for v in self.candidates)
        super().__init__(f"« {requete} » désigne plusieurs villes : {noms}")


def normaliser(texte: str) -> str:
    """Clé de recherche : sans accents, en minuscules, chaque suite de caractères non alphanumériques remplacée par un tiret."""
    # œ et æ n'ont pas de décomposition NFKD : sans ce remplacement, ils disparaîtraient à l'encodage ASCII
    texte = texte.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("Æ", "AE")
    ascii_ = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    cle = re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")
    return re.sub(r"^st-", "saint-", cle)


@dataclass(frozen=True, slots=True)
class Ville:
    """Une ville du référentiel ; frozen, comme le reste des données de ce module."""

    nom: str
    # code alphanumérique, pas un entier : 2A et 2B pour la Corse, 971 à 976 outre-mer
    departement: str
    region: str
    latitude: float
    longitude: float
    utc_hiver: timedelta
    heure_ete: bool = True

    @property
    def cle(self) -> str:
        return f"{normaliser(self.nom)}-{self.departement.lower()}"


_VILLES = (
    Ville("Rennes", "35", "Bretagne", 48.1173, -1.6778, UTC_PLUS_1),
    Ville("Brest", "29", "Bretagne", 48.3904, -4.4861, UTC_PLUS_1),
    Ville("Quimper", "29", "Bretagne", 47.9960, -4.1024, UTC_PLUS_1),
    Ville("Saint-Brieuc", "22", "Bretagne", 48.5136, -2.7653, UTC_PLUS_1),
    Ville("Vannes", "56", "Bretagne", 47.6582, -2.7608, UTC_PLUS_1),
    # Nantes est en Pays de la Loire, pas en Bretagne, même si les deux se confondent souvent
    Ville("Nantes", "44", "Pays de la Loire", 47.2184, -1.5536, UTC_PLUS_1),
    Ville("Paris", "75", "Île-de-France", 48.8566, 2.3522, UTC_PLUS_1),
    Ville("Saint-Denis", "93", "Île-de-France", 48.9362, 2.3574, UTC_PLUS_1),
    Ville("Lille", "59", "Hauts-de-France", 50.6292, 3.0573, UTC_PLUS_1),
    Ville("Strasbourg", "67", "Grand Est", 48.5734, 7.7521, UTC_PLUS_1),
    Ville("Lyon", "69", "Auvergne-Rhône-Alpes", 45.7640, 4.8357, UTC_PLUS_1),
    Ville("Marseille", "13", "Provence-Alpes-Côte d'Azur", 43.2965, 5.3698, UTC_PLUS_1),
    Ville("Toulouse", "31", "Occitanie", 43.6047, 1.4442, UTC_PLUS_1),
    Ville("Bordeaux", "33", "Nouvelle-Aquitaine", 44.8378, -0.5792, UTC_PLUS_1),
    Ville("Ajaccio", "2A", "Corse", 41.9192, 8.7386, UTC_PLUS_1),
    # outre-mer : décalage fixe toute l'année, pas d'heure d'été
    Ville("Pointe-à-Pitre", "971", "Guadeloupe", 16.2411, -61.5331, timedelta(hours=-4), heure_ete=False),
    Ville("Cayenne", "973", "Guyane", 4.9224, -52.3135, timedelta(hours=-3), heure_ete=False),
    Ville("Saint-Denis", "974", "La Réunion", -20.8823, 55.4504, timedelta(hours=4), heure_ete=False),
)


def _tri_alphabetique(villes: Iterable[Ville]) -> tuple[Ville, ...]:
    # tri alphabétique sur la clé normalisée : trié brut, « Île-de-France » passerait après « z »
    return tuple(sorted(villes, key=lambda v: (normaliser(v.nom), v.departement)))


def _index_par_nom() -> Mapping[str, tuple[Ville, ...]]:
    groupes: dict[str, list[Ville]] = {}
    for ville in _VILLES:
        groupes.setdefault(normaliser(ville.nom), []).append(ville)
    return MappingProxyType({nom: _tri_alphabetique(v) for nom, v in sorted(groupes.items())})


# vues en lecture seule : un appelant ne peut pas enrichir le référentiel par mégarde
VILLES: Mapping[str, Ville] = MappingProxyType({v.cle: v for v in _tri_alphabetique(_VILLES)})
PAR_NOM = _index_par_nom()
REGIONS: tuple[str, ...] = tuple(sorted({v.region for v in _VILLES}, key=normaliser))

# « Saint-Denis (974) », « saint denis 93 », « Rennes » ; le code est alphanumérique (2A, 971)
_REQUETE = re.compile(r"^\s*(?P<nom>.+?)\s*(?:\(\s*(?P<dep1>\w{2,3})\s*\)|\s(?P<dep2>\d[0-9ABab]\d?))?\s*$")


def resoudre(requete: str) -> Ville:
    """Résout une saisie libre en une ville du référentiel, ou lève une erreur explicite."""
    m = _REQUETE.match(requete)
    if not m:
        raise VilleInconnue(f"requête vide : {requete!r}")
    nom = normaliser(m["nom"])
    departement = (m["dep1"] or m["dep2"] or "").upper()
    candidates = PAR_NOM.get(nom, ())
    if departement:
        candidates = tuple(v for v in candidates if v.departement == departement)
    if not candidates:
        raise VilleInconnue(f"ville absente du référentiel : {requete!r}")
    if len(candidates) > 1:
        raise VilleAmbigue(requete, candidates)
    return candidates[0]


def suggestions(prefixe: str, limite: int = 5) -> tuple[Ville, ...]:
    """Villes dont le nom normalisé commence par ``prefixe``, dans l'ordre alphabétique."""
    debut = normaliser(prefixe)
    if not debut:
        return ()
    return _tri_alphabetique(v for v in VILLES.values() if normaliser(v.nom).startswith(debut))[:limite]


def villes_de_la_region(region: str) -> tuple[Ville, ...]:
    """Villes d'une région (« bretagne » et « Bretagne » donnent le même résultat)."""
    cible = normaliser(region)
    return _tri_alphabetique(v for v in _VILLES if normaliser(v.region) == cible)


def distance_km(a: Ville, b: Ville) -> float:
    """Distance orthodromique (formule de haversine, Terre sphérique) : à 0,5 % près, assez pour la météo."""
    lat_a, lat_b = math.radians(a.latitude), math.radians(b.latitude)
    delta_lat = lat_b - lat_a
    delta_lon = math.radians(b.longitude - a.longitude)
    h = math.sin(delta_lat / 2) ** 2 + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    return 2 * RAYON_TERRE_KM * math.asin(math.sqrt(h))


def ville_la_plus_proche(latitude: float, longitude: float) -> Ville:
    point = Ville("point", "", "", latitude, longitude, timedelta(0))
    return min(_VILLES, key=lambda v: distance_km(point, v))


def _dernier_dimanche(annee: int, mois: int) -> datetime:
    """Dernier dimanche du mois à 01:00 UTC, instant de bascule de l'heure d'été en Europe."""
    premier_du_suivant = datetime(annee + mois // 12, mois % 12 + 1, 1, 1, tzinfo=UTC)
    dernier_jour = premier_du_suivant - timedelta(days=1)
    # weekday() : lundi = 0, dimanche = 6
    return dernier_jour - timedelta(days=(dernier_jour.weekday() + 1) % 7)


def decalage_utc(ville: Ville, instant: datetime) -> timedelta:
    """Décalage de la ville par rapport à UTC à un instant donné (heure d'été comprise)."""
    if instant.tzinfo is None:
        raise ValueError("instant sans fuseau : passer une date avec tzinfo (UTC de préférence)")
    if not ville.heure_ete:
        return ville.utc_hiver
    instant = instant.astimezone(UTC)
    debut = _dernier_dimanche(instant.year, 3)
    fin = _dernier_dimanche(instant.year, 10)
    return ville.utc_hiver + (DECALAGE_ETE if debut <= instant < fin else timedelta(0))


def heure_locale(ville: Ville, instant: datetime) -> datetime:
    """Heure murale de la ville, sans tzinfo : à afficher, pas à recomparer avec d'autres instants."""
    return (instant.astimezone(UTC) + decalage_utc(ville, instant)).replace(tzinfo=None)
