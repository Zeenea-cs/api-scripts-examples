# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/
#
# This is not really an example but a small wizard to help you to configure the example settings.
# You don't need such a functionality for you application.
# Call it with the command:
#      python -m zeenea.setup

import os

import questionary
import tomlkit
from tomlkit import TOMLDocument

SCIM_EXAMPLES = ['user.py']
GRAPHQL_EXAMPLES = [
    'export_items_in_excel.py',
    'update_items_from_excel.py',
    'send_field_lineage.py',
    'send_dqm_results.py'
]


def main():
    settings = read_toml('settings.toml')
    secrets = read_toml('.secrets.toml')

    if tenant := questionary.text("Zeenea tenant:", default=settings.get('tenant', '')).ask():
        settings['tenant'] = tenant
    elif 'tenant' in settings:
        del settings['tenant']

    examples = questionary.checkbox("Which example do you want to try ?",
                                    choices=GRAPHQL_EXAMPLES + SCIM_EXAMPLES).ask()

    if any(example in GRAPHQL_EXAMPLES for example in examples):
        ask_api_secret(secrets, 'api_secret', 'Zeenea', 'Manage documentation')

    if any(example in SCIM_EXAMPLES for example in examples):
        ask_api_secret(secrets, 'scim_api_secret', 'Scim', 'Admin')

    if 'export_items_in_excel.py' in examples:
        questionary.print("* Options for export_items_in_excel.py", "italic")
        ask_file_path(settings, setting_name='excel_output_file', label="Excel output", default='output/datasets.xlsx')
        if page_size := questionary.text("Export page size:", default=str(settings.get('page_size', '')),
                                         validate=lambda s: s == '' or s.isdigit()).ask():
            settings['page_size'] = int(page_size)
        elif 'page_size' in settings:
            del settings['page_size']

    if 'update_items_from_excel.py' in examples:
        questionary.print("* Options for update_items_from_excel.py", "italic")
        ask_file_path(settings, 'excel_input_file', 'Excel input', 'input/datasets.xlsx')

    if 'send_field_lineage.py' in examples:
        questionary.print("* Options for send_field_lineage.py", "italic")
        ask_file_path(settings, 'lineage_input_file', 'Lineage input', 'input/lineage.json')

    if 'send_dqm_results.py' in examples:
        questionary.print("* Options for send_dqm_results.py", "italic")
        ask_file_path(settings, 'dqm_input_file', 'DQM input', 'input/dqm-results.csv')

    write_toml(settings, 'settings.toml')
    write_toml(secrets, '.secrets.toml')


def ask_file_path(settings: TOMLDocument, setting_name: str, label: str, default: str) -> None:
    if path := questionary.path(f"{label} file:", default=(settings.get(setting_name) or default)).ask():
        settings[setting_name] = path
    elif setting_name in settings:
        del settings[setting_name]


def ask_api_secret(secrets: TOMLDocument, p_name: str, p_label: str, scope: str) -> None:
    if secrets.get(p_name):
        should_ask_api_secret = questionary.confirm(
            f"The {p_label} API Secret is already defined, do you want to change it?",
            default=False).ask()
    else:
        should_ask_api_secret = True
    if api_secret := questionary.password(f"{p_label} API Secret (scope: {scope}):") \
        .skip_if(not should_ask_api_secret, default=secrets.get(p_name) or '').ask():
        secrets[p_name] = api_secret
    elif p_name in secrets:
        del secrets[p_name]


def read_toml(path: str) -> TOMLDocument:
    if os.path.exists(path):
        with open(path, 'r') as f:
            content = f.read()
        return tomlkit.parse(content)
    else:
        return tomlkit.document()


def write_toml(content: TOMLDocument, path: str) -> None:
    with open(path, 'w') as f:
        tomlkit.dump(content, f)


if __name__ == "__main__":
    main()
