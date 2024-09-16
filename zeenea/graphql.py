import re
import textwrap
from typing import Iterable

import httpx


class GqlResponse:
    def __init__(self, json_response: dict):
        self.data = json_response.get("data")
        errors = json_response.get("errors")
        self.errors = GqlErrorList(GqlError(error) for error in errors) if errors else None
        self.extensions = json_response.get("extensions")

    def __repr__(self):
        return f"GqlResponse({self.data=}, {self.errors=}, {self.extensions=})"

    def has_errors(self) -> bool:
        """Test if the response has errors."""
        return bool(self.errors)

    def has_error(self, code: str, unique: bool = False) -> bool:
        """
        Test if the response has an error with the given code.
        If the 'unique' parameter is True, there should be only one error.

        :param code: Code of the expected error.
        :param unique: Requires only one error.
        :return: True or False.
        """
        if self.errors and self.errors.errors:
            if unique:
                return len(self.errors.errors) == 1 and self.errors.errors[0].code == code
            else:
                return any(err.code == code for err in self.errors.errors)
        else:
            return False


class GqlError:
    def __init__(self, json: dict):
        self.message = json.get("message")
        self.path = json.get("path")
        locations = json.get("locations")
        if locations:
            self.locations = [GqlErrorLocation(location) for location in locations]
        self.extensions = json.get("extensions")
        self.code = self.extensions.get("code") if self.extensions else None

    def __str__(self):
        locations = f"\n\tlocations: {', '.join(map(str, self.locations))}" if self.locations else ""
        other_ext = [f"{k}: {v}" for k, v in self.extensions if not k == 'code'] if self.extensions else []
        extra = f"\n\textensions:\n{textwrap.indent("\n".join(other_ext), '\t')}" if other_ext else ""
        return f"{self.code or 'ERROR'}: {self.message}{locations}{extra}"

    def __repr__(self):
        return f"GqlError({self.message=})"


class GqlErrorList:
    def __init__(self, errors: Iterable[GqlError]):
        self.errors = list(errors)

    def __str__(self):
        return f"{len(self.errors)} errors:\n{textwrap.indent("\n".join(map(str, self.errors)), '\t')}"

    def __repr__(self):
        return f"GqlErrorList({len(self.errors)})[{repr(self.errors)}]"

    def __iter__(self):
        return iter(self.errors)


class GqlErrorLocation:
    def __init__(self, json: dict):
        self.line = json.get("line")
        self.column = json.get("column")

    def __str__(self):
        return f"({self.line},{self.column})"

    def __repr__(self):
        return f"Location({self.line=},{self.column=})"


class GqlPage[A]:
    """
    Represent a page of result.
    """

    def __init__(self, content: A, total_items: int, next_cursor: str):
        self.content = content
        self.total_items = total_items
        self.next_cursor = next_cursor

    @property
    def has_content(self):
        """Return true if there are any items in this page."""
        return bool(self.content)

    def __bool__(self):
        return self.has_content


class ZeeneaGraphQLClient:
    def __init__(self, tenant: str, api_secret: str):
        if not re.match('^https?://', tenant):
            url = f"https://{tenant}.zeenea.app/api/catalog/graphql"
        else:
            url = f"{tenant}/api/catalog/graphql"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "X-API-SECRET": api_secret
        }
        self._client = httpx.Client(base_url=url, headers=headers)

    def request(self, query: str, **variables) -> GqlResponse:
        payload = {
            "query": query,
            "variables": variables,
        }
        response = self._client.post("", json=payload)
        if response.status_code == 200:
            return GqlResponse(response.json())
        else:
            raise httpx.RequestError(f"{response.status_code=}, {response.json()=}")


def end_cursor(page_info: dict) -> str | None:
    return page_info['endCursor'] if page_info['hasNextPage'] else None
