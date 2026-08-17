import os
import sqlite3

# Get the absolute path to the 'db' directory where this script lives
DB_DIR = os.path.dirname(os.path.abspath(__file__))

# Create absolute paths for all files so it works from any terminal location
DATABASE_NAME = os.path.join(DB_DIR, "database.db")
SCHEMA_FILE = os.path.join(DB_DIR, "schema.sql")
SEED_FILE = os.path.join(DB_DIR, "seed.sql")

# Remove old database if it exists
if os.path.exists(DATABASE_NAME):
    os.remove(DATABASE_NAME)

# Create new database
connection = sqlite3.connect(DATABASE_NAME)

# Create tables
with open(SCHEMA_FILE, "r") as schema_file:
    connection.executescript(schema_file.read())

# Insert seed data
with open(SEED_FILE, "r") as seed_file:
    connection.executescript(seed_file.read())

connection.commit()
connection.close()

print("Database created successfully.")
print("Sample data inserted successfully.")