from authlib.integrations.starlette_client import OAuth

from core.config import config

oauth = OAuth()

# server_metadata_url lets Authlib auto-discover Google's authorization, token,
# and JWKS endpoints, which also enables ID-token signature verification.
oauth.register(
    name="google",
    client_id=config.GOOGLE_CLIENT_ID,
    client_secret=config.GOOGLE_CLIENT_SECRET,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)
