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
> venv/Sccipts/activate
> py -m pip install -r requirements.txt
> py -m zeenea.setup
```

Unix/Linux commands
-------------------

```
$ python3 -m venv venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
$ python -m zeenea.setup
```

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
> venv/Sccipts/activate
> py export_items_in_excel.py
```

Unix/Linux commands
-------------------

```
$ venv/Sccipts/activate
$ python export_items_in_excel.py
$ ./export_items_in_excel.py
```

Script Examples
===============

export_items_in_excel.py
------------------------

Export some Zeenea items into an Excel file.
([Sources](export_items_in_excel.py))

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.
* pandas: Data frames manipulation.
* openpyxl: Excel writer.

update_items_from_excel.py
--------------------------

Update Zeenea items from an Excel file containing a property and a description.
([Sources](update_items_from_excel.py))

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.
* pandas: Data frames manipulation.
* openpyxl: Excel reader.

send_dqm_results.py
-------------------

Inject DQM results for Zeenea datasets from an external source.
([Sources](send_dqm_results.py))

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

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.

Modules
=======

The example files use common modules in the zeenea package for common technical code.
You can look at these modules, reuse them.
However, there are provided as examples and Zeenea provides no guaranty or support about them.

zeenea.config
-------------

This module use dynaconf to load the documentation from setting files and environment variables.

See the `read_configuration` method for an example.

If you want to use dynaconf for your own project, read their [documentation](https://www.dynaconf.com/).

zeenea.graphql
--------------

This module provides a small client to make easier to use the Zeenea GraphQL API.
It's mostly a wrapper around httpx.
Another valid solution would be to use a GraphQL client library.

The entry point of the module is the `ZeeneaGraphQLClient` class.

zeenea.tool
-----------

For now, it just provides `create_parent`: a function to create the parent folders of an output file if required.



License
=======
All assets and code are under the [CC0 LICENSE](./LICENSE) and in the public domain unless specified otherwise.
