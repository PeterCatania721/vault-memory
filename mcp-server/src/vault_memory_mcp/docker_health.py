"""Probe Neo4j availability without forcing compose recreate."""

from __future__ import annotations

import subprocess
from pathlib import Path


def neo4j_healthy(uri: str = "bolt://127.0.0.1:7687", user: str = "neo4j", password: str = "vaultmemory") -> bool:
    try:
        from neo4j import GraphDatabase

        driver = GraphDatabase.driver(uri, auth=(user, password))
        try:
            with driver.session() as session:
                session.run("RETURN 1 AS ok").single()
            return True
        finally:
            driver.close()
    except Exception:
        return False


def services_healthy(
    neo4j_uri: str = "bolt://127.0.0.1:7687",
    neo4j_user: str = "neo4j",
    neo4j_password: str = "vaultmemory",
    **_kwargs: object,
) -> bool:
    """Neo4j-only health check (Qdrant removed)."""
    return neo4j_healthy(neo4j_uri, neo4j_user, neo4j_password)


def qdrant_healthy(url: str = "http://127.0.0.1:6333") -> bool:
    """Deprecated — always False; Qdrant is no longer required."""
    return False


def ensure_docker_services(project_root: Path | None = None) -> bool:
    """Return True when Neo4j is reachable."""
    if services_healthy():
        return True

    root = project_root or Path(__file__).resolve().parents[3]
    script = root / "scripts" / "docker-up.sh"
    if not script.exists():
        return False

    try:
        subprocess.run(
            ["bash", str(script)],
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        pass

    return services_healthy()