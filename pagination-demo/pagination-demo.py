import json
import re
from typing import Optional, List, Dict, Any

import os
import requests
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_output_alias(alias: str) -> None:
    """
    Raise ValueError if alias is not a valid JSON key / GraphQL identifier.

    Valid aliases contain only letters, digits, and underscores, and must
    not start with a digit.  Spaces, hyphens, and other special characters
    are rejected because they would produce invalid JSON field names.
    """
    if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', alias):
        raise ValueError(
            f"Connection output name '{alias}' is not a valid identifier. "
            "Use only letters, digits, and underscores, and do not start with a digit."
        )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(script_dir: str, config_file: str = "config.json") -> Dict[str, Any]:
    """
    Load and validate configuration from a JSON file located next to the script.

    Required keys : zeenea_url, api_key, datatypes_to_export
    Optional keys : connections (default []), pagination_size (default 20)

    Each entry in connections must be a two-element list [ref, output_name]
    where ref is the internal connection reference and output_name is the key
    used in the JSON export.  output_name must be a valid identifier (letters,
    digits, and underscores only; must not start with a digit).
    """
    try:
        config_path = os.path.join(script_dir, config_file)

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found at {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        required_keys = ['zeenea_url', 'api_key', 'datatypes_to_export']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required configuration key: {key}")

        zeenea_url = config['zeenea_url']
        if not zeenea_url.startswith('https://'):
            raise ValueError("zeenea_url must use HTTPS")
        if not zeenea_url.rstrip('/').endswith('.zeenea.app'):
            raise ValueError("zeenea_url must end with '.zeenea.app'")

        # Validate connections: each must be a [ref, output_name] pair.
        for i, conn in enumerate(config.get('connections', [])):
            if not isinstance(conn, list) or len(conn) != 2:
                raise ValueError(
                    f"connections[{i}] must be a [ref, output_name] pair, got: {conn!r}"
                )
            _, alias = conn
            validate_output_alias(alias)

        config.setdefault('connections', [])
        config.setdefault('pagination_size', 20)
        config.setdefault('debug_mode', False)

        return config

    except FileNotFoundError as e:
        print(f"x- Error: {e}")
        exit(1)
    except json.JSONDecodeError as e:
        print(f"x- Error: Invalid JSON in configuration file - {e}")
        exit(1)
    except ValueError as e:
        print(f"x- Error: {e}")
        exit(1)
    except Exception as e:
        print(f"x- Error loading configuration: {e}")
        exit(1)


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = load_config(SCRIPT_DIR)
ZEENEA_URL = CONFIG['zeenea_url']
API_KEY = CONFIG['api_key']
DATATYPES_TO_EXPORT: List[str] = CONFIG['datatypes_to_export']
CONNECTIONS: List[List[str]] = CONFIG['connections']
PAGINATION_SIZE: int = CONFIG['pagination_size']
DEBUG_MODE: bool = CONFIG['debug_mode']


# ---------------------------------------------------------------------------
# Error logger
# ---------------------------------------------------------------------------

class ErrorLogger:
    def __init__(self, script_dir: str):
        self.script_dir = script_dir
        self.has_errors = False
        self.errors: List[str] = []

    def log_error(self, message: str):
        self.has_errors = True
        self.errors.append(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

    def write_log_file(self) -> Optional[str]:
        if not self.has_errors:
            return None
        log_dir = os.path.join(self.script_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_path = os.path.join(log_dir, f"error_log_{current_datetime}.log")
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write("ERROR LOG - PAGINATION DEMO SCRIPT\n")
            f.write("=" * 70 + "\n\n")
            for error in self.errors:
                f.write(error + "\n")
        return log_file_path


# ---------------------------------------------------------------------------
# Debug logger
# ---------------------------------------------------------------------------

class DebugLogger:
    """
    Logger for capturing debug information including full API requests and responses.
    Enabled via debug_mode: true in config.json.
    """
    def __init__(self, script_dir: str, enabled: bool = False):
        self.script_dir = script_dir
        self.enabled = enabled
        self.log_file_path = None

        if self.enabled:
            log_dir = os.path.join(self.script_dir, "logs")
            os.makedirs(log_dir, exist_ok=True)
            current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file_path = os.path.join(log_dir, f"debug_log_{current_datetime}.log")
            with open(self.log_file_path, 'w', encoding='utf-8') as f:
                f.write("=" * 70 + "\n")
                f.write("DEBUG LOG - PAGINATION DEMO SCRIPT\n")
                f.write("=" * 70 + "\n\n")

    def log_api_call(self, endpoint: str, request_data: Dict[str, Any], response_data: Any, status_code: int):
        """Log a single API call with its full request and response."""
        if not self.enabled:
            return
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write("-" * 70 + "\n")
            f.write(f"[{timestamp}] API CALL\n")
            f.write("-" * 70 + "\n")
            f.write(f"Endpoint: {endpoint}\n")
            f.write(f"Status Code: {status_code}\n\n")
            f.write("Request Data:\n")
            f.write(json.dumps(request_data, indent=2, ensure_ascii=False) + "\n\n")
            f.write("Response Data:\n")
            f.write(json.dumps(response_data, indent=2, ensure_ascii=False) + "\n\n")

    def log_message(self, message: str):
        """Log a general debug message."""
        if not self.enabled:
            return
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")


# ---------------------------------------------------------------------------
# GraphQL query builders
# ---------------------------------------------------------------------------

def build_items_query(connections: List[List[str]]) -> str:
    """
    Build the main items query.

    linkedItems (members) and curators are always included.
    Every entry in `connections` is a [ref, output_name] pair.  output_name
    is used directly as the GraphQL field alias and the JSON export key.
    """
    extra_connection_fields = ""
    for conn_ref, alias in connections:
        extra_connection_fields += f"""
      {alias}: connection(ref: "{conn_ref}", after: "*") {{
        nodes {{
          name
          id
          key
        }}
        pageInfo {{
          startCursor
          hasNextPage
          hasPreviousPage
          endCursor
        }}
        totalCount
      }}
"""

    return f"""
query Items(
  $type: ItemType!,
  $first: Int,
  $after: String
) {{
  items(type: $type, first: $first, after: $after) {{
    nodes {{
      id
      type
      key
      name
      completion
      descriptionV2 {{ content {{ content }} }}
      lastCatalogMetadataUpdate
    {extra_connection_fields}
    }}

    pageInfo {{
      startCursor
      hasNextPage
      endCursor
    }}
    totalCount
  }}
}}
"""


def build_connection_page_query(conn_ref: str, alias: str, include_type: bool = False) -> str:
    """
    Build a query that fetches a single page of a connection for one item.

    Used when paginating beyond the first page of a sub-list.
    `alias` is the GraphQL field name (must match the alias used in the
    initial items query).  `include_type` adds the `type` field for the
    members/linkedItems connection.
    """
    node_fields = "id\n          key"
    if include_type:
        node_fields = "id\n          type\n          key"
    else:
        node_fields = "name\n          id\n          key"

    return f"""
query ItemConnectionPage($ref: ItemReference!, $first: Int, $after: String) {{
  item(ref: $ref) {{
    {alias}: connection(ref: "{conn_ref}", first: $first, after: $after) {{
      nodes {{
        {node_fields}
      }}
      pageInfo {{
        startCursor
        hasNextPage
        hasPreviousPage
        endCursor
      }}
      totalCount
    }}
  }}
}}
"""


# ---------------------------------------------------------------------------
# GraphQL execution
# ---------------------------------------------------------------------------

def execute_graphql(
    endpoint: str,
    headers: Dict[str, str],
    query: str,
    variables: Dict[str, Any],
    debug_logger: Optional['DebugLogger'] = None
) -> Dict[str, Any]:
    request_payload = {"query": query, "variables": variables}
    response = requests.post(endpoint, headers=headers, json=request_payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    if debug_logger:
        debug_logger.log_api_call(
            endpoint=endpoint,
            request_data=request_payload,
            response_data=data,
            status_code=response.status_code
        )
    return data


# ---------------------------------------------------------------------------
# Sub-list pagination
# ---------------------------------------------------------------------------

def paginate_connection(
    endpoint: str,
    headers: Dict[str, str],
    item_key: str,
    conn_ref: str,
    alias: str,
    initial_nodes: List[Dict],
    initial_page_info: Dict,
    pagination_size: int,
    include_type: bool,
    error_logger: ErrorLogger,
    debug_logger: Optional[DebugLogger] = None
) -> List[Dict]:
    """
    Starting from the data already fetched in the initial query, follow any
    remaining pages for a connection on a specific item.

    Returns the complete, deduplicated list of nodes across all pages.
    """
    all_nodes = list(initial_nodes)

    if not initial_page_info.get("hasNextPage"):
        return all_nodes

    query = build_connection_page_query(conn_ref, alias, include_type=include_type)
    cursor = initial_page_info["endCursor"]

    while cursor:
        variables = {"ref": item_key, "first": pagination_size, "after": cursor}
        try:
            data = execute_graphql(endpoint, headers, query, variables, debug_logger)

            if "errors" in data:
                error_logger.log_error(
                    f"GraphQL errors paginating '{conn_ref}' for item '{item_key}': {data['errors']}"
                )
                break

            connection_data = data["data"]["item"][alias]
            if connection_data is None:
                break

            all_nodes.extend(connection_data.get("nodes") or [])

            page_info = connection_data.get("pageInfo") or {}
            if page_info.get("hasNextPage"):
                cursor = page_info["endCursor"]
            else:
                cursor = None

        except requests.exceptions.RequestException as e:
            error_logger.log_error(
                f"Request error paginating '{conn_ref}' for item '{item_key}': {e}"
            )
            break

    return all_nodes


# ---------------------------------------------------------------------------
# Main fetch logic
# ---------------------------------------------------------------------------

def fetch_items_for_type(
    zeenea_url: str,
    api_key: str,
    item_type: str,
    connections: List[List[str]],
    pagination_size: int,
    error_logger: ErrorLogger,
    debug_logger: Optional[DebugLogger] = None
) -> List[Dict[str, Any]]:
    """
    Fetch every item of `item_type`, handling pagination at two levels:

    1. Top-level items list  (uses $after cursor, starts with "*")
    2. Each sub-list per item (linkedItems, curators, and every configured
       connection) — paginated individually if the first page reports
       hasNextPage = true.

    Returns a flat list of fully-resolved item dicts.
    """
    graphql_endpoint = f"{zeenea_url}/api/catalog/graphql"
    headers = {
        "Content-Type": "application/json",
        "X-API-SECRET": api_key
    }

    items_query = build_items_query(connections)

    # Build a lookup: alias -> (conn_ref, include_type)
    # linkedItems and curators are handled explicitly; the rest come from config.
    sub_connections: Dict[str, tuple] = {
        "linkedItems": ("members", True),
        "curators": ("curators", False),
    }
    for conn_ref, alias in connections:
        sub_connections[alias] = (conn_ref, False)

    all_items: List[Dict[str, Any]] = []
    cursor = "*"
    has_more = True
    page_num = 0

    print(f"  Fetching items of type: {item_type}")

    while has_more:
        page_num += 1
        variables = {
            "type": item_type,
            "first": pagination_size,
            "after": cursor
        }

        try:
            data = execute_graphql(graphql_endpoint, headers, items_query, variables, debug_logger)

            if "errors" in data:
                error_logger.log_error(
                    f"GraphQL errors fetching '{item_type}' (page {page_num}): {data['errors']}"
                )
                break

            items_connection = data["data"]["items"]
            nodes = items_connection["nodes"]
            total_count = items_connection.get("totalCount", "?")

            print(f"    Page {page_num}: {len(nodes)} items  (reported total: {total_count})")

            for item in nodes:
                complete_item = dict(item)

                # Paginate every sub-list connection
                for alias, (conn_ref, include_type) in sub_connections.items():
                    conn_data = item.get(alias) or {}
                    initial_nodes = conn_data.get("nodes") or []
                    initial_page_info = conn_data.get("pageInfo") or {}

                    all_nodes = paginate_connection(
                        graphql_endpoint, headers,
                        item["key"],
                        conn_ref, alias,
                        initial_nodes, initial_page_info,
                        pagination_size, include_type,
                        error_logger, debug_logger
                    )

                    # Replace the connection data with the fully-resolved version.
                    # pageInfo is omitted because the list is now complete.
                    complete_item[alias] = {
                        "nodes": all_nodes,
                        "totalCount": len(all_nodes)
                    }

                all_items.append(complete_item)

            # Advance the top-level cursor
            page_info = items_connection.get("pageInfo") or {}
            if page_info.get("hasNextPage"):
                cursor = page_info["endCursor"]
            else:
                has_more = False

        except requests.exceptions.RequestException as e:
            error_logger.log_error(
                f"Request error fetching '{item_type}' (page {page_num}): {e}"
            )
            break

    print(f"    v- Total items fetched: {len(all_items)}")
    return all_items


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    error_logger = ErrorLogger(SCRIPT_DIR)
    debug_logger = DebugLogger(SCRIPT_DIR, enabled=DEBUG_MODE)

    print("=" * 70)
    print("PAGINATION DEMO - MULTI-LEVEL GRAPHQL PAGINATION EXPORT")
    print("=" * 70 + "\n")

    if DEBUG_MODE:
        print(f"v- DEBUG MODE ENABLED\n")

    print(f"v- Zeenea URL       : {ZEENEA_URL}")
    print(f"v- Types to export  : {DATATYPES_TO_EXPORT}")
    conn_display = [(ref, alias) for ref, alias in CONNECTIONS] if CONNECTIONS else "(none)"
    print(f"v- Connections      : {conn_display}")
    print(f"v- Pagination size  : {PAGINATION_SIZE}")
    print()

    results: Dict[str, List] = {}
    total_items = 0

    for item_type in DATATYPES_TO_EXPORT:
        print(f"Processing type: {item_type}")
        print("-" * 70)

        items = fetch_items_for_type(
            ZEENEA_URL, API_KEY,
            item_type, CONNECTIONS, PAGINATION_SIZE,
            error_logger, debug_logger
        )

        results[item_type] = items
        total_items += len(items)
        print()

    # -----------------------------------------------------------------------
    # Write JSON export
    # -----------------------------------------------------------------------
    output = {
        "export_metadata": {
            "timestamp": datetime.now().isoformat(),
            "zeenea_url": ZEENEA_URL,
            "datatypes_exported": DATATYPES_TO_EXPORT,
            "connections_included": [[ref, alias] for ref, alias in CONNECTIONS],
            "pagination_size": PAGINATION_SIZE,
            "total_items": total_items
        },
        "results": results
    }

    export_dir = os.path.join(SCRIPT_DIR, "exports")
    os.makedirs(export_dir, exist_ok=True)

    current_datetime = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(export_dir, f"export_{current_datetime}.json")

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print("Export Result:")
    print("-" * 70)
    if error_logger.has_errors:
        print("  ! Warning: Some errors occurred during export")
    print(f"v- Exported {total_items} items to: {filepath}")
    print()

    if error_logger.has_errors:
        log_file = error_logger.write_log_file()
        print("Error Log:")
        print("-" * 70)
        print(f"x- Errors detected during execution")
        print(f"   Error log written to: {log_file}")
        print()

    if DEBUG_MODE and debug_logger.log_file_path:
        print("Debug Log:")
        print("-" * 70)
        print(f"v- Debug log written to: {debug_logger.log_file_path}")
        print()


if __name__ == "__main__":
    main()
