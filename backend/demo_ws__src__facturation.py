"""Module de facturation de démonstration (fictif)."""


def total_ttc(montants_ht: list[float], taux_tva: float = 0.2) -> float:
    """Total TTC d'une liste de montants hors taxes."""
    total = sum(montants_ht)
    return round(total * (1 + taux_tva), 2)


def remise(total: float) -> float:
    """Remise de 5 % dès 500 euros de commande."""
    if total > 500:
        return round(total * 0.05, 2)
    return 0.0
