"""Taux de conversion FTK <-> ETH.

Aujourd'hui : taux fixe lu dans la configuration (FTK_ETH_RATE, défaut
1 FTK = 0.0001 ETH). L'abstraction est volontairement une fonction unique :
pour passer à un taux dynamique (oracle Chainlink, API CoinGecko…), il
suffira de remplacer le corps de get_ftk_eth_rate() — aucun appelant ne
change.
"""

import logging

from config.settings import Settings

logger = logging.getLogger(__name__)


def get_ftk_eth_rate(settings: Settings) -> float:
    """Retourne combien d'ETH vaut 1 FTK.

    Point d'extension futur : interroger ici un oracle on-chain ou une API
    de prix, avec le taux de la config en valeur de repli.
    """
    return settings.ftk_eth_rate


def ftk_to_eth(amount_ftk: float, settings: Settings) -> float:
    """Convertit un montant FTK en ETH (arrondi 8 décimales)."""
    return round(amount_ftk * get_ftk_eth_rate(settings), 8)
