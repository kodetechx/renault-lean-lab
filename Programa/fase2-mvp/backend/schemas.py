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
    # Nomes de classe separados por vírgula (ex.: "encaixe_circular,encaixe_hexagono").
    encaixes_detectados: Optional[str] = None
    encaixes_esperados: Optional[str] = None
    # Identifica qual treino gerou o modelo usado (ex.: "lean_lab_v2"), para
    # não misturar nas estatísticas eventos de versões de modelo diferentes.
    modelo_versao: Optional[str] = None


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
    encaixes_detectados: Optional[str] = None
    encaixes_esperados: Optional[str] = None
    modelo_versao: Optional[str] = None


class EstacaoStats(BaseModel):
    estacao: str
    total_pecas: int
    total_ok: int
    total_alertas: int
    alertas_camada_incorreta: int
    alertas_parafusos_insuficientes: int
    alertas_encaixe_incompleto: int
    taxa_alerta: float
    tempo_medio_ciclo_s: float
    # None quando nenhum evento da estação trouxe contagem de parafusos.
    media_parafusos_detectados: Optional[float] = None
    # Horário do evento mais recente dessa estação -- usado para sinalizar
    # estação "sem evento há muito tempo" (possível câmera travada/estação parada).
    ultimo_evento: Optional[datetime] = None
