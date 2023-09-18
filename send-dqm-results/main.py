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

    try:
        # Read CSV file (using Pandas)
        df = pd.read_csv("dqm-results.csv", sep=";")
    except Exception as err:
        print("Oops, unable to read input file {}".format(err))
        exit()

    if df is not None:
        # Get the operations (queries)
        update_dq_statement_mutation = graphql.get_operation("update_dq_statement_mutation")

        # For each line from the CSV file, collect metadata to update a dataset with DQ statements
        current_dataset = ""
        dq_statements = []
        originator = ""
        trust_score = 0
        dashboard_link = ""

        for index, row in df.iterrows():
            # Get the key (unique identifier for Zeenea)
            key = row["dataset"]

            if len(current_dataset) == 0:
                current_dataset = key
                originator = row["originator"]
                trust_score = row["trust_score"]
                dashboard_link = row["dashboard_link"]

            if current_dataset != key and len(key) > 0:
                # update statement
                args = {"ref": key, "quality": {"originator": originator, "trustScore": trust_score, "dashboardLink": dashboard_link, "checks": dq_statements}}
                item = graphql.request(client, update_dq_statement_mutation, args)
                current_dataset = key
                dq_statements = []
                originator = row["originator"]
                trust_score = row["trust_score"]
                dashboard_link = row["dashboard_link"]

            # add DQ statement to the list
            dq_statements.append({"name": row["check_name"], "family": row["check_family"], "description": {"content": row["check_description"]}, "result": row["check_result"], "lastExecutionTime": row["check_lastexec"], "checkLink": row["check_link"]})

        if len(key) > 0:
            # Finally, update the last dataset:
            args = {"ref": key, "quality": {"originator": originator, "trustScore": trust_score, "dashboardLink": dashboard_link, "checks": dq_statements}}
            item = graphql.request(client, update_dq_statement_mutation, args)


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
