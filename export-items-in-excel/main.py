import sys, getopt
import pandas as pd
from config import settings

import graphql

def main():

    url = "{}/api/catalog/graphql".format(settings.tenant_address)

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-APP-ID": settings.app_id,
        "X-API-KEY": settings.api_key
    }

    client = graphql.client(url=url, headers=headers)

    get_items_query = graphql.get_operation("get_items_query")

    cursor = "*"
    page_size = 2

    items_list = []
    total_items = None
    while (True):
        args = {
            "type": "dataset",
            "filters" : [
                {
                    "property": {
                        "ref": "domain",
                        "isEmpty": False
                    }
                }
            ],
            "after" : cursor,
            "first": page_size
        }

        items = graphql.request(client, get_items_query, args)
        if items is None:
            print("Warning: No item found for this query")
            break
        else:
            if total_items is None:
                total_items = items['items']['totalCount']
                print("{} item(s) found... Processing them.".format(total_items))

            for item in items['items']['nodes']:
                domain = None
                if item['domain'] is not None and len(item['domain']) > 0:
                    domain = item['domain'][0]
                items_list.append({'key': item['key'], 'name': item['name'], 'domain': domain, })

            # Is there a next page?
            has_next_age = items['items']['pageInfo']['hasNextPage']
            if not has_next_age:
                break

            cursor = items['items']['pageInfo']['endCursor']

    if len(items_list) > 0:
        df = pd.DataFrame.from_dict(items_list)
        df.to_excel('datasets.xlsx', index=False, header=True)
        print("Excel file generated")


if __name__ == "__main__":
    main()
