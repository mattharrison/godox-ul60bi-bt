"""Public Python API for Godox UL60Bi Bluetooth control.

Typical usage
-------------
Control a light that has already been provisioned and rebound::

    import asyncio
    from godox_ul60bi_bt import GodoxController

    async def main():
        async with GodoxController("304BCD50-...", "mesh_state.json") as light:
            await light.power_on()
            await light.set_params(brightness=80, cct=4000)

    asyncio.run(main())

For first-time setup use the CLI::

    godox-ul60bi provision   # provision factory-reset device
    godox-ul60bi rebind      # push app key
    godox-ul60bi set --brightness 80 --cct 4000

Examples
--------
>>> sorted(__all__)
['GodoxController', 'MeshState', 'ProxyClient', 'UL60BiClient']
"""

from __future__ import annotations

import logging

from godox_ul60bi_bt.client import ProxyClient, UL60BiClient
from godox_ul60bi_bt.controller import GodoxController
from godox_ul60bi_bt.state import MeshState

logger = logging.getLogger(__name__)

__all__ = [
    "ProxyClient",
    "UL60BiClient",
    "GodoxController",
    "MeshState",
]
