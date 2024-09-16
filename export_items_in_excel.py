#!/usr/bin/env python
import sys

import pandas as pd

from zeenea.config import read_configuration
from zeenea.graphql import ZeeneaGraphQLClient, GqlResponse, end_cursor, GqlPage
from zeenea.tool import create_parent

FIND_DATASETS_QUERY = '''
query find_datasets(
    $filters: [ItemFilterInput!],
    $after: String,
    $page_size: Int
) {
    items(
        type: "dataset",
        filters: $filters,
        after: $after,
        first: $page_size
    ) {
        nodes {
          key
          name
          domain: property(ref: "domain")
        }
        pageInfo {
          hasNextPage
          endCursor
        }
        totalCount
    }
}
'''


def main():
    # Read the configuration.
    config = read_configuration(['tenant', 'api_secret'])

    # Read parameters from the configuration
    excel_file = config.get('excel_output_file', 'output/datasets.xlsx')
    page_size = config.get('page_size', 2)

    # Create ZeeneaGraphQLClient.
    client = ZeeneaGraphQLClient(tenant=config.tenant, api_secret=config.api_secret)

    # Prepare query variable for the first page.
    filters = [
        {
            "property": {
                "ref": "domain",
                "isEmpty": False
            }
        }
    ]

    # Request the first page.
    response = client.request(FIND_DATASETS_QUERY, filters=filters, page_size=page_size)

    # Read the page.
    if page := read_page(response):
        print(f"{page.total_items} items found... Processing them.")
        item_list = page.content
        next_cursor = page.next_cursor

        # Fetch the other pages as long as there are more.
        while next_cursor:
            response = client.request(FIND_DATASETS_QUERY, filters=filters, page_size=page_size, after=next_cursor)
            if page:= read_page(response):
                item_list += page.content
                next_cursor = page.next_cursor
            else:
                print("No item found in this page")
                next_cursor = None

        write_to_excel(excel_file, item_list)
    else:
        print("No item found")


def read_page(response: GqlResponse) -> GqlPage[list[dict]] | None:
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
    items = response.data['items']
    item_list = [{'key': item['key'], 'name': item['name'], 'domain': item['domain'][0] if item.get('domain') else None}
                 for item in items['nodes']]
    return GqlPage(item_list, items['totalCount'], end_cursor(items['pageInfo']))


def write_to_excel(file: str, item_list: list[dict]) -> None:
    """
    Write the list of items to the Excel file.

    :param file: File path to write into.
    :param item_list: Item list.
    :type item_list: list[dict]
    :return:  None
    """
    if item_list:
        try:
            df = pd.DataFrame.from_records(item_list, columns=['key', 'name', 'domain'])
            create_parent(file)
            df.to_excel(file, index=False, header=True)
            print("Excel file generated")
        except Exception as e:
            print(f"Failed to write to Excel file: {e}")


if __name__ == "__main__":
    main()
