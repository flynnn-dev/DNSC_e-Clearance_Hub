"""HMAC-SHA256 check for a signed import manifest.

The signed bytes are the manifest JSON with the signature field removed.
Object keys are sorted, and the separators are a comma and a colon with no
spaces. The key is HMAC_SECRET. STARTER_HMAC_KEY is used when HMAC_SECRET is
empty, which is the name on the starter-kit checker.
"""

import hashlib
import hmac
import json
import os


def signing_key() -> str:
    secret = os.environ.get("HMAC_SECRET", "").strip()
    if secret:
        return secret
    return os.environ.get("STARTER_HMAC_KEY", "").strip()


def signature_problem(manifest: dict, key: str | None = None) -> str | None:
    secret = signing_key() if key is None else key.strip()
    if not secret:
        return "HMAC_SECRET is missing, so the manifest signature was not checked."
    signature = manifest.get("signature")
    if not isinstance(signature, str):
        return "The manifest signature is invalid."
    body = json.dumps(
        {name: value for name, value in manifest.items() if name != "signature"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    if len(signature) != len(expected) or not hmac.compare_digest(expected, signature):
        return "The manifest signature is invalid."
    return None
