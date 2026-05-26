"""
import-dcp.py - CLI tool for uploading Zeenea Data Product YAML definitions via the API.
"""

import argparse
import json
import logging
import os
import sys
import time
import warnings
import zipfile
from datetime import datetime
from pathlib import Path

# Suppress urllib3 v2 warning about LibreSSL on macOS
warnings.filterwarnings("ignore", message=".*NotOpenSSLWarning.*")
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

import requests
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Logging helpers
# ---------------------------------------------------------------------------

def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def setup_logging(debug_mode: bool) -> Tuple[logging.Logger, logging.Logger]:
    """Return (debug_logger, error_logger). Files are always datetime-stamped."""
    ts = _timestamp()
    log_dir = _SCRIPT_DIR / "logs"
    log_dir.mkdir(exist_ok=True)

    # Error logger – always active
    error_log_path = log_dir / f"error_{ts}.log"
    error_logger = logging.getLogger("error")
    error_logger.setLevel(logging.ERROR)
    error_handler = logging.FileHandler(error_log_path, encoding="utf-8")
    error_handler.setFormatter(logging.Formatter("%(asctime)s [ERROR] %(message)s"))
    error_logger.addHandler(error_handler)

    # Debug logger – only active when debug_mode is True
    debug_logger = logging.getLogger("debug")
    if debug_mode:
        debug_log_path = log_dir / f"debug_{ts}.log"
        debug_logger.setLevel(logging.DEBUG)
        debug_handler = logging.FileHandler(debug_log_path, encoding="utf-8")
        debug_handler.setFormatter(logging.Formatter("%(asctime)s [DEBUG] %(message)s"))
        debug_logger.addHandler(debug_handler)
        print(f"Debug logging enabled: {debug_log_path}")

    return debug_logger, error_logger


def log_request(debug_logger: logging.Logger, method: str, url: str,
                headers: Optional[dict], body: Optional[str],
                response: Optional[requests.Response]) -> None:
    if not debug_logger.handlers:
        return
    debug_logger.debug(f">>> {method} {url}")
    if headers:
        debug_logger.debug(f"    Request headers: {json.dumps(headers, indent=2)}")
    if body:
        debug_logger.debug(f"    Request body: {body}")
    if response is not None:
        debug_logger.debug(f"    Response status: {response.status_code}")
        try:
            debug_logger.debug(f"    Response body: {response.text}")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

DEFAULTS = {
    "debug_mode": False,
    "catalog_code": "default",
    "status_delay_in_milliseconds": 3000,
}

REQUIRED = ("zeenea_url", "api_key", "path_to_yaml_fileset")


def load_config(config_path: str, explicit: bool = False) -> dict:
    config = dict(DEFAULTS)
    try:
        with open(config_path, encoding="utf-8") as f:
            file_cfg = json.load(f)
        config.update(file_cfg)
    except FileNotFoundError:
        if explicit:
            print(f"ERROR: Config file not found: {config_path}", file=sys.stderr)
            sys.exit(1)
        # Default config is optional — required values can come from CLI
    except json.JSONDecodeError as exc:
        print(f"ERROR: Could not parse {config_path}: {exc}", file=sys.stderr)
        sys.exit(1)
    return config


def apply_cli_overrides(config: dict, args: argparse.Namespace) -> dict:
    mapping = {
        "zeenea_url": "zeenea_url",
        "api_key": "api_key",
        "path_to_yaml_fileset": "path_to_yaml_fileset",
        "debug_mode": "debug_mode",
        "catalog_code": "catalog_code",
        "status_delay_in_milliseconds": "status_delay_in_milliseconds",
    }
    for arg_name, cfg_key in mapping.items():
        val = getattr(args, arg_name, None)
        if val is not None:
            config[cfg_key] = val
    return config


def validate_config(config: dict) -> None:
    missing = [k for k in REQUIRED if not config.get(k)]
    if missing:
        print(f"ERROR: Missing required settings: {', '.join(missing)}", file=sys.stderr)
        print("Provide them in config.json or via CLI arguments.", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# ZIP preparation
# ---------------------------------------------------------------------------

def prepare_zip(path_str: str) -> Path:
    """
    If path_str is a zip file, return it directly.
    If path_str is a directory, zip all *.yml / *.yaml files and return the zip path.
    """
    path = Path(path_str)

    if path.is_file():
        if path.suffix.lower() == ".zip":
            return path
        print(f"ERROR: {path} is not a zip file or directory.", file=sys.stderr)
        sys.exit(1)

    if path.is_dir():
        yaml_files = list(path.rglob("*.yml")) + list(path.rglob("*.yaml"))
        if not yaml_files:
            print(f"ERROR: No YAML files found in {path}", file=sys.stderr)
            sys.exit(1)

        uploads_dir = _SCRIPT_DIR / "uploads"
        uploads_dir.mkdir(exist_ok=True)
        zip_path = uploads_dir / f"upload_{_timestamp()}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for yaml_file in yaml_files:
                # Store relative to the source directory
                arcname = yaml_file.relative_to(path)
                zf.write(yaml_file, arcname)
        print(f"Created zip archive: {zip_path} ({len(yaml_files)} YAML file(s))")
        return zip_path

    print(f"ERROR: {path} does not exist or is not a file/directory.", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------

def get_upload_url(zeenea_url: str, api_key: str,
                   debug_logger: logging.Logger,
                   error_logger: logging.Logger) -> dict:
    """Step 1: POST to get a pre-signed S3 upload URL."""
    url = f"{zeenea_url.rstrip('/')}/api/synchronization/data-product-uploads"
    headers = {"X-API-SECRET": api_key}

    try:
        resp = requests.post(url, headers=headers)
        log_request(debug_logger, "POST", url, headers, None, resp)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        msg = f"Step 1 failed – could not get upload URL: {exc}"
        error_logger.error(msg)
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)


def upload_zip(upload_params: dict, zip_path: Path,
               max_bytes: int,
               debug_logger: logging.Logger,
               error_logger: logging.Logger) -> None:
    """Step 2: PUT the zip file to the pre-signed S3 URL."""
    file_size = zip_path.stat().st_size
    if file_size > max_bytes:
        msg = (f"Zip file size ({file_size} bytes) exceeds maximum "
               f"allowed size ({max_bytes} bytes).")
        error_logger.error(msg)
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)

    url = upload_params["url"]
    headers = dict(upload_params.get("headers", {}))

    try:
        with open(zip_path, "rb") as f:
            resp = requests.put(url, headers=headers, data=f)
        log_request(debug_logger, "PUT", url, headers, f"<zip file: {zip_path}>", resp)
        resp.raise_for_status()
        print(f"Upload successful (HTTP {resp.status_code})")
    except requests.RequestException as exc:
        msg = f"Step 2 failed – upload error: {exc}"
        error_logger.error(msg)
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)


def trigger_processing(zeenea_url: str, api_key: str, upload_id: str,
                       catalog_code: str,
                       debug_logger: logging.Logger,
                       error_logger: logging.Logger) -> None:
    """Step 3: POST to trigger file processing."""
    url = (f"{zeenea_url.rstrip('/')}/api/synchronization/"
           f"data-product-uploads/{upload_id}/process")
    headers = {
        "X-API-SECRET": api_key,
        "Content-Type": "application/json",
    }
    body = {"catalogCode": catalog_code}

    try:
        resp = requests.post(url, headers=headers, json=body)
        log_request(debug_logger, "POST", url, headers, json.dumps(body), resp)
        resp.raise_for_status()
        print(f"Processing triggered (HTTP {resp.status_code})")
    except requests.RequestException as exc:
        msg = f"Step 3 failed – could not trigger processing: {exc}"
        error_logger.error(msg)
        print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit(1)


def poll_status(zeenea_url: str, api_key: str, upload_id: str,
                delay_ms: int,
                debug_logger: logging.Logger,
                error_logger: logging.Logger) -> dict:
    """Step 4: Poll GET endpoint until status is 'Processed'."""
    url = (f"{zeenea_url.rstrip('/')}/api/synchronization/"
           f"data-product-uploads/{upload_id}")
    headers = {"X-API-SECRET": api_key}
    delay_s = delay_ms / 1000.0

    while True:
        try:
            resp = requests.get(url, headers=headers)
            log_request(debug_logger, "GET", url, headers, None, resp)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            msg = f"Step 4 failed – status check error: {exc}"
            error_logger.error(msg)
            print(f"ERROR: {msg}", file=sys.stderr)
            sys.exit(1)

        status = data.get("status", "")
        result = data.get("result") or {}
        processed = result.get("processed", 0)
        upserted = result.get("upserted", 0)
        errors = result.get("errors", [])

        print(f"Status: {status} | processed={processed} upserted={upserted} "
              f"errors={len(errors)}")

        if status == "Processed":
            return data

        time.sleep(delay_s)


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

_SCRIPT_DIR = Path(__file__).parent


def build_arg_parser() -> argparse.ArgumentParser:
    default_config = str(_SCRIPT_DIR / "config.json")
    parser = argparse.ArgumentParser(
        description="Upload Zeenea Data Product YAML definitions via the sync API.",
    )
    parser.add_argument("--config", default=None,
                        help=f"Path to config JSON file (default: {default_config})")
    parser.add_argument("--zeenea-url", dest="zeenea_url",
                        help="Zeenea tenant URL")
    parser.add_argument("--api-key", dest="api_key",
                        help="API key (sent as X-API-SECRET header)")
    parser.add_argument("--path", dest="path_to_yaml_fileset",
                        help="Path to directory or zip file containing YAML definitions")
    parser.add_argument("--debug", dest="debug_mode", action="store_true", default=None,
                        help="Enable debug logging")
    parser.add_argument("--catalog-code", dest="catalog_code",
                        help="Target catalog code (default: default)")
    parser.add_argument("--status-delay", dest="status_delay_in_milliseconds",
                        type=int,
                        help="Milliseconds between status poll requests (default: 3000)")
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    # Load config from file, then apply CLI overrides
    explicit_config = args.config is not None
    config_path = args.config if explicit_config else str(_SCRIPT_DIR / "config.json")
    config = load_config(config_path, explicit=explicit_config)
    config = apply_cli_overrides(config, args)
    validate_config(config)

    zeenea_url: str = config["zeenea_url"]
    api_key: str = config["api_key"]
    path_str: str = config["path_to_yaml_fileset"]
    debug_mode: bool = bool(config["debug_mode"])
    catalog_code: str = config["catalog_code"]
    status_delay: int = int(config["status_delay_in_milliseconds"])

    debug_logger, error_logger = setup_logging(debug_mode)

    if debug_logger.handlers:
        debug_logger.debug(f"Config: {json.dumps({k: v for k, v in config.items() if k != 'api_key'}, indent=2)}")

    # Prepare zip
    zip_path = prepare_zip(path_str)

    # Step 1: Get upload URL
    print("\n[1/4] Requesting upload URL...")
    upload_info = get_upload_url(zeenea_url, api_key, debug_logger, error_logger)
    upload_id: str = upload_info["id"]
    upload_params: dict = upload_info["uploadParameters"]
    max_bytes: int = upload_info.get("maximumFileSizeInBytes", 52428800)
    print(f"      Upload ID: {upload_id}")

    # Step 2: Upload zip
    print("\n[2/4] Uploading zip file...")
    upload_zip(upload_params, zip_path, max_bytes, debug_logger, error_logger)

    # Step 3: Trigger processing
    print("\n[3/4] Triggering processing...")
    trigger_processing(zeenea_url, api_key, upload_id, catalog_code,
                       debug_logger, error_logger)

    # Step 4: Poll for completion
    print(f"\n[4/4] Polling status (every {status_delay}ms)...")
    final = poll_status(zeenea_url, api_key, upload_id, status_delay,
                        debug_logger, error_logger)

    result = final.get("result", {})
    errors = result.get("errors", [])

    print("\n--- Done ---")
    print(f"  Processed : {result.get('processed', 0)}")
    print(f"  Upserted  : {result.get('upserted', 0)}")
    print(f"  Errors    : {len(errors)}")

    if errors:
        for err in errors:
            error_logger.error(f"Processing error: {err}")
            print(f"  ! {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
