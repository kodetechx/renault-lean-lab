"""
models.py

Modelo de dados (ORM) do evento gerado por uma estação. Cada linha
representa uma peça observada pela câmera: qual estação, qual classe foi
detectada, se estava correta ou disparou alerta, e o tempo de ciclo medido.
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
    status = Column(String, index=True)  # "OK" ou "ALERTA_CAMADA_INCORRETA"
    tempo_ciclo_s = Column(Float)
