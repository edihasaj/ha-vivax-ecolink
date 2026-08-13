"""Public application identity used by the official VIVAX EcoLink client."""

from __future__ import annotations

from .models import ApplicationCredentials

# These values identify the VIVAX EcoLink application. They are shared by every
# installation and are not a Home Assistant user's account credentials.
APPLICATION = ApplicationCredentials(
    app_secret="PROD_nW6aJ7eY8bI6dU4g",
    client_id="4fcb8a78d03e0865a5802e5496d80d2a",
    client_secret="06f258887e2aa3709a61fd509ebaf55e",
    encryption_key="4dbc9ff6c15944d78eebb581c2b23de3",
)
