#!/usr/bin/env python
#
# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import sys
import textwrap

import pandas as pd

from zeenea.config import read_configuration
from zeenea.graphql import ZeeneaGraphQLClient

UPDATE_ITEM_MUTATION = '''
mutation update_description_and_domain(
    $ref: ItemReference!, 
    $description: String!,
    $descType: ContentType!,
    $domain: PropertyValue
) {
    updateItem(input: {
        ref: $ref,
        updates: {
            descriptionV3: { 
                content: { 
                    content: $description,
                    contentType: $descType 
                },
                recomputeSummary: true 
            },
            properties: [{ command: REPLACE, ref: "domain", value: $domain }]
        }  
    }) {
        item {
            key
            descriptionV2 { content { content } }
            domain: property(ref: "domain")
        }
    }
}
'''


def main():
    # Read the configuration.
    config = read_configuration(['tenant', 'api_secret'])
    excel_file = config.get('excel_input_file', 'input/datasets.xlsx')

    # Create ZeeneaGraphQLClient.
    with ZeeneaGraphQLClient(tenant=config.tenant, api_secret=config.api_secret) as client:
        # Read data from the Excel file.
        data = read_from_excel(excel_file)

        # For each line from the Excel file, collect metadata to update an item.
        for row_idx, row in data:
            # Get the key (unique identifier for Zeenea)
            key = row['key']
            domain = [row['domain']] if 'domain' in row else []
            desc = row.get('description', '')
            desc_type = row.get('description type', 'RAW').upper()
            if desc_type not in ['RAW', 'HTML']:
                print(f"Item '{key}' (line {row_idx}) has invalid description type '{desc_type}'")

            # Then update.
            response = client.request(UPDATE_ITEM_MUTATION, ref=key, descType=desc_type, description=desc, domain=domain)

            # Process the errors
            if response.has_error('ITEM_NOT_FOUND', unique=True):
                print(f"Item '{key}' (line {row_idx}) not found")
            elif response.has_errors():
                print(f"Item '{key}' (line {row_idx}) errors\n" + textwrap.indent(str(response.errors), '\t'),
                      file=sys.stderr)

            # Test is the result matches the new values.
            if response.data:
                new_item = response.data['updateItem']['item']
                if desc != new_item['descriptionV2']['content']['content']:
                    print(f"Item '{key}' (line {row_idx}) the description was not updated")
                if domain != new_item['domain']:
                    print(f"Item '{key}' (line {row_idx}) the domain was not updated")


def read_from_excel(excel_file: str):
    """
    Read the Excel file.
    :param excel_file: Path to the Excel file.
    :return: The content of the file as a list of pairs (line number, row).
    """
    try:
        # Read Excel file (using Pandas).
        df = pd.read_excel(excel_file, sheet_name=0)
        # Convert the dataframe to a simple Python collection.
        # The index is shifted to correspond to the line number in the Excel file.
        return [(idx + 2, row.to_dict()) for idx, row in df.iterrows()]

    except Exception as err:
        print(f"Failed to read input file {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
