"""
Generate fresh secrets for your .env file.

Run this ONCE when setting up a new environment:
    cd backend
    python -m scripts.generate_secrets
"""
import secrets
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.core.encryption import EncryptionService


def main() -> None:
    print()
    print("=" * 70)
    print("  GENERATED SECRETS — copy these into backend/.env")
    print("=" * 70)
    print()

    jwt_secret = secrets.token_urlsafe(64)
    print(f"JWT_SECRET_KEY={jwt_secret}")
    print()

    encryption_key = EncryptionService.generate_key()
    print(f"ENCRYPTION_KEY={encryption_key}")
    print()

    print("=" * 70)
    print("  ⚠️  NEVER commit these values to git.")
    print("  ⚠️  Losing ENCRYPTION_KEY will make encrypted credentials unrecoverable.")
    print("=" * 70)


if __name__ == "__main__":
    main()
