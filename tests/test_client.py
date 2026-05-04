from __future__ import annotations

from typing import Any

import pytest

from godox_ul60bi_bt.client import ProxyClient
from godox_ul60bi_bt.client import UL60BiClient


@pytest.mark.asyncio
async def test_client_connects_and_disconnects(
    fake_client_factory: tuple[Any, list[Any]],
    no_device_resolver: Any,
) -> None:
    factory, clients = fake_client_factory
    client = UL60BiClient(
        "device-id",
        client_factory=factory,
        device_resolver=no_device_resolver,
    )

    await client.connect()
    assert client.is_connected is True
    assert clients[0].is_connected is True

    await client.disconnect()
    assert client.is_connected is False
    assert clients[0].is_connected is False


@pytest.mark.asyncio
async def test_client_resolves_live_ble_device_before_connecting(
    fake_client_factory: tuple[Any, list[Any]],
) -> None:
    factory, clients = fake_client_factory
    live_device = object()
    resolved_addresses: list[str] = []

    async def resolver(address: str) -> object:
        resolved_addresses.append(address)
        return live_device

    client = UL60BiClient(
        "device-id",
        client_factory=factory,
        device_resolver=resolver,
    )

    await client.connect()

    assert resolved_addresses == ["device-id"]
    assert clients[0].address is live_device


@pytest.mark.asyncio
async def test_client_falls_back_to_address_when_resolver_finds_nothing(
    fake_client_factory: tuple[Any, list[Any]],
) -> None:
    factory, clients = fake_client_factory

    async def resolver(address: str) -> object | None:
        return None

    client = UL60BiClient(
        "device-id",
        client_factory=factory,
        device_resolver=resolver,
    )

    await client.connect()

    assert clients[0].address == "device-id"


@pytest.mark.asyncio
async def test_client_supports_async_context_manager(
    fake_client_factory: tuple[Any, list[Any]],
    no_device_resolver: Any,
) -> None:
    factory, clients = fake_client_factory

    async with UL60BiClient(
        "device-id",
        client_factory=factory,
        device_resolver=no_device_resolver,
    ) as client:
        assert client.is_connected is True

    assert clients[0].is_connected is False


@pytest.mark.asyncio
async def test_write_raw_sends_payload_to_characteristic(
    fake_client_factory: tuple[Any, list[Any]],
    no_device_resolver: Any,
) -> None:
    factory, clients = fake_client_factory
    client = UL60BiClient(
        "device-id",
        client_factory=factory,
        device_resolver=no_device_resolver,
    )
    await client.connect()

    await client.write_raw("char-id", bytes.fromhex("010203"), response=False)

    assert clients[0].writes == [("char-id", b"\x01\x02\x03", False)]


@pytest.mark.asyncio
async def test_write_raw_requires_connection(
    fake_client_factory: tuple[Any, list[Any]],
) -> None:
    factory, _ = fake_client_factory
    client = UL60BiClient("device-id", client_factory=factory)

    with pytest.raises(RuntimeError, match="client is not connected"):
        await client.write_raw("char-id", b"\x01", response=False)


@pytest.mark.asyncio
async def test_notification_subscription_plumbing(
    fake_client_factory: tuple[Any, list[Any]],
    no_device_resolver: Any,
) -> None:
    factory, clients = fake_client_factory
    client = UL60BiClient(
        "device-id",
        client_factory=factory,
        device_resolver=no_device_resolver,
    )
    await client.connect()

    received: list[bytes] = []

    def callback(data: bytes) -> None:
        received.append(data)

    await client.start_notify("notify-char", callback)
    stored_callback = clients[0].started_notifications[0][1]
    stored_callback("mock-char", bytearray(b"\x0a"))
    await client.stop_notify("notify-char")

    assert received == [b"\x0a"]
    assert clients[0].stopped_notifications == ["notify-char"]


@pytest.mark.asyncio
async def test_proxy_client_stop_notify_uses_proxy_characteristic(
    fake_client_factory: tuple[Any, list[Any]],
) -> None:
    factory, clients = fake_client_factory
    client = ProxyClient(
        "device-id",
        client_factory=factory,
    )
    await client.connect()

    await client.start_notify(lambda _data: None)
    await client.stop_notify()

    assert clients[0].started_notifications[0][0] == "00002ade-0000-1000-8000-00805f9b34fb"
    assert clients[0].stopped_notifications == ["00002ade-0000-1000-8000-00805f9b34fb"]


@pytest.mark.asyncio
async def test_start_notify_requires_connection(
    fake_client_factory: tuple[Any, list[Any]],
) -> None:
    factory, _ = fake_client_factory
    client = UL60BiClient("device-id", client_factory=factory)

    with pytest.raises(RuntimeError, match="client is not connected"):
        await client.start_notify("notify-char", lambda _data: None)
