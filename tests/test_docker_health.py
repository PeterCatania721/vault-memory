"""Docker health probes."""

from __future__ import annotations

from vault_memory_mcp.docker_health import ensure_docker_services, neo4j_healthy, services_healthy


def test_neo4j_probe_returns_bool():
    assert isinstance(neo4j_healthy(), bool)


def test_services_healthy_returns_bool():
    assert isinstance(services_healthy(), bool)


def test_ensure_docker_services_returns_bool():
    assert isinstance(ensure_docker_services(), bool)