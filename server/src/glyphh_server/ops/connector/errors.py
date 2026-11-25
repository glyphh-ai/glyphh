"""A refusal from the connector's OAuth endpoints, in OAuth's own shape ({"error", "error_description"}: RFC 6749
section 5.2, RFC 7591 section 3.2.2, RFC 7009), since OAuth clients read that shape and not the API's."""


class OAuthError(Exception):
    def __init__(self, error: str, description: str, status: int = 400) -> None:
        super().__init__(description)
        self.error, self.description, self.status = error, description, status


class AuthorizeRefused(OAuthError):
    """A refusal of an authorization request whose client and redirect URI are known: it goes back to the redirect
    URI, never shown as a page."""


def invalid_client() -> OAuthError:
    return OAuthError("invalid_client", "The client is unknown or did not authenticate.", 401)


def invalid_grant(description: str) -> OAuthError:
    return OAuthError("invalid_grant", description)
