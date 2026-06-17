from pydantic import BaseModel
from typing import Optional


class MemoryEntry(BaseModel):
    agent_name: str
    project: str
    content: str
    category: str = "task"


class MemoryResponse(BaseModel):
    id: int
    timestamp: str
    agent_name: str
    project: str
    category: str
    content: str


class AgendaEntry(BaseModel):
    id: str
    data: str
    hora: str
    titulo: str
    estacao: Optional[str] = "central"
    descricao: Optional[str] = ""


class AgendaSavePayload(BaseModel):
    eventos: list[AgendaEntry]


class NotaEntry(BaseModel):
    texto: str
    estacao: Optional[str] = "desconhecida"


class ProjetoEntry(BaseModel):
    nome: str
    local_caminho: str
    status: Optional[str] = "ativo"
    tags: Optional[str] = ""
    readme_preview: Optional[str] = ""
    estacao: Optional[str] = "central"


class ProjetosSyncPayload(BaseModel):
    projetos: list[ProjetoEntry]


class ProjetoRelatorioPayload(BaseModel):
    nome: str
    readme: Optional[str] = ""
    git_status: Optional[str] = ""
    git_log: Optional[str] = ""
    estacao: Optional[str] = "desconhecida"
    tasks_content: Optional[str] = ""


class ChatPayload(BaseModel):
    mensagem: str
    contexto: Optional[str] = ""


class ResumoPayload(BaseModel):
    resumo: str
    agente: str


class EstacaoPing(BaseModel):
    hostname: str
    ip: str = "desconhecido"


class TarefaCreate(BaseModel):
    projeto_id: int
    titulo: str
    status: str = "pendente"
    prioridade: str = "media"
    data_limite: str | None = None


class TarefaUpdate(BaseModel):
    titulo: str | None = None
    status: str | None = None
    prioridade: str | None = None
    data_limite: str | None = None