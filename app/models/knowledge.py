from sqlalchemy import Text, String
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.database import Base

class Knowledge(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536), nullable=False)