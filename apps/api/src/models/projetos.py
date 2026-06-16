from sqlalchemy import Column, Integer, String, Text

from ..database import Base


class Projeto(Base):
    __tablename__ = "projetos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(256))
    local_caminho = Column(Text)
    status = Column(String(64), default="ativo")
    tags = Column(String(512), default="")
    readme_preview = Column(Text, default="")
    estacao = Column(String(128), default="central")
    ultima_atualizacao = Column(String(32))