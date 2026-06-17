from pydantic import BaseModel
from typing import Optional


class TarefaCreate(BaseModel):
    projeto_id: int
    titulo: str
    status: Optional[str] = "pendente"
    prioridade: Optional[str] = "media"
    data_limite: Optional[str] = None


class TarefaUpdate(BaseModel):
    titulo: Optional[str] = None
    status: Optional[str] = None
    prioridade: Optional[str] = None
    data_limite: Optional[str] = None


class TarefaResponse(BaseModel):
    id: int
    projeto_id: int
    titulo: str
    status: str
    prioridade: str
    data_limite: Optional[str] = None