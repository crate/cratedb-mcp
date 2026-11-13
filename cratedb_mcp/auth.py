import hmac
import typing as t

from fastmcp.server.auth import AccessToken, TokenVerifier


class BearerTokenVerifier(TokenVerifier):
    """
    Accept HTTP requests that carry the configured bearer token.
    """

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token.encode()

    async def verify_token(self, token: str) -> t.Optional[AccessToken]:
        if not hmac.compare_digest(token.encode(), self._token):
            return None
        return AccessToken(token=token, client_id="cratedb-mcp", scopes=[])
