"""Mint an HS256 dev JWT for the local Docker stack.

Usage: python scripts/dev_token.py [admin|resident|calendar_admin] [--days N]
"""
import argparse
import base64
import hashlib
import hmac
import json
import sys
import time
from pathlib import Path

# Keep in sync with docker/db/080_seed.sql and ADMIN_EMAILS in .env.docker.
DEV_USERS = {
    "admin": {"id": "11111111-1111-1111-1111-111111111111", "email": "admin@example.test", "name": "Local Admin"},
    "resident": {"id": "22222222-2222-2222-2222-222222222222", "email": "resident@example.test", "name": "Local Resident"},
    "calendar_admin": {
        "id": "33333333-3333-3333-3333-333333333333",
        "email": "calendar.admin@example.test",
        "name": "Local Calendar Admin",
    },
}

ENV_FILE = Path(__file__).resolve().parent.parent / ".env.docker"


def read_secret() -> str:
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("SUPABASE_JWT_SECRET="):
            return line.split("=", 1)[1].strip()
    sys.exit(f"SUPABASE_JWT_SECRET not found in {ENV_FILE}")


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def mint(role: str, days: int, secret: str) -> str:
    user = DEV_USERS[role]
    now = int(time.time())
    claims = {
        "sub": user["id"],
        "email": user["email"],
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + days * 86400,
    }
    signing_input = ".".join(
        b64url(json.dumps(part, separators=(",", ":")).encode()) for part in ({"alg": "HS256", "typ": "JWT"}, claims)
    )
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{b64url(signature)}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("role", nargs="?", default="admin", choices=sorted(DEV_USERS))
    parser.add_argument("--days", type=int, default=1)
    args = parser.parse_args()
    secret = read_secret()
    if not secret.startswith("local-dev-"):
        sys.exit("Refusing to sign: the secret in .env.docker does not start with 'local-dev-'.")
    print(mint(args.role, args.days, secret))


if __name__ == "__main__":
    main()
