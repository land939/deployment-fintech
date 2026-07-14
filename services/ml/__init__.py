"""Machine Learning fraud detection service."""

import json
import logging
from pathlib import Path
from typing import Optional
import joblib
import numpy as np
import pandas as pd
from config.settings import Settings

logger = logging.getLogger(__name__)


class FraudDetectionService:
    """ML-based fraud detection using 31 features."""

    def __init__(self, settings: Settings):
        """Initialize ML service with models and scaler."""
        self.settings = settings
        self.fraud_model = None
        self.scaler = None
        self.feature_columns = None
        self.all_features_loaded = False
        self._load_models()

    def _load_models(self) -> None:
        """Load ML models, scaler, and feature columns."""
        try:
            # Load fraud detector model
            if Path(self.settings.ml_model_path).exists():
                self.fraud_model = joblib.load(self.settings.ml_model_path)
                logger.info("✅ Fraud detection model loaded")
            else:
                logger.error(f"❌ Fraud model not found: {self.settings.ml_model_path}")
                raise FileNotFoundError(f"Model not found: {self.settings.ml_model_path}")

            # Load scaler
            if Path(self.settings.ml_scaler_path).exists():
                self.scaler = joblib.load(self.settings.ml_scaler_path)
                logger.info("✅ Feature scaler loaded")
            else:
                logger.error(f"❌ Scaler not found: {self.settings.ml_scaler_path}")
                raise FileNotFoundError(f"Scaler not found: {self.settings.ml_scaler_path}")

            # Load feature columns
            if Path(self.settings.ml_features_path).exists():
                with open(self.settings.ml_features_path) as f:
                    self.feature_columns = json.load(f)
                logger.info(f"✅ Feature columns loaded: {len(self.feature_columns)} features")
                self.all_features_loaded = len(self.feature_columns) >= 30
            else:
                logger.error(f"❌ Features JSON not found: {self.settings.ml_features_path}")
                raise FileNotFoundError(f"Features JSON not found: {self.settings.ml_features_path}")

        except Exception as e:
            logger.error(f"❌ Failed to load ML models: {e}")
            raise

    def predict_fraud(
        self,
        transaction_data: dict,
    ) -> dict:
        """
        Predict fraud probability using all 31 features.

        Args:
            transaction_data: Dict with Amount, Time, and optionally V1-V28

        Returns:
            Dict with fraud_probability, risk_score, risk_level, blocked
        """
        if not self.fraud_model or not self.scaler or not self.feature_columns:
            return {
                "fraud_probability": 0.0,
                "risk_score": 0,
                "risk_level": "UNKNOWN",
                "blocked": False,
                "error": "ML models not loaded",
            }

        try:
            # Initialize feature vector with all columns
            row = {col: 0.0 for col in self.feature_columns}

            # Fill in provided features
            for col, value in transaction_data.items():
                if col in row:
                    row[col] = float(value)

            # Create DataFrame with exact feature order
            df = pd.DataFrame([row], columns=self.feature_columns)

            # Get numeric features that need scaling (typically Amount, Time, Hour)
            # Adjust based on your scaler's expectations
            numeric_cols = [col for col in ["Amount", "Time", "Hour"] if col in self.feature_columns]
            if numeric_cols:
                try:
                    df[numeric_cols] = self.scaler.transform(df[numeric_cols])
                except Exception as scale_err:
                    logger.warning(f"Scaling failed, using raw values: {scale_err}")

            # Predict fraud probability
            proba = self.fraud_model.predict_proba(df)[0]
            fraud_prob = float(proba[1])
            risk_score = int(fraud_prob * 100)

            # Determine risk level and blocking
            if fraud_prob < 0.30:
                risk_level, blocked = "LOW", False
            elif fraud_prob < 0.60:
                risk_level, blocked = "MEDIUM", False
            elif fraud_prob < 0.85:
                risk_level, blocked = "HIGH", True
            else:
                risk_level, blocked = "CRITICAL", True

            logger.info(
                f"🔍 Fraud prediction: amount={transaction_data.get('Amount', 0)}, "
                f"prob={fraud_prob:.4f}, risk={risk_level}, blocked={blocked}"
            )

            return {
                "fraud_probability": round(fraud_prob, 4),
                "risk_score": risk_score,
                "risk_level": risk_level,
                "blocked": blocked,
                "features_used": len(self.feature_columns),
            }

        except Exception as e:
            logger.error(f"❌ Fraud prediction error: {e}")
            return {
                "fraud_probability": 0.5,
                "risk_score": 50,
                "risk_level": "HIGH",
                "blocked": True,
                "error": str(e),
            }

    def get_feature_importance(self) -> Optional[dict]:
        """Get feature importance from the model."""
        try:
            if hasattr(self.fraud_model, "feature_importances_"):
                importances = self.fraud_model.feature_importances_
                if len(importances) == len(self.feature_columns):
                    return {
                        col: float(imp)
                        for col, imp in zip(self.feature_columns, importances)
                    }
        except Exception as e:
            logger.warning(f"Could not extract feature importance: {e}")
        return None

    def get_model_info(self) -> dict:
        """Get information about loaded models."""
        return {
            "fraud_model_loaded": self.fraud_model is not None,
            "scaler_loaded": self.scaler is not None,
            "feature_columns_loaded": self.feature_columns is not None,
            "num_features": len(self.feature_columns) if self.feature_columns else 0,
            "all_features_available": self.all_features_loaded,
            "model_type": type(self.fraud_model).__name__ if self.fraud_model else "None",
        }
