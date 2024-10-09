#!/usr/bin/env python
#
# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import argparse
import sys
from argparse import Namespace

from zeenea.config import read_configuration
from zeenea.scim import ZeeneaScimClient, ScimError, ScimNotFound, ScimTooMany, ZeeneaUser


def main() -> None:
    arguments = parse_arguments()
    match arguments.action:
        case 'create':
            create_user(arguments)
        case 'delete':
            delete_user(arguments)
        case 'modify':
            modify_user(arguments)
        case _:
            print(f'Unknown action: {arguments.action}')
            sys.exit(1)


def create_user(arguments: Namespace) -> None:
    with open_scim_client() as scim_client:
        email: str = arguments.email
        given_name: str = arguments.given_name if 'given_name' in arguments else None
        family_name: str = arguments.family_name if 'family_name' in arguments else None
        user = ZeeneaUser(email, given_name=given_name, family_name=family_name)
        match scim_client.create_user(user):
            case ZeeneaUser() as new_user:
                print(f"Created new user {new_user.email} ({new_user.id})")
                if 'group' in arguments and arguments.group:
                    add_user_to_groups(scim_client, new_user, arguments.group)
            case ScimError() as e:
                print(e.message, file=sys.stderr)
                sys.exit(1)


def modify_user(arguments: Namespace) -> None:
    given_name: str = arguments.given_name if 'given_name' in arguments else None
    family_name: str = arguments.family_name if 'family_name' in arguments else None
    new_groups: set[str] = set(arguments.group) if 'group' in arguments and arguments.group else None

    if given_name is None and family_name is None and new_groups is None:
        print("Nothing to modify")
        sys.exit(0)

    with open_scim_client() as scim_client:
        match scim_client.find_user(arguments.email):
            case ZeeneaUser() as user:
                print(f"Found user {user.email} ({user.id})")
                if given_name is not None or family_name is not None:
                    modified_user = ZeeneaUser(email=user.email, id=user.id, given_name=given_name, family_name=family_name)
                    match scim_client.modify_user(modified_user):
                        case ZeeneaUser():
                            print(f"Modified user {user.email} ({user.id})")
                        case ScimError() as e:
                            print(f"Failed to modify user {user.email} ({user.id}) {e.message}", file=sys.stderr)
                if new_groups:
                    old_groups: set[str] = user.groups
                    remove_groups: list[str] = list(filter(lambda g: not g in new_groups, old_groups))
                    add_groups: list[str] = list(filter(lambda g: not g in old_groups, new_groups))
                    remove_user_from_groups(scim_client, user, remove_groups)
                    add_user_to_groups(scim_client, user, add_groups)
            case ScimError() as e:
                print(e.message, file=sys.stderr)
                sys.exit(1)


def delete_user(arguments: Namespace) -> None:
    with open_scim_client() as scim_client:
        email = arguments.email
        match scim_client.delete_user(email):
            case ZeeneaUser() as user:
                print(f"Deleted user {email} ({user.id})")
            case ScimNotFound() | ScimTooMany() as e:
                print(e)
            case ScimError() as e:
                print(e, file=sys.stderr)
                sys.exit(1)


def add_user_to_groups(client: ZeeneaScimClient, user: ZeeneaUser, group_list: list[str]):
    for group_name in group_list:
        match client.group_add_user(group_name, user.id):
            case None:
                print(f"Added user {user.email} ({user.id}) to group {group_name}")
            case ScimError() as e:
                print(e, file=sys.stderr)


def remove_user_from_groups(client: ZeeneaScimClient, user: ZeeneaUser, group_list: list[str]):
    for group_name in group_list:
        match client.group_remove_user(group_name, user.id):
            case None:
                print(f"Removed user {user.email} ({user.id}) from group {group_name}")
            case ScimError() as e:
                print(e, file=sys.stderr)


def open_scim_client() -> ZeeneaScimClient:
    settings = read_configuration(['tenant', 'scim_api_secret'])
    return ZeeneaScimClient(tenant=settings.tenant, api_secret=settings.scim_api_secret)


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

    modify_parser = subparsers.add_parser('modify', help="Modify a user")
    modify_parser.set_defaults(action='modify')
    modify_parser.add_argument('-e', '--email', required=True, help="Email address")
    modify_parser.add_argument('--given-name', help="Given name")
    modify_parser.add_argument('--family-name', help="Family name")
    modify_parser.add_argument('-g', '--group', action='append', help='Group to add the user to')

    return main_parser.parse_args()


if __name__ == '__main__':
    main()
