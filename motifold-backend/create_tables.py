from alembic import command

from app.database import get_alembic_config


def main() -> None:
    command.upgrade(get_alembic_config(), "head")


if __name__ == "__main__":
    main()
