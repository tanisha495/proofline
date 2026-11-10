"""Command-line helper to create an organisation and user with a hashed password."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app.config import settings
from app.models.organisation import Organisation
from app.models.user import User
from app.core.security import hash_password


def get_db_session(database_url: str | None = None):
    url = database_url or os.environ.get("DATABASE_URL") or settings.database_url
    engine = create_engine(url, echo=False)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)()


def create_user(
    org_name: str,
    email: str,
    password: str,
    role: str = "creator",
    name: str | None = None,
    database_url: str | None = None,
) -> None:
    norm_email = email.strip().lower()
    norm_role = role.strip().lower()

    if norm_role not in ("creator", "reviewer", "admin"):
        raise ValueError(f"Invalid role '{role}'. Must be one of: creator, reviewer, admin")

    with get_db_session(database_url) as db:
        # Find or create organisation
        org = db.scalars(select(Organisation).where(Organisation.name == org_name.strip())).first()
        if not org:
            org = Organisation(name=org_name.strip())
            db.add(org)
            db.commit()
            db.refresh(org)
            print(f"[ProofLine] Created new organisation '{org.name}' ({org.id})")
        else:
            print(f"[ProofLine] Using existing organisation '{org.name}' ({org.id})")

        # Check if user already exists
        user = db.scalars(select(User).where(User.email == norm_email)).first()
        if not user:
            user = User(
                organisation_id=org.id,
                email=norm_email,
                password_hash=hash_password(password),
                full_name=name.strip() if name else None,
                role=norm_role,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"[ProofLine] Successfully created user '{user.email}' (ID: {user.id}, Role: {user.role})")
        else:
            user.organisation_id = org.id
            user.password_hash = hash_password(password)
            user.role = norm_role
            if name:
                user.full_name = name.strip()
            user.is_active = True
            db.commit()
            print(f"[ProofLine] Updated existing user '{user.email}' (ID: {user.id}, Role: {user.role})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a ProofLine user and organisation.")
    parser.add_argument("--org", required=True, help="Organisation name (created if not found)")
    parser.add_argument("--email", required=True, help="User email address")
    parser.add_argument("--password", required=True, help="User plain-text password")
    parser.add_argument("--role", default="creator", choices=["creator", "reviewer", "admin"], help="User role (default: creator)")
    parser.add_argument("--name", default=None, help="User full name (optional)")
    parser.add_argument("--database-url", default=None, help="Optional database URL override")

    args = parser.parse_args()
    create_user(
        org_name=args.org,
        email=args.email,
        password=args.password,
        role=args.role,
        name=args.name,
        database_url=args.database_url,
    )


if __name__ == "__main__":
    main()
