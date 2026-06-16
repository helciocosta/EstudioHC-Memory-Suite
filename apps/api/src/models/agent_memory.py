from sqlalchemy import Column, Integer, String, Text

from ..database import Base


class AgentMemory(Base):
    __tablename__ = "agent_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(32))
    agent_name = Column(String(128))
    project = Column(String(256))
    category = Column(String(64), default="task")
    content = Column(Text)