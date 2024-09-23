# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import re
import uuid
from types import TracebackType

import httpx
from scim2_client import SCIMClient
from scim2_models import User, Group


class ScimUser:
    ...


class ZeeneaScimClient:
    def __init__(self, *, tenant: str, api_secret: str):
        if not re.match('^https?://', tenant):
            url = f"https://{tenant}.zeenea.app/api/scim/v2"
        else:
            url = f"{tenant}/api/scim/v2/Users"
        headers = {"Authorization": f"Bearer {api_secret}"}
        self._client = httpx.Client(base_url=url, headers=headers)
        self._scim = SCIMClient(self._client, resource_types=(User, Group))

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        self._client.__enter__()

    def __exit__(self,
                 exc_type: type[BaseException] | None = None,
                 exc_val: BaseException | None = None,
                 exc_tb: TracebackType | None = None,
                 ):
        self._client.__exit__(exc_type, exc_val, exc_tb)

    def create_user(self, user: User) -> None:
        self._scim.create()

    def get_user(self, user_id: uuid.UUID) -> ScimUser:
        response = httpx.request('GET', f'Users/{user_id}')
