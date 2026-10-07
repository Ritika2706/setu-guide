"""Day 2 deliverables that can be checked without a Docker daemon.

Guards the files DevOps 1 owns: split requirements, .dockerignore, Dockerfile,
docker-compose.yml and .env.example.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


# ---------------------------------------------------------------- requirements
def test_runtime_requirements_have_no_dev_packages():
    runtime = _read("requirements.txt").lower()
    for dev_pkg in ("pytest", "httpx", "ruff", "black", "mypy"):
        assert dev_pkg not in runtime, f"{dev_pkg} must live in requirements-dev.txt"
    assert "pydantic-settings==" in runtime
    assert "cachetools==" in runtime


def test_every_new_dependency_is_pinned_to_an_exact_version():
    for line in _read("requirements.txt").splitlines() + _read("requirements-dev.txt").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("-r"):
            continue
        assert re.match(r"^[A-Za-z0-9_.\-]+==[0-9][0-9a-zA-Z_.\-]*$", line), (
            f"dependency must be pinned with ==: {line!r}"
        )


def test_dev_requirements_include_the_runtime_set():
    assert "-r requirements.txt" in _read("requirements-dev.txt")
    assert "pytest==" in _read("requirements-dev.txt")
    assert "httpx==" in _read("requirements-dev.txt")


# -------------------------------------------------------------------- docker
def test_dockerfile_is_safe():
    dockerfile = _read("docker", "Dockerfile")
    assert "FROM python:3.11-slim" in dockerfile
    assert dockerfile.count("FROM ") >= 2, "multi-stage build expected"
    assert "--no-cache-dir" in dockerfile
    assert "HEALTHCHECK" in dockerfile and "/health" in dockerfile
    assert re.search(r"^\s*USER\s+\w+", dockerfile, re.M), "container must run as non-root"
    assert "0.0.0.0" in dockerfile and "8000" in dockerfile, "uvicorn must listen on 0.0.0.0:8000"
    # secrets must never be baked in
    assert "ARG LLM_API_KEY" not in dockerfile
    assert "LLM_API_KEY=" not in dockerfile


def test_dockerignore_hides_secrets_and_caches():
    dockerignore = _read(".dockerignore")
    for entry in (".env", ".venv", ".git", "__pycache__", ".pytest_cache", "tests"):
        assert entry in dockerignore, f"{entry} must be excluded from the build context"
    # .env (the secret) is hidden, while the example file stays available to devs.
    assert re.search(r"^\s*\.env\s*$", dockerignore, re.M), ".env must be an exact entry"


def test_env_file_is_ignored_by_git_and_docker():
    assert ".env" in _read(".gitignore")
    assert ".env.example" in _read(".env.example")


def test_env_example_documents_every_setting():
    example = _read(".env.example")
    for var in ("LLM_API_KEY", "LLM_PROVIDER", "LLM_TIMEOUT_SECONDS", "USE_MOCK",
                "RATE_LIMIT_PER_USER", "RATE_LIMIT_PER_IP", "CACHE_ENABLED",
                "CACHE_TTL_SECONDS", "CACHE_MAX_ITEMS", "TRUSTED_PROXY", "LOG_LEVEL"):
        assert f"{var}=" in example, f"{var} missing from .env.example"


def test_docker_compose_reads_env_and_offers_a_model_volume():
    compose = _read("docker-compose.yml")
    assert "docker/Dockerfile" in compose
    assert ".env" in compose
    assert "/app/models" in compose or "/app/data" in compose
    assert "8000:8000" in compose


def test_dockerfile_has_a_commented_section_for_model_files():
    dockerfile = _read("docker", "Dockerfile")
    assert "/app/models" in dockerfile, "image must document the model volume mount"


def test_readme_documents_day2():
    readme = _read("README.md")
    for needle in ("docker build", "docker compose", "RATE_LIMIT", "X-Cache",
                   "PLACEHOLDER", "Redis"):
        assert needle in readme, f"README must document {needle}"
