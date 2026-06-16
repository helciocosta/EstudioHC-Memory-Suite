from sqlalchemy import Column, String, Text

from ..database import Base


class ResumoDiario(Base):
    __tablename__ = "resumos_diarios"

    data = Column(String(16), primary_key=True)
    resumo = Column(Text)
    agente = Column(String(64))
    timestamp = Column(String(32))