"""Tests for the IPv4-pinned PostgreSQL connection helper."""

from __future__ import annotations

import socket

import pytest

from app.db import client


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    client._ipv4_hostaddr.cache_clear()
    yield
    client._ipv4_hostaddr.cache_clear()


def test_ipv4_hostaddr_returns_first_address(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        client.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("203.0.113.5", 5432))
        ],
    )

    assert client._ipv4_hostaddr("db.example.com", 5432) == "203.0.113.5"


def test_ipv4_hostaddr_returns_none_when_dns_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(*args: object, **kwargs: object) -> list[object]:
        raise socket.gaierror("no address")

    monkeypatch.setattr(client.socket, "getaddrinfo", fail)

    assert client._ipv4_hostaddr("db.example.com", 5432) is None


def test_connection_kwargs_pins_ipv4(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(client.settings, "DATABASE_URL", "postgresql://u:p@db.example.com:5432/app")
    monkeypatch.setattr(client, "_ipv4_hostaddr", lambda host, port: "203.0.113.9")

    assert client._connection_kwargs() == {"hostaddr": "203.0.113.9"}


def test_connection_kwargs_respects_explicit_hostaddr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        client.settings,
        "DATABASE_URL",
        "postgresql://u:p@db.example.com/app?hostaddr=198.51.100.7",
    )

    assert client._connection_kwargs() == {}


def test_connection_kwargs_skips_unresolvable_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(client.settings, "DATABASE_URL", "postgresql://u:p@db.example.com/app")
    monkeypatch.setattr(client, "_ipv4_hostaddr", lambda host, port: None)

    assert client._connection_kwargs() == {}
