from sqlalchemy import Column, Integer, String, ForeignKey
from app.database import Base

class Reaction(Base):
    __tablename__ = "reactions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False)
    user_email = Column(String, nullable=False)
    emoji = Column(String, nullable=False)
    