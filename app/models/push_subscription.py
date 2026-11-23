from sqlalchemy import Column, Integer, String, Text
from app.database import Base

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, index=True)
    endpoint = Column(Text, unique=True)
    p256dh = Column(Text)
    auth = Column(Text)
