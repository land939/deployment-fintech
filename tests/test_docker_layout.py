"""Unit tests for Docker layout consistency."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_only_docker_folder_has_dockerfile():
    root_dockerfile = ROOT / "Dockerfile"
    docker_dockerfile = ROOT / "docker" / "Dockerfile"
    assert not root_dockerfile.exists(), "legacy root Dockerfile must be removed"
    assert docker_dockerfile.exists(), "canonical Dockerfile lives under docker/"


def test_only_docker_folder_has_compose():
    root_compose = ROOT / "docker-compose.yml"
    docker_compose = ROOT / "docker" / "docker-compose.yml"
    assert not root_compose.exists(), "legacy root compose must be removed"
    assert docker_compose.exists()


def test_compose_builds_from_docker_dockerfile():
    text = (ROOT / "docker" / "docker-compose.yml").read_text()
    assert "dockerfile: docker/Dockerfile" in text
    assert "context: .." in text


def test_root_dockerignore_exists_for_build_context():
    """Compose context is repo root, so .dockerignore must live there."""
    assert (ROOT / ".dockerignore").exists()


def test_compose_mounts_project_models_and_logs():
    text = (ROOT / "docker" / "docker-compose.yml").read_text()
    assert "../models:/app/models" in text
    assert "../logs:/app/logs" in text
