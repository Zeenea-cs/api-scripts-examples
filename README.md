API Scripts Examples
====================

This repository contains some simple Python scripts to showcase how to use our GraphQL API.

Read our Zeenea GraphQL Catalog API [documentation](https://docs.zeenea.com/) for details.

List of the scripts:

* [export_items_in_excel.py](#export_items_in_excelpy): Export some Zeenea items into an Excel file.
* [update_items_from_excel.py](#update_items_from_excelpy): Update Zeenea items from an Excel file
  containing a property and a description.
* [send_dqm_results.py](#send_dqm_resultspy): Inject DQM results for Zeenea datasets from an
  external source.
* [send_field_lineage.py](#send_field_lineagepy): Inject Field to Field lineage from an external
  source.
* [user.py](#userpy): A command line tool to create, modify and delete users.
* [migrate_contact.py](migrate_contactpy): A command line tool to copy contact-items links of a contact to another one.

Setup
=====

To set up the project:

1. Install a Python environment if needed.
2. Clone this repository.
3. Create a virtual environment with venv.
4. Activate the new virtual environment.
5. Install the dependencies listed in _requirements.txt_.
6. Prepare the settings. You have two options to do this:
    1. Edit settings.toml and .secrets.toml files.
    2. Use the `zeenea.setup` wizard to guide you in the settings.
7. Your environment is ready you can run the examples.

Scripts have been tested with Python 3.12.

Windows commands
----------------

```
> py -m venv venv
> venv/Scripts/activate
> py -m pip install -r requirements.txt
> py -m zeenea.setup
```

Unix/Linux commands
-------------------

```
$ python -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
$ python -m zeenea.setup
```

NOTE: you may have to use ```python3```instead of ```python``` if using MacOS

Prepare settings
----------------

In order to make easier to prepare the settings, we provided you with a small command line tool.
The wizard can be used several times without losing the existing settings.

You can call it with a simple command:

### On Windows

```
❯ py -m zeenea.setup
```

### On Linux

```
$ python -m zeenea.setup
```

### Example

```
$ python -m zeenea.setup
? Zeenea tenant: acme
? Zeenea API Secret: **************************************
? Which example do you want to try ? (Use arrow keys to move, <space> to select, <a> to toggle, <i> to invert)
 » ● export_items_in_excel.py
   ● update_items_from_excel.py
   ● send_field_lineage.py
   ● send_dqm_results.py
* Options for export_items_in_excel.py
? Excel output file: output/datasets.xlsx
? Export page size:
* Options for update_items_from_excel.py
? Excel input file: input/datasets.xlsx
* Options for send_field_lineage.py
? Lineage input file: input/lineage.json
* Options for send_dqm_results.py
? DQM input file: input/dqm-results.csv
```

Run a script
============

In order to run a script

1. Set up the environment, if already set, don't forget to activate the virtual environment.
2. Update settings files.
3. Run the python interpreter or directly execute the command (linux/unix).

Windows commands
----------------

```
> venv/Scripts/activate
> py export_items_in_excel.py
```

Unix/Linux commands
-------------------

```
$ source .venv/bin/activate
$ python export_items_in_excel.py
$ ./export_items_in_excel.py
```

Script Examples
===============

export_items_in_excel.py
------------------------

Export some Zeenea items into an Excel file.
([Sources](export_items_in_excel.py))

### Configuration

In _settings.toml_:
* tenant: The tenant name. Example: "acme". For very specific use cases, a URL prefix can be provided.
* excel_output_file: The path to the Excel output file. The default value is "output/datasets.xlsx".
* page_size: The size of a page. Default to 20.

In _.secrets.toml_:
* api_secret: A valid Zeenea API Secret with the scope "Manage documentation".

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.
* pandas: Data frames manipulation.
* openpyxl: Excel writer.

update_items_from_excel.py
--------------------------

Update Zeenea items from an Excel file containing a property and a description.
([Sources](update_items_from_excel.py))

### Configuration

In _settings.toml_:
* tenant: The tenant name. Example: "acme". For very specific use cases, a URL prefix can be provided.
* excel_input_file: The path to the Excel input file. The default value is "input/datasets.xlsx".

In _.secrets.toml_:
* api_secret: A valid Zeenea API Secret with the scope "Manage documentation".

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.
* pandas: Data frames manipulation.
* openpyxl: Excel reader.

send_dqm_results.py
-------------------

Inject DQM results for Zeenea datasets from an external source.
([Sources](send_dqm_results.py))

### Configuration

In _settings.toml_:
* tenant: The tenant name. Example: "acme". For very specific use cases, a URL prefix can be provided.
* dqm_input_file: The path to the CSV input file. The default value is "input/dqm-results.csv".

In _.secrets.toml_:
* api_secret: A valid Zeenea API Secret with the scope "Manage documentation".

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.

send_field_lineage.py
---------------------

Inject Field to Field lineage from an external source.
([Sources](send_field_lineage.py))

The source here is a sample JSON file _input/lineage.json_.
In real implementation you will fetch the information directly from the source system using API or
any intermediate file format depending on your context.

### Configuration

In _settings.toml_:
* tenant: The tenant name. Example: "acme". For very specific use cases, a URL prefix can be provided.
* lineage_input_file: The path to the JSON input file. The default value is "input/lineage.json".

In _.secrets.toml_:
* api_secret: A valid Zeenea API Secret with the scope "Manage documentation".

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.

user.py
-------

This is a command line tool to create, modify or delete users.

### Configuration

In _settings.toml_:
* tenant: The tenant name. Example: "acme". For very specific use cases, a URL prefix can be provided.

In _.secrets.toml_:
* scim_api_secret: A valid Zeenea API Secret with the scope "Admin".

You can get the command line arguments documentation with the command line itself with the option `--help`. 

For create command, options are:
* `-e`, `--email`: The user email address.
* `--given-name`: The user given name.
* `--family-name`: The user family name.
* `-g`, `--group`: A group to add the user to.
Examples:
```
> py user.py --help
usage: user.py [-h] {create,delete,modify} ...

CLI to manage users with scim as an integration example

options:
  -h, --help            show this help message and exit

user commands:
  {create,delete,modify}
    create              Create a new user
    delete              Delete an existing user
    modify              Modify a user


> py .\user.py create --help            
usage: user.py create [-h] -e EMAIL [--given-name GIVEN_NAME] [--family-name FAMILY_NAME] [-g GROUP]

options:
  -h, --help            show this help message and exit
  -e EMAIL, --email EMAIL
                        Email address
  --given-name GIVEN_NAME
                        Given name
  --family-name FAMILY_NAME
                        Family name
  -g GROUP, --group GROUP
                        Group to add the user to
```

### Dependencies

* argparse: a command line argument parser.
* scim2_client: A Scim 2.0 client library.
* dynaconf: Configuration.
* httpx: HTTP request.

migrate_contact.py
------------------

This is a command line tool to copy the contact-item links of a contact to another one.
This can help the transmission of a responsibility from a contact to another one.
This can happen when a person changes or a new user must be created for a person whose email changes.

### Configuration

In _settings.toml_:
* tenant: The tenant name. Example: "acme". For very specific use cases, a URL prefix can be provided.

In _.secrets.toml_:
* scim_api_secret: A valid Zeenea API Secret with the scope "Admin".

Command line options:
* `--from`: Email address of the contact to copy from.
* `--to`: Email address of the contact to copy to.

You can get the command line arguments documentation with the command line itself with the option `--help`.

### Usage Example
```
> py user.py create --email john.doe@actian.com --given-name John --family-name Doe
> py migrate_contact.py --from jdoe@zeenea.com --to john.doe@actian.com
> py user.py delete --email john.doe@actian.com
```

### Dependencies

* argparse: a command line argument parser.
* dynaconf: Configuration.
* httpx: HTTP request.


Modules
=======

The example files use common modules in the zeenea package for common technical code.
You can look at these modules, reuse them.
However, there are provided as examples and Zeenea provides no guaranty or support about them.

zeenea.graphql
--------------

This module provides a small client to make easier to use the Zeenea GraphQL API.
It's mostly a wrapper around httpx.
Another valid solution would be to use a GraphQL client library.

The entry point of the module is the `ZeeneaGraphQLClient` class.

zeenea.scim
-----------

This module provide a small scim 2.0 client restricted to recommended Zeenea patterns primitives.
It is based on scim2_client library and complete some unimplemented method.

The entry point of the module is the `ZeeneaScimClient` class.

zeenea.config
-------------

This module use dynaconf to load the documentation from setting files and environment variables.

See the `read_configuration` method for an example.

If you want to use dynaconf for your own project, read their [documentation](https://www.dynaconf.com/).

zeenea.tool
-----------

For now, it just provides `create_parent`: a function to create the parent folders of an output file if required.

License
=======
All assets and code are under the [CC0 LICENSE](./LICENSE) and in the public domain unless specified otherwise.
