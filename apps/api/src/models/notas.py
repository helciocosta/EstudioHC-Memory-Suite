from sqlalchemy import Column, Integer, String, Text

from ..database import Base


class Nota(Base):
    __tablename__ = "notas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    estacao = Column(String(128))
    texto = Column(Text)
    timestamp = Column(String(32))