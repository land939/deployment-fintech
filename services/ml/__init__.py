"""Service de détection de fraude par ML (11 features FTK)."""

import json
import logging
from pathlib import Path

import joblib
import pandas as pd

from config.settings import Settings

logger = logging.getLogger(__name__)

_fraud_service: "FraudDetectionService | None" = None


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

            return {
                "fraud_probability": round(fraud_prob, 4),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "blocked": blocked,
                "features_used": len(self.feature_columns),
            }
        except Exception as e:
            logger.error("Erreur prédiction fraude: %s", e)
            return {
                "fraud_probability": 0.5,
                "risk_score": 50,
                "risk_level": "HIGH",
                "blocked": True,
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
