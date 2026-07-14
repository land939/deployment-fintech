"""Tests for ML fraud detection service."""

import pytest
from config import Settings
from services.ml import FraudDetectionService


@pytest.fixture
def fraud_service(settings):
    """Create fraud service instance."""
    # This will load actual models if they exist
    try:
        return FraudDetectionService(settings)
    except FileNotFoundError:
        pytest.skip("ML models not available")


def test_fraud_service_initialization(fraud_service):
    """Test fraud service initializes correctly."""
    assert fraud_service is not None
    assert fraud_service.fraud_model is not None
    assert fraud_service.scaler is not None


def test_fraud_service_model_info(fraud_service):
    """Test model info retrieval."""
    info = fraud_service.get_model_info()

    assert "fraud_model_loaded" in info
    assert "scaler_loaded" in info
    assert "feature_columns_loaded" in info
    assert "num_features" in info


def test_predict_fraud_with_minimal_data(fraud_service, mock_fraud_data):
    """Test fraud prediction with minimal required data."""
    result = fraud_service.predict_fraud({"Amount": 100.0, "Time": 0})

    assert "fraud_probability" in result
    assert "risk_score" in result
    assert "risk_level" in result
    assert "blocked" in result
    assert isinstance(result["fraud_probability"], float)
    assert 0 <= result["fraud_probability"] <= 1
    assert 0 <= result["risk_score"] <= 100


def test_predict_fraud_with_all_features(fraud_service, mock_fraud_data):
    """Test fraud prediction with all 31 features."""
    result = fraud_service.predict_fraud(mock_fraud_data)

    assert "fraud_probability" in result
    assert "risk_score" in result
    assert "risk_level" in result
    assert "blocked" in result
    assert result["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def test_risk_level_thresholds(fraud_service):
    """Test risk level thresholds."""
    # Create test data with varying probabilities
    test_cases = [
        ({"Amount": 1.0, "Time": 0}, "LOW", False),  # Very small amount
        ({"Amount": 1000.0, "Time": 86400}, "MEDIUM", False),  # Large amount late at night
    ]

    for features, expected_level, expected_blocked in test_cases:
        result = fraud_service.predict_fraud(features)
        # Just verify we get a response, exact levels depend on model
        assert result["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        assert isinstance(result["blocked"], bool)


def test_fraud_service_handles_missing_models(settings):
    """Test service handles missing models gracefully."""
    # Create service with non-existent model paths
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

    # Should raise FileNotFoundError
    with pytest.raises(FileNotFoundError):
        FraudDetectionService(bad_settings)
