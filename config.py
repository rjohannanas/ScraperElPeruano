import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# The Supabase connection string usually looks like:
# postgresql://postgres.[project]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
# For SQLAlchemy with psycopg2 it might need postgresql+psycopg2://...
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "sqlite:///./scraper.db"  # Fallback to local SQLite if no DB URL is provided
)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
