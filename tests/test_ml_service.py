"""Tests du service ML de détection de fraude."""

import pytest

from config import Settings
from services.ml import FraudDetectionService
from services.ml.features import FEATURE_COLS


@pytest.fixture
def fraud_service(settings):
    """Instance du service (skip si modèles absents)."""
    try:
        return FraudDetectionService(settings)
    except FileNotFoundError:
        pytest.skip("Modèles ML indisponibles")


def test_fraud_service_initialization(fraud_service):
    assert fraud_service is not None
    assert fraud_service.fraud_model is not None
    assert fraud_service.scaler is not None
    assert fraud_service.feature_columns is not None
    assert len(fraud_service.feature_columns) == len(FEATURE_COLS)


def test_fraud_service_model_info(fraud_service):
    info = fraud_service.get_model_info()
    assert info["fraud_model_loaded"] is True
    assert info["num_features"] == len(FEATURE_COLS)


def test_predict_fraud_with_minimal_data(fraud_service, mock_fraud_data):
    result = fraud_service.predict_fraud({"amount": 100.0, "hour": 12})

    assert "fraud_probability" in result
    assert "risk_score" in result
    assert "risk_level" in result
    assert "blocked" in result
    assert 0 <= result["fraud_probability"] <= 1
    assert 0 <= result["risk_score"] <= 100
    assert "error" not in result


def test_predict_fraud_with_all_features(fraud_service, mock_fraud_data):
    result = fraud_service.predict_fraud(mock_fraud_data)

    assert result["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    assert isinstance(result["blocked"], bool)
    assert result["features_used"] == len(FEATURE_COLS)


def test_risk_level_thresholds(fraud_service):
    for features in (
        {"amount": 1.0, "hour": 14, "tx_count_1h": 0},
        {"amount": 5000.0, "hour": 3, "tx_count_1h": 12, "is_new_receiver": 1},
    ):
        result = fraud_service.predict_fraud(features)
        assert result["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert isinstance(result["blocked"], bool)


def test_fraud_service_handles_missing_models(settings):
    bad_settings = Settings(
        environment="test",
        debug=True,
        database_url="sqlite:///:memory:",
        secret_key="test-key",
        superadmin_email="admin@test.local",
        superadmin_password="Password123!",
        ml_model_path="/nonexistent/fraud_detector.pkl",
        ml_scaler_path="/nonexistent/scaler.pkl",
        ml_features_path="/nonexistent/features.json",
    )
    with pytest.raises(FileNotFoundError):
        FraudDetectionService(bad_settings)
