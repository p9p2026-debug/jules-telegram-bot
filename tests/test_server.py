"""
Automated unit tests for Health Check Server.
"""

import asyncio
import urllib.request
import unittest
from utils.server import start_health_server

class TestHealthServer(unittest.IsolatedAsyncioTestCase):

    async def test_health_endpoints(self):
        port = 9876
        server = await start_health_server(host="127.0.0.1", port=port)
        try:
            # Test /health
            def _request(path):
                url = f"http://127.0.0.1:{port}{path}"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3) as resp:
                    return resp.status, resp.read().decode("utf-8")

            status, body = await asyncio.to_thread(_request, "/health")
            self.assertEqual(status, 200)
            self.assertIn("healthy", body)

            # Test /
            status_root, body_root = await asyncio.to_thread(_request, "/")
            self.assertEqual(status_root, 200)
            self.assertIn("AI Telegram Bot", body_root)

        finally:
            server.close()
            await server.wait_closed()

if __name__ == "__main__":
    unittest.main()
