# import-dcp.py — Data Intelligence Data Product Import Tool

CLI tool for uploading Zeenea Data Product YAML definitions via the synchronization API.

## Prerequisites

- Python 3.8+
- `requests` library (`pip install requests`)

### Getting an API Key

1. In the Zeenea UI, navigate to **Administration > API Keys**
2. Click **Create API Key**, give it a name and select the **Admin** scope
3. Click **Create API Key** again, then click **Copy and go back to list**
4. Paste the key into `config.json` as the `api_key` value
5. Remove the `X-API-SECRET: ` prefix from the pasted value if present — only the token itself should be stored

The key is passed as the `X-API-SECRET` HTTP header on every request.

## Configuration

Settings can be provided via a `config.json` file, CLI arguments, or a combination of both.
**CLI arguments always take precedence over the config file.**

### config.json

Copy `config.json.example` to `config.json` and fill in your values:

```json
{
  "zeenea_url": "https://your-tenant.zeenea.app",
  "api_key": "<your-api-key>",
  "path_to_yaml_fileset": "./yamls",
  "catalog_code": "default",
  "status_delay_in_milliseconds": 3000,
  "debug_mode": false
}
```

| Field | Required | Default | Description |
|---|---|---|---|
| `zeenea_url` | Yes | — | Base URL of your Zeenea tenant |
| `api_key` | Yes | — | API key from the administration panel |
| `path_to_yaml_fileset` | Yes | — | Path to a directory of YAML files or a pre-built `.zip` |
| `catalog_code` | No | `default` | Target catalog code |
| `status_delay_in_milliseconds` | No | `3000` | Polling interval while waiting for processing |
| `debug_mode` | No | `false` | Write detailed request/response logs to `logs/debug_*.log` |
| `ordered` | No | `false` | Import `DataContract` files first, then `DataProduct` files (two upload cycles) |
| `anonymise_api_key` | No | `true` | Mask the API key (`X-API-SECRET`) as `***REDACTED***` in debug logs so they can be shared safely |

### CLI Arguments

```
usage: import-dcp.py [-h] [--config CONFIG] [--zeenea-url URL] [--api-key KEY]
                     [--path PATH] [--catalog-code CODE]
                     [--status-delay MS] [--debug]

  --config CONFIG         Path to config JSON file (default: ./config.json)
  --zeenea-url URL        Zeenea tenant URL
  --api-key KEY           API key (sent as X-API-SECRET header)
  --path PATH             Directory or zip file containing YAML definitions
  --catalog-code CODE     Target catalog code (default: default)
  --status-delay MS       Milliseconds between status poll requests (default: 3000)
  --debug                 Enable debug logging
  --ordered               Import DataContract files first, then DataProduct files
  --anonymise-api-key     Mask the API key in debug logs (default: enabled)
  --no-anonymise-api-key  Log the real API key in debug logs (disable masking)
```

## Usage Examples

### Using config.json only

```bash
python import-dcp.py
```

### Using CLI arguments only

```bash
python import-dcp.py \
  --zeenea-url https://your-tenant.zeenea.app \
  --api-key eyJ0eXAiOiJKV1Qi... \
  --path ./yamls
```

### Overriding specific config.json values from the CLI

```bash
# Use a different catalog code for this run
python import-dcp.py --catalog-code staging

# Point to a different YAML directory
python import-dcp.py --path /tmp/my-data-products

# Use a custom config file
python import-dcp.py --config /path/to/other-config.json
```

### Uploading a pre-built zip file

```bash
python import-dcp.py --path ./my-data-products.zip
```

### Ordered import (contracts before products)

A data product output port links to a data contract via a `contractId` UUID, so the
contracts must exist before the products that reference them. With `--ordered`, the tool
splits the directory by `kind:` and runs two separate upload/process/poll cycles —
`DataContract` files first, then `DataProduct` files. If the contracts phase reports any
errors, the products phase is skipped.

```bash
python import-dcp.py --path ./yamls-sana-corrected --ordered --debug
```

### Enabling debug logging

```bash
python import-dcp.py --debug
# or set "debug_mode": true in config.json
```

## What the Tool Does

The import runs in four sequential steps:

1. **Request upload URL** — `POST /api/synchronization/data-product-uploads` to obtain a pre-signed S3 URL and an upload ID.
2. **Upload zip** — `PUT` the zip file to the S3 pre-signed URL.
3. **Trigger processing** — `POST /api/synchronization/data-product-uploads/{id}/process` with the target catalog code.
4. **Poll for completion** — `GET /api/synchronization/data-product-uploads/{id}` repeatedly until status is `Processed`.

If `path_to_yaml_fileset` points to a directory, the tool automatically zips all `*.yml` / `*.yaml` files it finds (recursively) and stores the archive in `uploads/upload_<timestamp>.zip`.

## Logs

| File | When created | Contents |
|---|---|---|
| `logs/error_<timestamp>.log` | Always | Errors that caused the run to fail |
| `logs/debug_<timestamp>.log` | Only when `debug_mode` is enabled | Full request/response details for every API call |

> **API key safety:** by default the API key is masked as `***REDACTED***` in debug logs (`anonymise_api_key: true`), so debug logs can be shared with support without exposing the secret. Set `anonymise_api_key` to `false`, or pass `--no-anonymise-api-key`, to log the real key.
