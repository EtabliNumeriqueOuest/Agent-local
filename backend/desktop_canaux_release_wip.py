# ======================================================================
# Fichier : desktop_canaux_release_wip.py
# Description : Canaux de publication du client desktop (WIP)
# Version : 0.1.3 (alpha)
# Auteur : équipe dev
# TODO: brancher sur le job de build, pour l'instant lancé à la main
# NOTE: le client desktop est en pause, fichier gardé pour plus tard
# ======================================================================
"""Canaux de publication du client desktop et manifestes de mise à jour delta.

- Versions SemVer 2.0 : pré-versions alpha < beta < rc < version finale (règle de précédence §11).
- Canaux : stable (versions finales), beta (beta et rc), alpha (toutes les pré-versions).
- Mises à jour différentielles : le manifeste delta liste les fichiers ajoutés, modifiés et supprimés
  entre deux builds ; au-delà d'un certain volume, on bascule sur le paquet complet.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

# identifiants de pré-version et de build : alphanumériques ASCII, tiret et point autorisés
SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$")

# tags admis par canal ; rc part sur le canal beta, pas besoin d'un canal à part
TAGS_PAR_CANAL = {
    "stable": frozenset(),
    "beta": frozenset({"beta", "rc"}),
    "alpha": frozenset({"alpha", "beta", "rc", "nightly"}),
}
# au-delà de 60 % de la taille complète, le delta ne vaut plus le coup (patch + vérification)
SEUIL_DELTA = 0.6


# frozen : une version est en lecture seule et hashable (clé de dict, set)
@dataclass(frozen=True)
class Version:
    major: int
    minor: int
    patch: int
    pre: tuple[str, ...] = ()
    build: str = ""

    @classmethod
    def parse(cls, texte: str) -> Version:
        m = SEMVER.match(texte.strip().removeprefix("v"))
        if not m:
            raise ValueError(f"version invalide : {texte!r}")
        major, minor, patch, pre, build = m.groups()
        return cls(int(major), int(minor), int(patch), tuple(pre.split(".")) if pre else (), build or "")

    def cle_tri(self) -> tuple:
        """Clé de précédence SemVer : le build (+...) est ignoré, une pré-version passe avant la finale.

        Identifiants comparés un à un : numérique < alphanumérique, numériques entre eux par valeur,
        alphanumériques par ordre ASCII. alpha < beta < rc tient donc à l'ordre alphabétique des tags ;
        un tag « preview » se classerait entre beta et rc.
        """
        pre = tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in self.pre)
        return (self.major, self.minor, self.patch, 0 if self.pre else 1, pre)

    @property
    def tag(self) -> str:
        """Premier identifiant de pré-version (alpha, beta, rc…) ; vide pour une version finale."""
        return self.pre[0] if self.pre else ""

    def __str__(self) -> str:
        texte = f"{self.major}.{self.minor}.{self.patch}"
        if self.pre:
            texte += "-" + ".".join(self.pre)
        return texte + (f"+{self.build}" if self.build else "")


def admise(version: Version, canal: str) -> bool:
    """Une version finale est admise partout ; une pré-version seulement si son tag est dans le canal."""
    if canal not in TAGS_PAR_CANAL:
        raise ValueError(f"canal inconnu : {canal!r}")
    return not version.pre or version.tag in TAGS_PAR_CANAL[canal]


def choisir_version(disponibles: list[str], canal: str, installee: str | None = None) -> Version | None:
    """Version à proposer : la plus haute admise par le canal, jamais en dessous de l'installée.

    Un poste qui repasse de beta à stable garde sa 2.1.0-beta.3 jusqu'à ce que la 2.1.0 finale sorte :
    pas de retour arrière automatique.
    """
    candidats = [v for v in map(Version.parse, disponibles) if admise(v, canal)]
    if not candidats:
        return None
    meilleure = max(candidats, key=Version.cle_tri)
    if installee is not None:
        actuelle = Version.parse(installee)
        if actuelle.cle_tri() >= meilleure.cle_tri():
            return None
    return meilleure


def manifeste_fichiers(fichiers: dict[str, bytes]) -> dict[str, dict]:
    """Empreinte sha256 et taille de chaque fichier du build, chemins en ordre alphabétique."""
    return {chemin: {"sha256": hashlib.sha256(data).hexdigest(), "taille": len(data)} for chemin, data in sorted(fichiers.items())}


def manifeste_delta(ancien: dict[str, dict], nouveau: dict[str, dict], depuis: str, vers: str) -> dict:
    """Manifeste de mise à jour delta entre deux manifestes de fichiers.

    Le delta ne contient que les fichiers ajoutés ou modifiés ; les supprimés sont listés pour le client.
    Si le delta dépasse SEUIL_DELTA de la taille complète, mode « complet » : le client télécharge tout.
    """
    ajoutes = sorted(set(nouveau) - set(ancien))
    supprimes = sorted(set(ancien) - set(nouveau))
    modifies = sorted(c for c in set(nouveau) & set(ancien) if nouveau[c]["sha256"] != ancien[c]["sha256"])
    taille_complete = sum(f["taille"] for f in nouveau.values())
    taille_delta = sum(nouveau[c]["taille"] for c in ajoutes + modifies)
    mode = "delta" if taille_complete and taille_delta <= SEUIL_DELTA * taille_complete else "complet"
    return {
        "depuis": depuis,
        "vers": vers,
        "mode": mode,
        "ajoutes": ajoutes,
        "modifies": modifies,
        "supprimes": supprimes,
        "taille_delta": taille_delta,
        "taille_complete": taille_complete,
    }


def empreinte_manifeste(manifeste: dict) -> str:
    """sha256 du manifeste sérialisé avec clés triées : deux builds identiques donnent la même empreinte."""
    brut = json.dumps(manifeste, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(brut.encode("utf-8")).hexdigest()


def chaine_deltas(versions: list[str], canal: str) -> list[tuple[str, str]]:
    """Paires (depuis, vers) à publier : un delta entre chaque version consécutive du canal, triées par précédence."""
    admises = sorted((v for v in map(Version.parse, versions) if admise(v, canal)), key=Version.cle_tri)
    return [(str(a), str(b)) for a, b in zip(admises, admises[1:], strict=False)]


if __name__ == "__main__":
    # test rapide (à la main)
    publiees = ["2.0.0", "2.1.0-alpha.1", "2.1.0-alpha.2", "2.1.0-beta.1", "2.1.0-beta.11", "2.1.0-beta.2", "2.1.0-rc.1"]
    for canal in ("stable", "beta", "alpha"):
        print(canal, "→", choisir_version(publiees, canal))
    # beta.11 après beta.2 : comparaison numérique des identifiants, pas alphabétique
    print(sorted(publiees, key=lambda t: Version.parse(t).cle_tri()))
    a = manifeste_fichiers({"app.bin": b"x" * 1000, "lib/core.so": b"a" * 400, "res/fr.json": b"{}"})
    b = manifeste_fichiers({"app.bin": b"x" * 1000, "lib/core.so": b"b" * 420, "res/en.json": b"{}"})
    delta = manifeste_delta(a, b, "2.1.0-rc.1", "2.1.0")
    print(json.dumps(delta, indent=2, ensure_ascii=False))
    print(empreinte_manifeste(delta)[:12], chaine_deltas(publiees, "beta"))
