"""
Client for official Google Jules REST API (jules.googleapis.com/v1alpha).
Allows autonomous interaction with GitHub repositories, sessions, activities, and PR creation.
"""

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
import config

logger = logging.getLogger(__name__)

class JulesApiException(Exception):
    """Custom exception for Jules REST API interactions."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[str] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class JulesApiClient:
    """Async wrapper for the Google Jules REST API."""

    @classmethod
    def _execute_request(
        cls,
        endpoint: str,
        method: str = "GET",
        payload: Optional[Dict[str, Any]] = None,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Synchronous HTTP worker executed in thread pool."""
        key = (api_key or config.JULES_API_KEY).strip()
        if not key:
            raise JulesApiException("لم يتم ضبط مفتاح Jules API. يرجى إضافة JULES_API_KEY في الإعدادات أو عبر /apikey.")

        url = f"{config.JULES_API_BASE_URL}/{endpoint.lstrip('/')}"
        headers = {
            "x-goog-api-key": key,
            "Content-Type": "application/json",
            "User-Agent": "AIAssistantBot/1.0"
        }

        data_bytes = json.dumps(payload).encode("utf-8") if payload is not None else None
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                content = response.read().decode("utf-8")
                return json.loads(content) if content else {}
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8", errors="ignore")
            logger.error("Jules API HTTP %s on %s: %s", err.code, url, err_body)
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("error", {}).get("message", err_body)
            except Exception:
                msg = err_body
            raise JulesApiException(f"خطأ من Jules API ({err.code}): {msg}", status_code=err.code, response_body=err_body)
        except urllib.error.URLError as url_err:
            logger.error("Jules API network error: %s", url_err)
            raise JulesApiException(f"فشل الاتصال بخادم Jules API: {url_err}")

    @classmethod
    async def list_sources(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves list of connected GitHub repositories (Sources).
        Endpoint: GET /v1alpha/sources
        """
        res = await asyncio.to_thread(cls._execute_request, "sources", "GET", None, api_key)
        return res.get("sources", [])

    @classmethod
    async def get_source(cls, source_name: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves details of a specific source.
        Endpoint: GET /v1alpha/sources/{sourceId}
        """
        clean_name = source_name if source_name.startswith("sources/") else f"sources/{source_name}"
        return await asyncio.to_thread(cls._execute_request, clean_name, "GET", None, api_key)

    @classmethod
    async def create_session(
        cls,
        source: str,
        prompt: str,
        starting_branch: str = "main",
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Creates an autonomous coding session on the given repository.
        Endpoint: POST /v1alpha/sessions
        """
        clean_source = source if source.startswith("sources/") else f"sources/{source}"
        payload = {
            "prompt": prompt,
            "sourceContext": {
                "source": clean_source,
                "githubRepoContext": {
                    "startingBranch": starting_branch
                }
            },
            "automationMode": "AUTO_CREATE_PR"
        }
        return await asyncio.to_thread(cls._execute_request, "sessions", "POST", payload, api_key)

    @classmethod
    async def get_session(cls, session_name: str, api_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches status of an active coding session.
        Endpoint: GET /v1alpha/{session_name}
        """
        clean_name = session_name if session_name.startswith("sessions/") else f"sessions/{session_name}"
        return await asyncio.to_thread(cls._execute_request, clean_name, "GET", None, api_key)

    @classmethod
    async def list_sessions(cls, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lists past and active coding sessions.
        Endpoint: GET /v1alpha/sessions
        """
        res = await asyncio.to_thread(cls._execute_request, "sessions", "GET", None, api_key)
        return res.get("sessions", [])

    @classmethod
    async def list_activities(cls, session_name: str, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lists timeline of activities and progress events in a session.
        Endpoint: GET /v1alpha/{session_name}/activities
        """
        clean_name = session_name if session_name.startswith("sessions/") else f"sessions/{session_name}"
        res = await asyncio.to_thread(cls._execute_request, f"{clean_name}/activities", "GET", None, api_key)
        return res.get("activities", [])

    @classmethod
    async def send_message(
        cls,
        session_name: str,
        message: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends follow-up instruction to an ongoing session.
        Endpoint: POST /v1alpha/{session_name}:sendMessage
        """
        clean_name = session_name if session_name.startswith("sessions/") else f"sessions/{session_name}"
        payload = {"prompt": message}
        return await asyncio.to_thread(cls._execute_request, f"{clean_name}:sendMessage", "POST", payload, api_key)
