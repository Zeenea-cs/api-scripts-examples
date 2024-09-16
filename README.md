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
6. Edit settings.toml and .secrets.toml files.
7. Your environment is ready you can run the examples.

Scripts have been tested with Python 3.12.

Windows commands
----------------

```
> py -m venv venv
> venv/Sccipts/activate
> py -m pip install -r requirements.txt
```

Unix/Linux commands
-------------------

```
$ python3 -m venv venv
$ source .venv/bin/activate
$ pip install -r requirements.txt
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

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.
* pandas: Data frames manipulation.
* openpyxl: Excel writer.

update_items_from_excel.py
--------------------------

Update Zeenea items from an Excel file containing a property and a description.

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.
* pandas: Data frames manipulation.
* openpyxl: Excel reader.

send_dqm_results.py
-------------------

Inject DQM results for Zeenea datasets from an external source.

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.

send_field_lineage.py
---------------------

Inject Field to Field lineage from an external source.

The source here is a sample JSON file _input/lineage.json_.
In real implementation you will fetch the information directly from the source system using API or
any intermediate file format depending on your context.

### Dependencies

* dynaconf: Configuration.
* httpx: HTTP request.

License
=======
All assets and code are under the [CC0 LICENSE](./LICENSE) and in the public domain unless specified
otherwise.
