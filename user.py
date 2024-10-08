#!/usr/bin/env python
#
# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import argparse
import re
import sys
from argparse import Namespace
from enum import Enum

import httpx
from scim2_client import SCIMClient
from scim2_models import User, Group, Error, Name, SearchRequest, ListResponse, PatchOp, PatchOperation

from zeenea.config import read_configuration


def main() -> None:
    arguments = parse_arguments()
    match arguments.action:
        case 'create':
            create_user(arguments)
        case 'delete':
            delete_user(arguments)
        case _:
            print(f'Unknown action: {arguments.action}')
            sys.exit(1)


def create_user(arguments: Namespace) -> None:
    with open_http_client() as http_client:
        scim_client: SCIMClient = open_scim_client(http_client)
        email: str = arguments.email
        given_name: str = arguments.given_name
        family_name: str = arguments.family_name
        name = Name(given_name=given_name, family_name=family_name) if given_name or family_name else None
        match scim_client.create(User(user_name=email, name=name), raise_scim_errors=False):
            case User() as new_user:
                print(f"Created new user {email} ({new_user.id})")
                if arguments.groups:
                    set_groups(new_user.id, GroupCommand.ADD, arguments.group, scim_client)
            case Error() as e:
                print(f"Failed to create user {email}: {e.status} {e.detail}", file=sys.stderr)
                sys.exit(1)
            case _ as unknown:
                print(f"Failed to create user {email}: unknown result ({type(unknown)}): {unknown}", file=sys.stderr)
                sys.exit(2)


def delete_user(arguments: Namespace) -> None:
    with open_http_client() as http_client:
        scim_client = open_scim_client(http_client)
        email = arguments.email
        user = find_user_by_email(scim_client, email)
        if user is not None:
            match scim_client.delete(User, user.id, raise_scim_errors=False):
                case None:
                    print(f"Deleted user {email} ({user.id})")
                case Error(status=404):
                    print(f"User {email} ({user.id}) not found")
                case Error() as e:
                    print(f"Failed to delete user {email} ({user.id}): {e.status} {e.detail}", file=sys.stderr)
                    sys.exit(1)


def find_user_by_email(scim_client: SCIMClient, email: str) -> User | None:
    match scim_client.query(User, search_request=SearchRequest(filter=f'userName eq "{email}"'),
                            raise_scim_errors=False):
        case ListResponse() as response:
            match response.total_results:
                case 0:
                    print(f"User {email} not found")
                    return None
                case 1:
                    if isinstance(response.resources[0], User):
                        user = response.resources[0]
                        print(f"Found user {email} ({user.id})")
                        return user
                    else:
                        print(f"Failed to find user {email}: invalid resource type ({type(response.resources[0])})",
                              file=sys.stderr)
                        sys.exit(2)
                case n:
                    print(f"Failed to find user {email}: too many matching resources: {n}", file=sys.stderr)
                    sys.exit(3)
        case Error(status=404):
            print(f"User {email} not found")
            return None
        case Error() as e:
            print(f"Failed to find user {email}: {e.status} {e.detail}", file=sys.stderr)
            sys.exit(1)
        case _ as unknown:
            print(f"Failed to find user {email}: unknown result ({type(unknown)}): {unknown}", file=sys.stderr)
            sys.exit(2)


def find_group_by_name(scim_client: SCIMClient, name: str) -> User | None:
    match scim_client.query(Group, search_request=SearchRequest(filter=f'displayName eq "{name}"'),
                            raise_scim_errors=False):
        case ListResponse() as response:
            match response.total_results:
                case 0:
                    print(f"Group {name} not found")
                    return None
                case 1:
                    if isinstance(response.resources[0], Group):
                        group = response.resources[0]
                        print(f"Found group {name} ({group.id})")
                        return group
                    else:
                        print(f"Failed to find group {name}: invalid resource type ({type(response.resources[0])})",
                              file=sys.stderr)
                        sys.exit(2)
                case n:
                    print(f"Failed to find group {name}: too many matching resources: {n}", file=sys.stderr)
                    sys.exit(3)
        case Error(status=404):
            print(f"Group {name} not found")
            return None
        case Error() as e:
            print(f"Failed to find group {name}: {e.status} {e.detail}", file=sys.stderr)
            sys.exit(1)
        case _ as unknown:
            print(f"Failed to find group {name}: unknown result ({type(unknown)}): {unknown}", file=sys.stderr)
            sys.exit(2)


class GroupCommand(Enum):
    SET: str = 'set'
    ADD: str = 'add'
    REMOVE: str = 'remove'


def set_groups(user_id: str, command: GroupCommand, groups: list[str], scim_client: SCIMClient) -> None:
    match command:
        case GroupCommand.ADD:
            for group in groups:
                group_add_user(group, user_id, scim_client)

        case GroupCommand.SET:
            # TODO remove existing values
            for group in groups:
                group_add_user(group, user_id, scim_client)

        case GroupCommand.REMOVE:
            for group in groups:
                group_remove_user(group, user_id, scim_client)


def group_add_user(groupName: str, user_id: str, scim_client: SCIMClient):
    group = find_group_by_name(scim_client, groupName)
    if group:
        scim_client.modify(Group, PatchOp({'operations': PatchOperation({'op': PatchOperation.Op.add, })}))


def group_remove_user(group: str, user_id: str, scim_client: SCIMClient):
    pass


def open_http_client() -> httpx.Client:
    settings = read_configuration(['tenant', 'scim_api_secret'])
    tenant = settings.tenant
    if not re.match('^https?://', tenant):
        url = f"https://{tenant}.zeenea.app/api/scim/v2"
    else:
        url = f"{tenant}/api/scim/v2"
    headers = {"Authorization": f"Bearer {settings.scim_api_secret}"}
    return httpx.Client(base_url=url, headers=headers)


def open_scim_client(http_client: httpx.Client) -> SCIMClient:
    return SCIMClient(http_client, resource_types=(User, Group))


def parse_arguments() -> argparse.Namespace:
    main_parser = argparse.ArgumentParser(description="CLI to manage users with scim as an integration example")
    subparsers = main_parser.add_subparsers(title="user commands")

    create_parser = subparsers.add_parser('create', help="Create a new user")
    create_parser.set_defaults(action='create')
    create_parser.add_argument('-e', '--email', required=True, help="Email address")
    create_parser.add_argument('--given-name', help="Given name")
    create_parser.add_argument('--family-name', help="Family name")
    create_parser.add_argument('-g', '--group', action='append', help='Group to add the user to')

    delete_parser = subparsers.add_parser('delete', help="Delete an existing user")
    delete_parser.set_defaults(action='delete')
    delete_parser.add_argument('-e', '--email', required=True, help="Email address")
    return main_parser.parse_args()


if __name__ == '__main__':
    main()