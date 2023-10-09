Description
===========

A simple script to illustrate how to inject DQM resultats for Zeenea datasets from an external source (CSV file here)


How to execute the script
=========================

1. Create a virtualenv

```python3 -m venv .venv```

2. Activate the virtualenv

```source .venv/bin/activate```

3. Install the dependencies

```pip install pandas httpx dynaconf```

4. Edit your settings.toml and .secrets.toml files

5. Then, run the program

```python main.py```