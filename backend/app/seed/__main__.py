"""CLI: ``python -m app.seed [--email E] [--password P] [--reset]``."""

import argparse
import logging

from app.database import SessionLocal
from app.logging_config import setup_logging
from app.seed.demo import DEFAULT_ADMIN_EMAIL, DEFAULT_PASSWORD, TEACHER_EMAIL, seed_demo

logger = logging.getLogger("app.seed")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed the EduGuardian demo school (GPS).")
    parser.add_argument("--email", default=DEFAULT_ADMIN_EMAIL, help="school_admin login email")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="password for demo users")
    parser.add_argument("--reset", action="store_true", help="delete the GPS school first")
    args = parser.parse_args(argv)

    setup_logging()
    with SessionLocal() as db:
        summary = seed_demo(db, email=args.email, password=args.password, reset=args.reset)
    if summary.created:
        logger.info("Demo school created (id=%s): %s", summary.school_id, summary.counts)
        logger.info("Login: %s / %s (teacher: %s)", args.email, "<password>", TEACHER_EMAIL)
        for path in summary.sample_files:
            logger.info("Wrote %s", path)
    else:
        logger.info("Demo school already present (id=%s); nothing to do", summary.school_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
