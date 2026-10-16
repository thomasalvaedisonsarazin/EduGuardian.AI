"""Password hashing with bcrypt (no passlib)."""

import logging

import bcrypt

logger = logging.getLogger(__name__)

# bcrypt only uses the first 72 bytes; truncate explicitly so long passwords do not raise.
_BCRYPT_MAX_BYTES = 72


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Return a salted bcrypt hash for ``password``."""
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Constant-time check of ``password`` against a stored bcrypt hash. Bad hashes -> False."""
    try:
        return bcrypt.checkpw(_encode(password), hashed.encode("utf-8"))
    except ValueError:
        logger.warning("Stored password hash is not a valid bcrypt hash")
        return False


# Pre-computed hash used to equalise timing when the user does not exist.
DUMMY_HASH = hash_password("timing-equaliser-not-a-real-password")
