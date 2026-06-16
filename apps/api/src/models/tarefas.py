from sqlalchemy import Column, Integer, String, Text, ForeignKey

from ..database import Base


class Tarefa(Base):
    __tablename__ = "tarefas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    projeto_id = Column(Integer, ForeignKey("projetos.id"))
    titulo = Column(String(256))
    status = Column(String(32), default="pendente")
    prioridade = Column(String(16), default="media")
    data_limite = Column(String(16), nullable=True)