from app.database import engine, SessionLocal, Base
from app import models

Base.metadata.create_all(bind=engine)

db = SessionLocal()
if db.query(models.Role).count() == 0:
    admin = models.Role(role_name="Admin", description="Full access")
    manager = models.Role(role_name="Manager", description="Manage documents")
    employee = models.Role(role_name="Employee", description="Ask questions only")
    db.add_all([admin, manager, employee])
    db.commit()
    print("Roles added")
db.close()
print("Database ready: app.db")