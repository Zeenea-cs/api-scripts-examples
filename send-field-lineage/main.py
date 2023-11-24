import sys, getopt
import json
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

    f = None
    lineage_raw = None

    try:
        f = open('lineage.json')
        lineage_raw = json.load(f)
    except Exception as err:
        print("Oops, unable to read input file {}".format(err))
        exit()

    if lineage_raw is not None and lineage_raw["dataprocesses"] is not None:
        # Get the operation
        update_dq_statement_mutation = graphql.get_operation("update_operations_mutation")

        for dataprocess in lineage_raw["dataprocesses"]:
            # Get the key (unique identifier for Zeenea)
            key = dataprocess["key"]

            operations = []
            dataprocess_operations = dataprocess["operations"]

            if dataprocess_operations is not None:
                for op in dataprocess_operations:
                    operation = {}
                    operation["description"] = {"content": op["description"]}
                    operation["inputFieldKeys"] = op["input_fields"]
                    operation["outputFieldKeys"] = op["output_fields"]
                    operations.append(operation)

            if len(key) > 0:
    #            # Finally, update the last dataset:
                args = {"ref": key, "operations": operations}
                item = graphql.request(client, update_dq_statement_mutation, args)

    if f is not None:
        f.close()

if __name__ == "__main__":
    main()
