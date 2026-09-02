"""
Lightweight Async HTTP Health Check Server.
Required by Render Web Services to satisfy port-scanning and health-check requirements.
Runs concurrently alongside the Telegram bot in the same asyncio event loop with zero overhead.
"""

import asyncio
import logging
import config

logger = logging.getLogger(__name__)

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handles incoming HTTP requests for health check endpoints."""
    try:
        data = await asyncio.wait_for(reader.read(1024), timeout=5.0)
        request_line = data.decode("utf-8", errors="ignore").split("\r\n")[0]
        
        path = "/"
        if request_line:
            parts = request_line.split(" ")
            if len(parts) > 1:
                path = parts[1]

        if path in ["/", "/health", "/status"]:
            body = '{"status": "healthy", "service": "Jules Telegram Bot", "version": "1.0.0"}\n'
            response = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{body}"
            )
        else:
            body = '{"error": "not found"}\n'
            response = (
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: application/json; charset=utf-8\r\n"
                f"Content-Length: {len(body.encode('utf-8'))}\r\n"
                "Connection: close\r\n"
                "\r\n"
                f"{body}"
            )

        writer.write(response.encode("utf-8"))
        await writer.drain()
    except Exception as exc:
        logger.debug("Health check connection handling exception: %s", exc)
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def start_health_server(host: str = config.HOST, port: int = config.PORT) -> asyncio.Server:
    """Starts the non-blocking HTTP health check server."""
    server = await asyncio.start_server(handle_client, host, port)
    logger.info("Render health check server listening on http://%s:%s", host, port)
    return server
