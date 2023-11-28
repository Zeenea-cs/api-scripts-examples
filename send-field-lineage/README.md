Description
===========

A simple script to illustrate how to inject Field to Field lineage from an external source (JSON file here).
This JSON file can be generated based on your transformation jobs, or provided by your data engineer as a description of their implementations

How to execute the script
=========================

1. Create a virtualenv

```python3 -m venv .venv```

2. Activate the virtualenv

```source .venv/bin/activate```

3. Install the dependencies

```pip install httpx dynaconf```

1. Edit your settings.toml and .secrets.toml files

2. Then, run the program

```python main.py```