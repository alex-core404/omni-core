from sqlalchemy import Column, Integer, String
from app.database import Base

class Contact(Base):
    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, index=True)
    owner_email = Column(String, index=True)
    contact_email = Column(String)
