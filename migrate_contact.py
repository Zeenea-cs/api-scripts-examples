#!/usr/bin/env python
#
# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/
import argparse
import sys
import textwrap
from dataclasses import dataclass

from dynaconf import Dynaconf

from zeenea.config import read_configuration
from zeenea.graphql import ZeeneaGraphQLClient, GqlResponse, GqlPage, end_cursor

LIST_CONTACT_ITEMS = '''
query list_contact_items(
    $ref: ItemReference!, 
    $responsibility: ConnectionReference!, 
    $after: String,
    $page_size: Int!
) {
    item(ref: $ref) {
        id
        type
        name
        connection(ref: $responsibility, after: $after, first: $page_size) {
           nodes {
               id
               type
               key
               name
           }
           pageInfo {
              hasNextPage
              endCursor
           }
           totalCount
        }
    }
}
'''

LINK_CONTACT_TO_ITEM = '''
mutation link_contact_to_item(
    $mutation_id: String, 
    $contact_ref: ItemReference!, 
    $responsibility: ConnectionReference!, 
    $item_ref: ItemReference!
) {
    updateItem(input: {
        clientMutationId: $mutation_id,
        ref: $item_ref,
        updates: {
            connections: [
                {
                    command: MERGE,
                    connectionRef: $responsibility,
                    itemRefs: [ $contact_ref ]
                }
            ]
        }
    }) {
        clientMutationId
    }
}
'''


@dataclass
class Item:
    """
    Representation of an item.
    """
    id: str
    key: str


def main() -> None:
    # Read the configuration.
    arguments = parse_arguments()
    contact_from: str = getattr(arguments, 'from')
    contact_to: str = arguments.to

    if contact_from == contact_to:
        print(f"You can't copy a contact to itself")
        sys.exit(1)

    config: Dynaconf = read_configuration(['tenant', 'api_secret', 'responsibilities'])
    page_size: int = config.get('page_size', 20)
    responsibilities: list[str] = load_responsibilities(config)

    # Create ZeeneaGraphQLClient.
    with ZeeneaGraphQLClient(tenant=config.tenant, api_secret=config.api_secret) as client:
        for responsibility in responsibilities:
            copy_responsibility(client, contact_from, contact_to, responsibility, page_size)


def load_responsibilities(config: Dynaconf) -> list[str]:
    """
    Load the existing responsibilities from the configuration.

    :param config: The configuration.
    :return: The list of responsibilities with the cura
    """
    responsibilities = config.get('responsibilities')
    if not isinstance(responsibilities, list):
        responsibilities = [responsibilities]
    if 'curator' not in responsibilities:
        responsibilities.insert(0, 'curator')
    return responsibilities


def copy_responsibility(client: ZeeneaGraphQLClient,
                        old_user: str,
                        new_user: str,
                        responsibility: str,
                        page_size: int) -> int:
    error_count = 0
    total_items = 0

    # Request the first page.
    response = client.request(LIST_CONTACT_ITEMS, ref=old_user, responsibility=responsibility, page_size=page_size)
    if page := read_page(response):
        total_items = page.total_items
        print(f"Copy {total_items} contact relations with '{responsibility}'")
        for item in page.content:
            error_count += link_contact_to_item(client, new_user, responsibility, item)
        next_cursor = page.next_cursor

        # Fetch the other pages as long as there are more.
        while next_cursor:
            response = client.request(LIST_CONTACT_ITEMS,
                                      ref=old_user,
                                      responsibility=responsibility,
                                      page_size=page_size,
                                      after=next_cursor)
            if page := read_page(response):
                for item in page.content:
                    error_count += link_contact_to_item(client, new_user, responsibility, item)
                next_cursor = page.next_cursor
            else:
                print("No item found in this page")
                next_cursor = None

    else:
        print(f"No link found for responsibility '{responsibility}'")

    print(f"End of the copy {total_items} contact relations with '{responsibility}'")
    if error_count:
        print(f"{error_count}/{total_items} copy errors for '{responsibility}", file=sys.stderr)

    return error_count


def link_contact_to_item(client: ZeeneaGraphQLClient, contact_ref: str, responsibility: str, item: Item) -> int:
    """
    Create a link from contact_ref to item_ref with responsibility.

    :param client: the Graphql client.
    :param contact_ref: Contact reference.
    :param responsibility: Responsibility.
    :param item_ref: item reference.
    :return: The error count (1 or 0).
    """

    # Fix curator code  inconsistency
    if responsibility == 'curator':
        responsibility = 'curators'
    response = client.request(LINK_CONTACT_TO_ITEM,
                              contact_ref=contact_ref,
                              responsibility=responsibility,
                              item_ref=item.id)
    print(f"Copied link '{contact_ref}' to '{item.key}' with responsibility '{responsibility}'")

    # Process the errors
    if response.has_errors():
        print(
            f"Failed to link '{contact_ref}' to '{item.key}' with responsibility '{responsibility}'\n" +
            textwrap.indent(str(response.errors), '\t'),
            file=sys.stderr)
        return 1
    else:
        return 0


def read_page(response: GqlResponse) -> GqlPage[list[Item]] | None:
    """
    Read the content of a page and process errors if there are some.
    A response can both have data and error. (It must have at list one of them.)
    This happens when a partial set of data is sent by the server.

    :param response: The GraphQL response from the server.
    :type response: GqlResponse
    :return: A Page Result or None fi there is no data or is data is None.
    :rtype: GqlPage | None
    """
    if response.errors:
        print(str(response.errors), file=sys.stderr)
    if response.data is None:
        return None

    item = response.data['item']
    connection = item.get('connection')
    if connection is None:
        return None

    item_list = [Item(id=node['id'], key=node['key']) for node in connection['nodes']]
    return GqlPage(item_list, connection['totalCount'], end_cursor(connection['pageInfo']))


def parse_arguments() -> argparse.Namespace:
    """
    Parse the command line arguments.

    :return: The argparse.Namespace containing the arguments values.
    """
    parser = argparse.ArgumentParser(description="CLI to copy contact-items links of a contact to another one.")

    parser.add_argument('--from', required=True, help="Email address of the contact to copy from.")
    parser.add_argument('--to', required=True, help="Email address of the contact to copy to.")

    return parser.parse_args()


if __name__ == '__main__':
    main()
