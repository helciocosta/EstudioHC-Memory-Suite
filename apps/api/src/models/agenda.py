from sqlalchemy import Column, String, Text

from ..database import Base


class Agenda(Base):
    __tablename__ = "agenda"

    id = Column(String(64), primary_key=True)
    data = Column(String(16))
    hora = Column(String(8))
    titulo = Column(String(256))
    estacao = Column(String(128), default="central")
    descricao = Column(Text, default="")
    timestamp = Column(String(32))