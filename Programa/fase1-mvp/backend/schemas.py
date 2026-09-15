"""
schemas.py

Schemas Pydantic: definem o formato dos dados que a API aceita (entrada) e
devolve (saída), com validação automática do FastAPI.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class EventoCreate(BaseModel):
    estacao: str
    classe_detectada: str
    status: str
    tempo_ciclo_s: float
    timestamp: Optional[datetime] = None


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    estacao: str
    classe_detectada: str
    status: str
    tempo_ciclo_s: float


class EstacaoStats(BaseModel):
    estacao: str
    total_pecas: int
    total_alertas: int
    taxa_alerta: float
    tempo_medio_ciclo_s: float
