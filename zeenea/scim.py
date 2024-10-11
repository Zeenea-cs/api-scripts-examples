# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import re
from types import TracebackType
from typing import Self, Union, Optional, Dict, List

import httpx
from scim2_client import SCIMClient
from scim2_models import User, Group, Error, PatchOp, PatchOperation, SearchRequest, ListResponse, Name, AnyResource


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
    def __init__(self, email: str,
                 *,
                 id: str | None = None,
                 given_name: str | None = None,
                 family_name: str | None = None,
                 groups: set[str] | None = None) -> None:
        self.email: str = email
        self.given_name: str = given_name
        self.family_name: str = family_name
        self.id: str = id
        self.groups = groups if groups is not None else set()

    @classmethod
    def from_scim(cls, scim_user: User) -> Self:
        if scim_user.name:
            given_name = scim_user.name.given_name
            family_name = scim_user.name.family_name
        else:
            given_name = None
            family_name = None
        groups = set(map(lambda gm: gm.display, scim_user.groups)) if scim_user.groups else None
        return ZeeneaUser(scim_user.user_name,
                          given_name=given_name,
                          family_name=family_name,
                          id=scim_user.id,
                          groups=groups)

    def to_scim(self):
        email: str = self.email
        given_name: str = self.given_name
        family_name: str = self.family_name
        name = Name(given_name=given_name, family_name=family_name) if given_name or family_name else None
        return User(id=self.id, user_name=email, name=name)


class ZeeneaScimClient:
    """
    Zeenea Scim Client.

    This is based on the scim2_client implementation.
    It limits the actions to the Zeenea recommend patterns.

    It also offers a temporary workaround waiting for the scim2_client to support the modify operation.

    The client should be closed after usage to close the underlying http client.
    It supports the :keyword:`with` statement, and this is the best option to use it:

    with open_scim_client() as scim_client:
        ...

    Most action return either the expect response or a :keyword:`ScimError` message.

    """
    def __init__(self, *, tenant: str, api_secret: str):
        """
        Initialize a new ZeeneaScimClient instance.

        :param tenant: Zeenea tenant name or URL.
        :param api_secret: Zeenea API Secret.
        """
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
        """
        Create a new user.
        :param user: User to create.
        :return: The new user (new object with the identifier).
        """
        scim_user = user.to_scim()
        match self.scim_client.create(scim_user, raise_scim_errors=False):
            case User() as new_user:
                return ZeeneaUser.from_scim(new_user)
            case Error() as e:
                return ScimError(f"Failed to create user {user.email}: {e.status} {e.detail}")
            case _ as unknown:
                return ScimError(
                    f"Failed to create user {user.email}: unknown result ({type(unknown)}): {unknown}")

    def modify_user(self, user: ZeeneaUser) -> ZeeneaUser | ScimError:
        """
        Modify a new user.
        :param user: User to modify.
        :return: The new user value.
        """
        scim_user = user.to_scim()
        operations = []
        if user.given_name is not None:
            operations.append(PatchOperation(op=PatchOperation.Op.replace_,
                                             path='name.givenName',
                                             value=user.given_name))
        if user.family_name is not None:
            operations.append(PatchOperation(op=PatchOperation.Op.replace_,
                                             path='name.familyName',
                                             value=user.family_name))
        match self.__scim_modify(scim_user, PatchOp(operations=operations), raise_scim_errors=False):
            case User() as modified_user:
                return ZeeneaUser.from_scim(modified_user)
            case Error() as e:
                return ScimError(f"Failed to modify user {user.email} ({user.id}): {e.status} {e.detail}")
            case _ as unknown:
                return ScimError(
                    f"Failed to modify user {user.email} ({user.id}): unknown result ({type(unknown)}): {unknown}")

    def delete_user(self, email: str) -> ZeeneaUser | ScimError:
        """
        Delete a user with the given e-mail.
        :param email: User e-mail.
        :return: The former user or an error message.
        """
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
        """
        Find a user with its e-mail.
        :param email: User e-mail.
        :return: The user or an error.
        """
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
        """
        Add a user to a group.
        :param group_name: Group name.
        :param user_id: User identifier
        :return: None or an error.
        """
        match self.find_group_by_name(group_name):
            case Group() as group:
                operation = PatchOperation(op=PatchOperation.Op.add, path='members', value=[{'value': user_id}])
                match self.__scim_modify(group, PatchOp(operations=[operation]), raise_scim_errors=False):
                    case Group() | None:
                        return None
                    case Error() as e:
                        return ScimError(f"Failed to modify group {group_name}: {e.status} {e.detail}")
                    case unknown:
                        return ScimError(
                            f"Failed to modify group {group_name}: unknown result ({type(unknown)}): {unknown}")
            case ScimError() as e:
                return e
            case unknown:
                return ScimError(f"Unexpected response type from find_group_by_name: {type(unknown)}")

    def group_remove_user(self, group_name: str, user_id: str) -> None | ScimError:
        """
        Remove a user from a group.
        :param group_name: Group name
        :param user_id: User identifier
        :return: None or an error.
        """
        match self.find_group_by_name(group_name):
            case Group() as group:
                operation = PatchOperation(op=PatchOperation.Op.remove, path='members', value=[{'value': user_id}])
                self.__scim_modify(group, PatchOp(operations=[operation]))
            case ScimError() as e:
                return e

    def find_group_by_name(self, name: str) -> Group | ScimError:
        """
        Find a group by its name.
        :param name: Name of the group.
        :return: The group or an error.
        """
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

    def __scim_modify(
        self,
        resource: Union[AnyResource, Dict],
        op: PatchOp,
        check_request_payload: bool = True,
        check_response_payload: bool = True,
        expected_status_codes: Optional[List[int]] = SCIMClient.REPLACEMENT_RESPONSE_STATUS_CODES,
        raise_scim_errors: bool = True,
        **kwargs
    ) -> Optional[Union[AnyResource, Dict]]:
        """
        Private Workaround. Implements the missing implementation of self.scim_client.modify.

        :param resource: The new resource to modify.
            If is a :data:`dict`, the resource type will be guessed from the schema.
        :param check_request_payload: If :data:`False`,
            :code:`resource` is expected to be a dict that will be passed as-is in the request.
        :param check_response_payload: Whether to validate that the response payload is valid.
            If set, the raw payload will be returned.
        :param expected_status_codes: The list of expected status codes form the response.
            If :data:`None` any status code is accepted.
        :param raise_scim_errors: If :data:`True` and the server returned an
            :class:`~scim2_models.Error` object, a :class:`~scim2_client.SCIMResponseErrorObject`
            exception will be raised. If :data:`False` the error object is returned.
        :param kwargs: Additional parameters passed to the underlying
            HTTP request library.

        :return:
            - An :class:`~scim2_models.Error` object in case of error.
            - The updated object as returned by the server in case of success.
        """
        from scim2_models import Resource, Context
        from scim2_client import SCIMRequestError, RequestPayloadValidationError, RequestNetworkError
        from pydantic import ValidationError
        from httpx import RequestError
        import sys

        if not check_request_payload:
            payload = resource
            url = kwargs.pop("url", None)

        else:
            if isinstance(resource, Resource):
                resource_type = resource.__class__

            else:
                resource_type = Resource.get_by_payload(self.scim_client.resource_types, resource)
                if not resource_type:
                    raise SCIMRequestError(
                        "Cannot guess resource type from the payload",
                        source=resource,
                    )

                try:
                    resource = resource_type.model_validate(resource)
                except ValidationError as exc:
                    scim_exc = RequestPayloadValidationError(source=resource)
                    if sys.version_info >= (3, 11):  # pragma: no cover
                        scim_exc.add_note(str(exc))
                    raise scim_exc from exc

            self.scim_client.check_resource_type(resource_type)

            if not resource.id:
                raise SCIMRequestError("Resource must have an id", source=resource)

            try:
                operation = PatchOp.model_validate(op)
            except ValidationError as exc:
                scim_exc = RequestPayloadValidationError(source=op)
                if sys.version_info >= (3, 11):  # pragma: no cover
                    scim_exc.add_note(str(exc))
                raise scim_exc from exc

            payload = operation.model_dump(scim_ctx=Context.RESOURCE_REPLACEMENT_REQUEST)
            url = kwargs.pop(
                "url", self.scim_client.resource_endpoint(resource_type) + f"/{resource.id}"
            )

        try:
            response = self.http_client.patch(url, json=payload, **kwargs)
        except RequestError as exc:
            scim_exc = RequestNetworkError(source=payload)
            if sys.version_info >= (3, 11):  # pragma: no cover
                scim_exc.add_note(str(exc))
            raise scim_exc from exc

        return self.scim_client.check_response(
            response=response,
            expected_status_codes=expected_status_codes,
            expected_types=([resource.__class__] if check_request_payload else None),
            check_response_payload=check_response_payload,
            raise_scim_errors=raise_scim_errors,
            scim_ctx=Context.RESOURCE_REPLACEMENT_RESPONSE,
        )
