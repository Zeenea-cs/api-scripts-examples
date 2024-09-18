# This work is marked with CC0 1.0 Universal.
# To view a copy of this license, visit https://creativecommons.org/publicdomain/zero/1.0/

import re
import textwrap
from collections.abc import Iterable

import httpx


class GqlResponse:
    """
    Response of a graphql query.

    Properties
    ----------

    data: The data element from the graphql response.
    errors: The list of errors from the graphql response. If there are no errors, the value is None.
    extensions: The extensions from the graphql response.
    """

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
    """
    A GraphQL Error.

    Properties
    ----------

    message: the error message.
    code: the error code or None. It is an easy way to get the code from the extensions.
    path: the path of graphql element implied by the error.
    locations: a list of locations in the query.
    extensions: the list of extensions.
    """

    def __init__(self, json: dict):
        """
        Construct a new GqlError.
        :param json: The json from the graphql response.
        """
        self.message = json.get("message")
        self.path = json.get("path")
        if locations := json.get("locations"):
            self.locations = [GqlErrorLocation(location) for location in locations]
        else:
            self.locations = None
        self.extensions = json.get("extensions")
        self.code = self.extensions.get("code") if self.extensions else None

    def __str__(self):
        """Make a """
        locations = f"\n\tlocations: {', '.join(map(str, self.locations))}" if self.locations else ""
        other_ext = [f"{k}: {v}" for k, v in self.extensions.items() if not k == 'code'] if self.extensions else []
        extra = f"\n\textensions:\n{textwrap.indent("\n".join(other_ext), '\t\t')}" if other_ext else ""
        return f"{self.code or 'ERROR'}: {self.message}{locations}{extra}"

    def __repr__(self):
        return f"GqlError({self.message=})"


class GqlErrorList:
    """A list of errors. The main purpose of this object is to manage the string representation of the list."""

    def __init__(self, errors: Iterable[GqlError]):
        self.errors = list(errors)

    def __str__(self):
        return f"{len(self.errors)} errors:\n{textwrap.indent("\n".join(map(str, self.errors)), '\t')}"

    def __repr__(self):
        return f"GqlErrorList({len(self.errors)})[{repr(self.errors)}]"

    def __iter__(self):
        return iter(self.errors)


class GqlErrorLocation:
    """
    Location of a GraphQL error.

    Properties
    ----------

    line: number of the line where the error occurred.
    column: number of the column where the error occurred.
    """

    def __init__(self, json: dict):
        self.line = json.get("line")
        self.column = json.get("column")

    def __str__(self):
        return f"({self.line},{self.column})"

    def __repr__(self):
        return f"Location({self.line=},{self.column=})"


class GqlPage[A:Iterable]:
    """
    Represent a page of result.
    This class is provided to help managing pages in a paginated query.
    The usage of this page depends on the application details.

    Properties
    ----------

    content: Content of the page. The type of the content is generic.
    has_content: A convenient method to test if there is a content.
    total_items: Total number of items. Can be None is the total_number is not provided.
    next_cursor: The next page cursor. None if there is no more page.
    """

    def __init__(self, content: A, total_items: int | None, next_cursor: str | None):
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
    """
    The Zeenea GraphQL Client.

    It's just a wrapper around a httpx client.
    It makes easier the configuration and the error handling.

    You can use similar technics or prefer to use a standardized GraphQL client library which will provided better
    GraphQL management with schema support and client side query validation.

    :Example:
    >>> client = ZeeneaGraphQLClient(tenant='acme', api_secret='eyJ0...')
    >>> response = client.request('query my_query($ref: Ref, $count: Int) {...}', ref="item_ref", count=10)
    """

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
        """
        Send a request to the Zeenea GraphQL API.
        :param query: The request query. Can be either a query or mutation.
        :param variables: Variables to send with the query in the form of a list of key values.
        :return: A GqlResponse object.

        :Example:
        >>> client = ZeeneaGraphQLClient(tenant='acme', api_secret='eyJ0...')
        >>> response = client.request('query my_query($ref: Ref, $count: Int) {...}', ref="item_ref", count=10)
        """
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
    """
    Get the end cursor of a page or None if there is no more page.
    :param page_info: The page info JSON object from the GraphQL Response.
    :return: The end cursor or None.
    """
    return page_info['endCursor'] if page_info['hasNextPage'] else None
