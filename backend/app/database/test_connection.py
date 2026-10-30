def check_database_connection() -> None:
    """Explicitly verify MongoDB connectivity when requested."""
    from app.database.mongodb import client

    client.admin.command("ping")