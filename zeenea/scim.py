# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import re
from types import TracebackType
from typing import Self

import httpx
from scim2_client import SCIMClient
from scim2_models import User, Group, Error, PatchOp, PatchOperation, SearchRequest, ListResponse, Name


class ScimError:
    def __init__(self, message: str) -> None:
        self.message = message

    def __str__(self) -> str:
        return f"ERROR: {self.message}"


class ScimNotFound(ScimError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ScimTooMany(ScimError):
    def __init__(self, message: str) -> None:
        super().__init__(message)


class ZeeneaUser:
    def __init__(self, email: str, *, given_name: str, family_name: str, id: str | None = None) -> None:
        self.email: str = email
        self.given_name: str = given_name
        self.family_name: str = family_name
        self.id: str = id

    @classmethod
    def from_scim(cls, scim_user: User) -> Self:
        if scim_user.name:
            given_name = scim_user.name.given_name
            family_name = scim_user.name.family_name
        else:
            given_name = None
            family_name = None
        return ZeeneaUser(scim_user.user_name, given_name=given_name, family_name=family_name, id=scim_user.id)

    def to_scim(self):
        email: str = self.email
        given_name: str = self.given_name
        family_name: str = self.family_name
        name = Name(given_name=given_name, family_name=family_name) if given_name or family_name else None
        return User(id=self.id, user_name=email, name=name)


class ZeeneaScimClient:
    def __init__(self, *, tenant: str, api_secret: str):
        if not re.match('^https?://', tenant):
            url = f"https://{tenant}.zeenea.app/api/scim/v2"
        else:
            url = f"{tenant}/api/scim/v2"
        headers = {"Authorization": f"Bearer {api_secret}"}
        self.http_client = httpx.Client(base_url=url, headers=headers)
        self.scim_client = SCIMClient(self.http_client, resource_types=(User, Group))

    def close(self):
        """Close the HTTP client."""
        self.http_client.close()

    def __enter__(self) -> Self:
        self.http_client.__enter__()
        return self

    def __exit__(self,
                 exc_type: type[BaseException] | None = None,
                 exc_val: BaseException | None = None,
                 exc_tb: TracebackType | None = None,
                 ) -> None:
        self.http_client.__exit__(exc_type, exc_val, exc_tb)

    def create_user(self, user: ZeeneaUser) -> ZeeneaUser | ScimError:
        scim_user = user.to_scim()
        match self.scim_client.create(scim_user, raise_scim_errors=False):
            case User() as new_user:
                return ZeeneaUser.from_scim(new_user)
            case Error() as e:
                return ScimError(f"Failed to create user {user.email}: {e.status} {e.detail}")
            case _ as unknown:
                return ScimError(
                    f"Failed to create user {user.email}: unknown result ({type(unknown)}): {unknown}")

    def delete_user(self, email: str) -> ZeeneaUser | ScimError:
        match self.find_user(email):
            case ZeeneaUser() as user:
                match self.scim_client.delete(User, user.id, raise_scim_errors=False):
                    case None:
                        return user
                    case Error(status=404):
                        return ScimNotFound(f"User {email} not found")
                    case Error() as e:
                        return ScimError(f"Failed to delete user {email} ({user.id}): {e.status} {e.detail}")
            case err:
                return err

    def find_user(self, email: str) -> ZeeneaUser | ScimError:
        match self.scim_client.query(User, search_request=SearchRequest(filter=f'userName eq "{email}"'),
                                     raise_scim_errors=False):
            case ListResponse() as response:
                match response.total_results:
                    case 0:
                        return ScimNotFound(f"User {email} not found")
                    case 1:
                        if isinstance(response.resources[0], User):
                            return ZeeneaUser.from_scim(response.resources[0])
                        else:
                            return ScimError(
                                f"Failed to find user {email}: invalid resource type ({type(response.resources[0])})")
                    case n:
                        return ScimTooMany(f"Too many users {email}: {n}")
            case Error(status=404):
                return ScimNotFound(f"User {email} not found")
            case Error() as e:
                return ScimError(f"Failed to find user {email}: {e.status} {e.detail}")
            case _ as unknown:
                return ScimError(f"Failed to find user {email}: unknown result ({type(unknown)}): {unknown}")

    def group_add_user(self, group_name: str, user_id: str) -> None | ScimError:
        match self.find_group_by_name(group_name):
            case Group() as group:
                # TODO modifier le groupe
                self.scim_client.modify(group, PatchOp({'operations': PatchOperation({'op': PatchOperation.Op.add, })}))
            case ScimError() as e:
                return e

    def find_group_by_name(self, name: str) -> Group | ScimError:
        match self.scim_client.query(Group, search_request=SearchRequest(filter=f'displayName eq "{name}"'),
                                     raise_scim_errors=False):
            case ListResponse() as response:
                match response.total_results:
                    case 0:
                        return ScimNotFound(f"Group with name {name} not found")
                    case 1:
                        if isinstance(response.resources[0], Group):
                            group = response.resources[0]
                            return group
                        else:
                            return ScimError(
                                f"Failed to find group {name}: invalid resource type ({type(response.resources[0])})")
                    case n:
                        return ScimTooMany(f"Failed to find group {name}: too many matching resources: {n}")
            case Error(status=404):
                return ScimNotFound(f"Group with name {name} not found")
            case Error() as e:
                return ScimError(f"Failed to find group {name}: {e.status} {e.detail}")
            case _ as unknown:
                return ScimError(f"Failed to find group {name}: unknown result ({type(unknown)}): {unknown}")
