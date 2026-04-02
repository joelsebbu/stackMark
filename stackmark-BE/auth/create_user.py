import argparse
import sys

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from auth.security import hash_password
from db.models.user import User
from db.session import SessionLocal


def main():
    parser = argparse.ArgumentParser(description="Create a StackMark user.")
    parser.add_argument("--u", required=True, help="Username")
    parser.add_argument("--p", required=True, help="Password")
    args = parser.parse_args()

    hashed = hash_password(args.p)

    with SessionLocal() as session:
        existing = session.execute(
            select(User).where(User.username == args.u)
        ).scalar_one_or_none()

        if existing:
            print(f"Error: user '{args.u}' already exists.")
            sys.exit(1)

        user = User(username=args.u, password=hashed)
        session.add(user)
        try:
            session.commit()
        except IntegrityError:
            print(f"Error: user '{args.u}' already exists.")
            sys.exit(1)

        print(f"User '{args.u}' created successfully (id: {user.uuid}).")


if __name__ == "__main__":
    main()
