"""
Power BI Service Semantic Model Refresh Trigger.
Triggers an automated refresh of the Power BI semantic model via the Power BI REST API
after batch ingestion completes.
"""

import logging
from typing import Any, Dict, Optional
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class PowerBIRefreshClient:
    """
    Automates semantic model dataset refresh in Power BI Service using Azure AD Service Principal.
    """

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        workspace_id: Optional[str] = None,
        dataset_id: Optional[str] = None
    ):
        self.tenant_id = tenant_id or settings.POWERBI_TENANT_ID
        self.client_id = client_id or settings.POWERBI_CLIENT_ID
        self.client_secret = client_secret or settings.POWERBI_CLIENT_SECRET
        self.workspace_id = workspace_id or settings.POWERBI_WORKSPACE_ID
        self.dataset_id = dataset_id or settings.POWERBI_DATASET_ID

    def is_configured(self) -> bool:
        return bool(
            self.tenant_id
            and self.client_id
            and self.client_secret
            and self.workspace_id
            and self.dataset_id
        )

    async def get_access_token(self) -> Optional[str]:
        """Obtains OAuth2 bearer token from Microsoft Entra ID (Azure AD)."""
        if not self.is_configured():
            return None

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": "https://analysis.windows.net/powerbi/api/.default"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(token_url, data=data)
            if resp.status_code == 200:
                token_data = resp.json()
                return token_data.get("access_token")
            else:
                logger.error("Power BI OAuth2 token request failed [%d]: %s", resp.status_code, resp.text)
                return None

    async def trigger_dataset_refresh(self) -> Dict[str, Any]:
        """
        Triggers dataset refresh in Power BI Service workspace.
        """
        if not settings.POWERBI_REFRESH_ENABLED:
            logger.info("Power BI refresh is disabled in configuration (POWERBI_REFRESH_ENABLED=false).")
            return {"status": "skipped", "reason": "disabled_in_config"}

        if not self.is_configured():
            logger.warning("Power BI credentials not fully configured; skipping automated refresh.")
            return {"status": "skipped", "reason": "missing_credentials"}

        token = await self.get_access_token()
        if not token:
            return {"status": "failed", "reason": "authentication_failed"}

        url = f"https://api.powerbi.com/v1.0/myorg/groups/{self.workspace_id}/datasets/{self.dataset_id}/refreshes"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, headers=headers, json={"notifyOption": "NoNotification"})
            if resp.status_code in (200, 202):
                logger.info("Power BI dataset refresh triggered successfully for dataset %s", self.dataset_id)
                return {"status": "success", "status_code": resp.status_code}
            else:
                logger.error("Power BI dataset refresh failed [%d]: %s", resp.status_code, resp.text)
                return {"status": "failed", "status_code": resp.status_code, "detail": resp.text}


def trigger_powerbi_refresh_sync() -> Dict[str, Any]:
    """Synchronous helper for CLI batch runner."""
    import asyncio
    client = PowerBIRefreshClient()
    return asyncio.run(client.trigger_dataset_refresh())
