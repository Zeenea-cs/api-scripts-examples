import sys

from dynaconf import Dynaconf, Validator, ValidationError


def read_configuration(required_params: list[str]) -> Dynaconf:
    """
    Read and validate the configuration.
    :param required_params: list of required parameters.
    :return: The configuration.
    """
    try:
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
        print(f"Configuration error: {e.message}", file=sys.stderr)
        sys.exit(1)
