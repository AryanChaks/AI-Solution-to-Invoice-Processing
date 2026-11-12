"""python scripts\\seed_database.py            -> create tables + seed (idempotent)
   python scripts\\seed_database.py --reset --yes -> DROP ALL tables, recreate, seed"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))   # so backend/.env is found
from app.database import seed

if "--reset" in sys.argv:
    if "--yes" not in sys.argv:
        sys.exit("Refusing to drop tables without --yes")
    seed.reset(); print("All tables dropped.")
print(seed.seed())
