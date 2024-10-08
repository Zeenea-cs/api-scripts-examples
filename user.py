#!/usr/bin/env python
#
# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import argparse
import sys
from argparse import Namespace

from scim2_models import User

from zeenea.config import read_configuration
from zeenea.scim import ZeeneaScimClient, ScimError, ScimNotFound, ScimTooMany, ZeeneaUser


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
    with open_scim_client() as scim_client:
        email: str = arguments.email
        given_name: str = arguments.given_name if 'given_name' in arguments else None
        family_name: str = arguments.family_name if 'family_name' in arguments else None
        user = ZeeneaUser(email, given_name=given_name, family_name=family_name)
        match scim_client.create_user(user):
            case ZeeneaUser() as new_user:
                print(f"Created new user {new_user.email} ({new_user.id})")
                if 'groups' in arguments and arguments.groups:
                    add_user_to_groups(scim_client, new_user.id, arguments.group)
            case ScimError() as e:
                print(e.message, file=sys.stderr)
                sys.exit(1)


def delete_user(arguments: Namespace) -> None:
    with open_scim_client() as scim_client:
        email = arguments.email
        match scim_client.delete_user(email):
            case User() as user:
                print(f"Deleted user {email} ({user.id})")
            case ScimNotFound() | ScimTooMany() as e:
                print(e)
            case ScimError() as e:
                print(e, file=sys.stderr)
                sys.exit(1)


def add_user_to_groups(client: ZeeneaScimClient, user_id: str, group_list: list[str]):
    for group_name in group_list:
        match client.group_add_user(group_name, user_id):
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
    return main_parser.parse_args()


if __name__ == '__main__':
    main()
