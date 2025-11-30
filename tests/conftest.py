"""Configuração de fixtures para testes."""

import pytest


@pytest.fixture
def sample_data() -> dict:
    """Dados de exemplo para testes."""
    return {"user_id": 123, "name": "Test User", "active": True}


@pytest.fixture
def sample_bytes() -> bytes:
    """Bytes de exemplo para testes."""
    return b"test data bytes"
