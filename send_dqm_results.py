#!/usr/bin/env python
#
# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import csv
import sys
import textwrap
import uuid
from itertools import groupby

from zeenea.config import read_configuration
from zeenea.graphql import ZeeneaGraphQLClient

UPDATE_DQ_STATEMENT_MUTATION = '''
mutation UpdateDataQualityStatement(
    $mutation_id: String,
    $ref: ItemReference!,
    $quality: DataQualityStatementInput!
) {
    updateDataQualityStatementV2(input: {
        clientMutationId: $mutation_id,
        ref: $ref,
        quality: $quality
    }) {
        clientMutationId
    }
}
'''


def main():
    # Read the configuration.
    config = read_configuration(['tenant', 'api_secret'])
    input_file = config.get('dqm_input_file', 'input/dqm-results.csv')

    # Create ZeeneaGraphQLClient.
    with ZeeneaGraphQLClient(tenant=config.tenant, api_secret=config.api_secret) as client:
        # Read the input file
        dqm = read_csv_file(input_file)

        if not dqm:
            print("No data quality statements found.")
            sys.exit(0)

        # For each line from the CSV file, collect metadata to update a dataset with DQ statements
        for key, row_group in groupby(sorted(dqm, key=lambda x: x['dataset']), key=lambda x: x['dataset']):
            # row group is an iterator we store it in a list to be able to use the first element twice
            rows = list(row_group)
            first_row = rows[0]

            try:
                quality = {
                    'originator': first_row['originator'],
                    'trustScore': read_float(first_row, 'trust_score'),
                    'dashboardLink': first_row['dashboard_link'],
                    'checks': [
                        {
                            'name': row['check_name'],
                            'family': row['check_family'],
                            'description': ({'content': row['check_description']} if row['check_description'] else None),
                            'result': row['check_result'],
                            'lastExecutionTime': row['check_lastexec'],
                            'checkLink': row['check_link']
                        } for row in rows
                    ]
                }
            except InvalidColumnError as e:
                print(f"Item '{key}' is invalid:", e)
                continue

            # Generate a mutation id
            mutation_id = str(uuid.uuid1())

            # Call the update request and check the result
            response = client.request(UPDATE_DQ_STATEMENT_MUTATION, mutation_id=mutation_id, ref=key, quality=quality)

            # Test mutation_id consistency
            if response.data:
                response_mutation_id = response.data['updateDataQualityStatementV2']['clientMutationId']
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
                print(f"Item '{key}' updated successfully")


def read_csv_file(input_file: str) -> list[dict[str, str]]:
    """Read the content of the csv file."""
    try:
        with open(input_file, newline='') as f:
            reader = csv.DictReader(f, delimiter=';')
            return list(reader)
    except Exception as err:
        print(f"ERROR unable to read csv file '{input_file}': {err}", file=sys.stderr)
        sys.exit(1)


def read_float(row: dict[str, str], column: str) -> float:
    try:
        return float(row[column])
    except KeyError as e:
        raise InvalidColumnError(f"Missing column '{column}'") from e
    except ValueError as e:
        raise InvalidColumnError(f"Invalid value in column '{column}', expected float but got '{row[column]}'") from e


class InvalidColumnError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


if __name__ == "__main__":
    main()
