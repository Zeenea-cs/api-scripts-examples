import sys, getopt
import pandas as pd

import graphql

def main(zeenea_tenant, zeenea_app_id, zeenea_api_key):

    url = "https://{}.zeenea.app/api/catalog/graphql".format(zeenea_tenant)

    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "X-APP-ID": zeenea_app_id,
        "X-API-KEY": zeenea_api_key
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
    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "e:a:k:", ["env=", "appid=", "apikey="])

    zeenea_env = ""
    zeenea_app_id = ""
    zeenea_api_key = ""

    for opt, arg in opts:
        if opt in ("-e", "--env"):
            zeenea_env = arg
        elif opt in ("-a", "--appid"):
            zeenea_app_id = arg
        elif opt in ("-k", "--apikey"):
            zeenea_api_key = arg

    main(zeenea_env, zeenea_app_id, zeenea_api_key)
