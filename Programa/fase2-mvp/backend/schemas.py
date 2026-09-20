"""
schemas.py

Schemas Pydantic: definem o formato dos dados que a API aceita (entrada) e
devolve (saída), com validação automática do FastAPI.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EventoCreate(BaseModel):
    estacao: str
    classe_detectada: str
    status: str
    tempo_ciclo_s: float
    timestamp: Optional[datetime] = None
    parafusos_detectados: Optional[int] = Field(default=None, ge=0)
    parafusos_esperados: Optional[int] = Field(default=None, ge=0)


class EventoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    estacao: str
    classe_detectada: str
    status: str
    tempo_ciclo_s: float
    parafusos_detectados: Optional[int] = None
    parafusos_esperados: Optional[int] = None


class EstacaoStats(BaseModel):
    estacao: str
    total_pecas: int
    total_ok: int
    total_alertas: int
    alertas_camada_incorreta: int
    alertas_parafusos_insuficientes: int
    taxa_alerta: float
    tempo_medio_ciclo_s: float
    # None quando nenhum evento da estação trouxe contagem de parafusos.
    media_parafusos_detectados: Optional[float] = None
