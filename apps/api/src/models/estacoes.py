from sqlalchemy import Column, String, Text

from ..database import Base


class Estacao(Base):
    __tablename__ = "estacoes"

    hostname = Column(String(128), primary_key=True)
    ip_tailscale = Column(String(64), default="desconhecido")
    ultimo_ping = Column(String(32))
    status = Column(String(32), default="offline")