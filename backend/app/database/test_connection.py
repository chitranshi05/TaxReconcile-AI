from app.database.mongodb import client, database


try:
    client.admin.command("ping")
    print("MongoDB connection successful!")
    print(f"Database: {database.name}")

except Exception as e:
    print("MongoDB connection failed!")
    print(e)