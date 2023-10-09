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

    try:
        # Read Excel file (using Pandas)
        df = pd.read_excel("datasets.xlsx", sheet_name=0)
    except Exception as err:
        print("Oops, unable to read input file {}".format(err))
        exit()

    if df is not None:
        # Get the operations (queries)
        read_item_query = graphql.get_operation("read_item_query")
        update_item_mutation = graphql.get_operation("update_item_mutation")

        # For each line from the Excel file, collect metadata to update an item
        for index, row in df.iterrows():
            # Get the key (unique identifier for Zeenea)
            key = row["key"]

            args = {"ref": key}
            # Try to get the item associated with this key to check if it exists
            item = graphql.request(client, read_item_query, args)
            if item is None: # Not found
                print("Item {} wasn't found. Skipping it!".format(key))
                pass

            desc = str(row["description"])
            domain_prop = str(row["domain"])

            # Forge the parameters used to update the item
            args = {"input": {"ref": key, "updates":  {"description": {"content": desc}, "properties": [{"command": "REPLACE","ref": "domain","value": domain_prop}]}}}

            # Then update
            item = graphql.request(client, update_item_mutation, args)
            if item is None:
                print("Item {} wasn't updated".format(key))


if __name__ == "__main__":
    main()
