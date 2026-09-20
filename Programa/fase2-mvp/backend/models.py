"""
models.py

Modelo de dados (ORM) do evento gerado por uma estação. Cada linha é uma
peça nova detectada pela câmera: qual estação, qual camada foi detectada,
quantos parafusos foram contados na peça e o resultado (OK ou alerta).
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from database import Base


class Evento(Base):
    __tablename__ = "eventos"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    estacao = Column(String, index=True)
    classe_detectada = Column(String)
    # "OK", "ALERTA_CAMADA_INCORRETA" ou "ALERTA_PARAFUSOS_INSUFICIENTES"
    status = Column(String, index=True)
    tempo_ciclo_s = Column(Float)
    # Anuláveis: eventos enviados por clientes que não medem parafusos
    # (ex.: o infer_webcam.py da Fase 1) continuam sendo aceitos.
    parafusos_detectados = Column(Integer, nullable=True)
    parafusos_esperados = Column(Integer, nullable=True)
