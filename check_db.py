from db.database import SessionLocal
from db.models import Norma
db = SessionLocal()
ops = [n.op for n in db.query(Norma).all()]
print("TOTAL EN DB:", len(ops))
