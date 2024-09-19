#!/usr/bin/env python
#
# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/


import json
import sys
import textwrap
import uuid

from zeenea.config import read_configuration
from zeenea.graphql import ZeeneaGraphQLClient

UPDATE_OPERATIONS_MUTATION = '''
mutation update_field_2_field_operations(
    $mutation_id: String,
    $ref: ItemReference!,
    $operations: [DataProcessOperationInput!]!
) {
    updateDataProcessOperationsV2(input: {
        clientMutationId: $mutation_id, 
        ref: $ref, 
        operations: $operations
    }) {
        clientMutationId
   }
}
'''


def main():
    # Read the configuration.
    config = read_configuration(['tenant', 'api_secret'])
    input_file = config.get('lineage_input_file', 'input/lineage.json')

    # Create ZeeneaGraphQLClient.
    with ZeeneaGraphQLClient(tenant=config.tenant, api_secret=config.api_secret) as client:
        # Read the input file
        lineage = read_json_file(input_file)

        # Check we have data to process
        if not lineage or not lineage["dataprocesses"]:
            print(f"No data processes in file {input_file}")
            sys.exit(0)

        # Process each data process
        for process in lineage["dataprocesses"]:
            # Get the operations
            if process_operations := process.get("operations"):
                # Get the key (unique identifier for Zeenea)
                key = process["key"]

                # Prepare the operation list
                operations = [{
                    "description": {"content": op["description"]},
                    "inputFieldKeys": op["input_fields"],
                    "outputFieldKeys": op["output_fields"]
                } for op in process_operations]

                # Generate a mutation id
                mutation_id = str(uuid.uuid1())

                # Call the update request and check the result
                response = client.request(UPDATE_OPERATIONS_MUTATION, mutation_id=mutation_id, ref=key,
                                          operations=operations)

                # Test mutation_id consistency
                if response.data:
                    response_mutation_id = response.data['updateDataProcessOperationsV2']['clientMutationId']
                    if response_mutation_id != mutation_id:
                        print(f"ERROR inconsistent client mutation id: got {response_mutation_id}, expected {mutation_id}",
                              file=sys.stderr)
                        continue

                # Process errors
                if response.has_error('ITEM_NOT_FOUND', unique=True):
                    print(f"Item '{key}' not found")
                elif response.has_errors():
                    print(f"Item '{key}'\n" + textwrap.indent(str(response.errors), '\t'))
                else:
                    print(f"Item '{key}' updated")


def read_json_file(input_file):
    """Read the content of the json file."""
    try:
        with open(input_file) as f:
            return json.load(f)
    except Exception as err:
        print(f"ERROR unable to read json file '{input_file}': {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
