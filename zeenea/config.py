import os
import sys

import questionary
import tomlkit
from dynaconf import Dynaconf, Validator, ValidationError
from tomlkit import TOMLDocument


def read_configuration(required_params: list[str]) -> Dynaconf:
    """
    Read and validate the configuration.

    :param required_params: list of required parameters.
    :return: The configuration.
    """
    try:
        # Create the configuration object from dynaconf library
        config = Dynaconf(
            # Set a prefix for environment variables
            envvar_prefix="ZEENEA",
            # Allow to load environment variables from .env files
            load_dotenv=True,
            # Set two settings file, one normal and one for the secrets
            settings_files=['settings.toml', '.secrets.toml'],
            # Set validators for required items
            validators=[Validator(required, must_exist=True) for required in required_params],
        )
        # Fast fail: the configuration as soon as it is read for early problem detection.
        config.validators.validate_all()
        return config

    except ValidationError as e:
        # Manage validation error by displaying a message in the standard error and exiting the programme with code 1.
        print(f"Configuration error: {e.message}", file=sys.stderr)
        sys.exit(1)





#
# The rest of the file is only to help preparing the settings.
# You don't need such a functionality for you application, this is only proposed to help you to define the settings.
# Call it with the command:
#      python -m zeenea.config
#
def main():
    settings = read_toml('settings.toml')
    secrets = read_toml('.secrets.toml')

    if tenant := questionary.text("Zeenea tenant:", default=settings.get('tenant', '')).ask():
        settings['tenant'] = tenant
    elif 'tenant' in settings:
        del settings['tenant']

    if secrets.get('api_secret'):
        should_ask_api_secret = questionary.confirm("An API Secret is already defined, do you want to change it?",
                                                    default=False).ask()
    else:
        should_ask_api_secret = True
    if api_secret := questionary.password("Zeenea API Secret:") \
        .skip_if(not should_ask_api_secret, default=secrets.get('api_secret') or '').ask():
        secrets['api_secret'] = api_secret
    elif 'api_secret' in settings:
        del settings['api_secret']

    examples = questionary.checkbox("Which example do you want to try ?", choices=[
        'export_items_in_excel.py',
        'update_items_from_excel.py',
        'send_field_lineage.py',
        'send_dqm_results.py'
    ]).ask()

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
