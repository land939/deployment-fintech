"""Service de détection de fraude par ML (11 features FTK)."""

import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from config.settings import Settings

logger = logging.getLogger(__name__)

_fraud_service: "FraudDetectionService | None" = None


def explain_fraud(features: dict) -> list[str]:
    """Facteurs de risque lisibles, dérivés des 11 features FTK.

    Le modèle XGBoost ne fournit pas d'explication native ; ces règles
    reprennent les scénarios de fraude du dataset d'entraînement (rafale,
    montant aberrant, compte neuf, vidage nocturne, récidive) pour dire à
    l'admin POURQUOI la transaction est suspecte avant de l'autoriser.
    """
    f = {k: float(features.get(k, 0.0)) for k in features}
    reasons: list[str] = []

    ratio = f.get("amount_avg_ratio", 1.0)
    if ratio >= 10:
        reasons.append(
            f"Montant aberrant : {ratio:.0f}× la moyenne habituelle de l'expéditeur"
        )
    elif ratio >= 3:
        reasons.append(f"Montant inhabituel : {ratio:.1f}× la moyenne de l'expéditeur")

    tx_1h = f.get("tx_count_1h", 0)
    if tx_1h >= 4:
        reasons.append(f"Rafale d'envois : {tx_1h:.0f} transactions dans la dernière heure")
    elif f.get("tx_count_24h", 0) >= 12:
        reasons.append(f"Activité intense : {f['tx_count_24h']:.0f} transactions en 24 h")

    age = f.get("account_age_days", 999)
    if age < 2 and (tx_1h >= 2 or f.get("amount", 0) > 500 or ratio >= 3):
        if age < 1 / 24:
            reasons.append("Compte créé il y a moins d'une heure")
        else:
            reasons.append(f"Compte très récent ({age:.1f} jour(s)) et déjà très actif")

    hour = f.get("hour", 12)
    if 1 <= hour <= 5:
        reasons.append(f"Envoi nocturne ({int(hour)} h) — plage typique des vidages de compte")

    if f.get("past_fraud_count", 0) >= 1:
        reasons.append(
            f"Récidive : {f['past_fraud_count']:.0f} transaction(s) déjà bloquée(s) "
            "pour cet expéditeur"
        )

    recv_24h = f.get("unique_receivers_24h", 0)
    if recv_24h >= 5:
        reasons.append(f"Dispersion : {recv_24h:.0f} destinataires distincts en 24 h")

    if f.get("is_new_receiver", 0) >= 1 and (ratio >= 3 or 1 <= hour <= 5 or tx_1h >= 3):
        reasons.append("Destinataire jamais utilisé par cet expéditeur")

    since = f.get("seconds_since_last_tx", 1e9)
    if since <= 120 and tx_1h >= 2:
        reasons.append(f"Envoi {since:.0f} s seulement après le précédent")

    return reasons


def set_fraud_service(service: "FraudDetectionService | None") -> None:
    """Enregistre le singleton chargé au lifespan."""
    global _fraud_service
    _fraud_service = service


def get_fraud_service() -> "FraudDetectionService | None":
    """Retourne le singleton (None si modèles absents)."""
    return _fraud_service


class FraudDetectionService:
    """Détection de fraude XGBoost sur features calculables en production."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.fraud_model = None
        self.scaler = None
        self.feature_columns = None
        self._load_models()

    def _load_models(self) -> None:
        if not Path(self.settings.ml_model_path).exists():
            raise FileNotFoundError(f"Modèle introuvable: {self.settings.ml_model_path}")
        if not Path(self.settings.ml_scaler_path).exists():
            raise FileNotFoundError(f"Scaler introuvable: {self.settings.ml_scaler_path}")
        if not Path(self.settings.ml_features_path).exists():
            raise FileNotFoundError(f"Features JSON introuvable: {self.settings.ml_features_path}")

        self.fraud_model = joblib.load(self.settings.ml_model_path)
        self.scaler = joblib.load(self.settings.ml_scaler_path)
        with open(self.settings.ml_features_path) as f:
            self.feature_columns = json.load(f)
        logger.info("ML chargé: modèle + scaler + %s features", len(self.feature_columns))

    def predict_fraud(self, transaction_data: dict) -> dict:
        """Prédit la probabilité de fraude (11 features FTK)."""
        if not self.fraud_model or not self.scaler or not self.feature_columns:
            return {
                "fraud_probability": 0.0,
                "risk_score": 0,
                "risk_level": "UNKNOWN",
                "blocked": False,
                "error": "Modèles ML non chargés",
            }

        try:
            row = {col: float(transaction_data.get(col, 0.0)) for col in self.feature_columns}
            df = pd.DataFrame([row], columns=self.feature_columns)
            df[self.feature_columns] = self.scaler.transform(df[self.feature_columns])

            proba = self.fraud_model.predict_proba(df)[0]
            fraud_prob = float(proba[1])
            risk_score = int(fraud_prob * 100)

            if fraud_prob < 0.30:
                risk_level, blocked = "LOW", False
            elif fraud_prob < 0.60:
                risk_level, blocked = "MEDIUM", False
            elif fraud_prob < 0.85:
                risk_level, blocked = "HIGH", True
            else:
                risk_level, blocked = "CRITICAL", True

            reasons = explain_fraud(transaction_data)
            if blocked and not reasons:
                reasons = ["Combinaison de signaux faibles jugée anormale par le modèle"]

            return {
                "fraud_probability": round(fraud_prob, 4),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "blocked": blocked,
                "reasons": reasons,
                "features_used": len(self.feature_columns),
            }
        except Exception as e:
            logger.error("Erreur prédiction fraude: %s", e)
            return {
                "fraud_probability": 0.5,
                "risk_score": 50,
                "risk_level": "HIGH",
                "blocked": True,
                "reasons": ["Erreur du modèle — transaction bloquée par précaution"],
                "error": str(e),
            }

    def get_model_info(self) -> dict:
        return {
            "fraud_model_loaded": self.fraud_model is not None,
            "scaler_loaded": self.scaler is not None,
            "feature_columns_loaded": self.feature_columns is not None,
            "num_features": len(self.feature_columns) if self.feature_columns else 0,
            "model_type": type(self.fraud_model).__name__ if self.fraud_model else "None",
        }
