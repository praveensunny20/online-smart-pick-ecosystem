"""Utility helpers for generating slugs and other text manipulation."""
import re
import secrets
import string


def slugify(text: str, max_length: int = 80) -> str:
    """
    Convert text to a URL-safe slug.

    Example:
        "Acme Corp, Inc." -> "acme-corp-inc"
        "Sarah's Boutique & Store" -> "sarahs-boutique-store"
    """
    if not text:
        return ""

    # Lowercase
    slug = text.lower()
    # Replace any non-alphanumeric character with a hyphen
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Strip leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug


def unique_slug(base: str, suffix_length: int = 6) -> str:
    """
    Create a slug with a random suffix to avoid collisions.
    Useful for client slugs (same agency could have two clients with the same name).
    """
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(suffix_length))
    base_slug = slugify(base)
    if not base_slug:
        base_slug = "item"
    return f"{base_slug}-{suffix}"


def random_password(length: int = 16) -> str:
    """
    Generate a secure random password that meets strength requirements
    (upper + lower + digit + special).
    """
    if length < 12:
        length = 12
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.isupper() for c in pwd)
            and any(c.islower() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%&*" for c in pwd)
        ):
            return pwd
