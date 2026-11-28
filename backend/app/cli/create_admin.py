"""Trusted server-side CLI to provision or promote an administrator account."""
import argparse
import getpass
import sys
import uuid

from backend.app.database import Base, SessionLocal, engine
from backend.app.models import User
from backend.app.services.auth import hash_password, normalize_email, validate_email_format, validate_password_strength


def provision_admin(email: str, name: str, password: str) -> User:
    Base.metadata.create_all(bind=engine)
    norm_email = validate_email_format(email)
    validate_password_strength(password)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == norm_email).first()
        if user:
            user.role = "admin"
            user.username = name.strip() or user.username
            user.password_hash = hash_password(password)
            db.commit()
            db.refresh(user)
            return user

        user = User(
            id=f"adm_{uuid.uuid4().hex[:12]}",
            username=name.strip() or "Raahi Admin",
            email=norm_email,
            password_hash=hash_password(password),
            role="admin",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision a Raahi administrator account.")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--name", default="Raahi Admin", help="Admin display name")
    parser.add_argument("--password", help="Admin password (if omitted, prompts securely)")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Admin password (min 8 chars, letter + number): ")
    if not args.password:
        confirm = getpass.getpass("Confirm admin password: ")
        if password != confirm:
            print("Error: Passwords do not match.", file=sys.stderr)
            return 1

    user = provision_admin(args.email, args.name, password)
    print(f"Provisioned admin account: id={user.id}, email={normalize_email(user.email or '')}, role={user.role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

