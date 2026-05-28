"""Network module for TCP communication with XIAO servos."""

import asyncio
import logging
from typing import Optional

import config
XIAO_CONFIG = config.XIAO_CONFIG

logger = logging.getLogger(__name__)


async def send_tcp_command(
    command: str,
    ip: Optional[str] = None,
    port: Optional[int] = None,
) -> bool:
    """Send TCP command to XIAO servo controller."""
    if command == "NONE":
        logger.info("[NET] Command is NONE, skipping")
        return True

    ip = ip or XIAO_CONFIG["ip"]
    port = port or XIAO_CONFIG["port"]

    logger.info(f"[NET] Sending '{command}' to {ip}:{port}")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(ip, port),
            timeout=3.0
        )

        payload = f"{command}\n"
        writer.write(payload.encode('utf-8'))
        await writer.drain()

        writer.close()
        await writer.wait_closed()

        logger.info(f"[NET] Command '{command}' sent successfully")
        return True
    except asyncio.TimeoutError:
        logger.error(f"[NET] Connection timeout for {ip}:{port}")
        return False
    except Exception as e:
        logger.error(f"[NET] Error: {e}")
        return False
