from sqlalchemy import create_engine, text
from passlib.context import CryptContext
from dotenv import load_dotenv
import uuid
import os

load_dotenv()

engine = create_engine(os.getenv("DATABASE_URL"))
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
hashed = pwd.hash("Shalimar2024")

print(f"Hash generated: {hashed}")
print(f"Hash length: {len(hashed)}")

with engine.connect() as conn:
    # Delete old broken user first
    conn.execute(text("DELETE FROM users WHERE username = 'hod_admin'"))
    
    # Insert fresh user with correctly generated hash
    conn.execute(text("""
        INSERT INTO users (id, name, username, password_hash, role, department, is_active)
        VALUES (:id, :name, :username, :password_hash, :role, :department, :is_active)
    """), {
        "id": str(uuid.uuid4()),
        "name": "HOD Admin",
        "username": "hod_admin",
        "password_hash": hashed,
        "role": "hod",
        "department": "boiler",
        "is_active": True
    })
    conn.commit()
    print("HOD user created successfully!")