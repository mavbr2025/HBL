import asyncio

import httpx
import pytest

from mtm_hbl.config import Settings
from mtm_hbl.gamma_connector import GammaClient


def test_gamma_client_lists_themes(monkeypatch):
    captured = {}

    async def mock_request(self, method, url, *, headers=None, json=None):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        return httpx.Response(
            200,
            json={"themes": [{"id": "theme_1", "name": "MTM"}]},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

    client = GammaClient(
        Settings(gamma_api_key="test-key", gamma_api_base_url="https://gamma.example/v1.0")
    )
    themes = asyncio.run(client.list_themes())

    assert themes == [{"id": "theme_1", "name": "MTM"}]
    assert captured["method"] == "GET"
    assert captured["url"] == "https://gamma.example/v1.0/themes"
    assert captured["headers"]["X-API-KEY"] == "test-key"


def test_gamma_client_requires_api_key():
    client = GammaClient(Settings(gamma_api_key=""))

    with pytest.raises(ValueError, match="GAMMA_API_KEY"):
        asyncio.run(client.list_themes())


def test_gamma_client_surfaces_api_errors(monkeypatch):
    async def mock_request(self, method, url, *, headers=None, json=None):
        return httpx.Response(401, json={"message": "invalid api key"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", mock_request)

    client = GammaClient(Settings(gamma_api_key="bad-key"))

    with pytest.raises(ValueError, match="401 invalid api key"):
        asyncio.run(client.list_themes())
