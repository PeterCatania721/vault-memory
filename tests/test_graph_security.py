import pytest

from vault_memory_mcp.graph import GraphStore
from vault_memory_mcp.config import GraphConfig


def test_readonly_blocks_writes():
    store = GraphStore(GraphConfig())
    try:
        with pytest.raises(ValueError, match="read-only"):
            store.query_readonly("CREATE (n:Note {path: 'x'}) RETURN n")
    finally:
        store.close()