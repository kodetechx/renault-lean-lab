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
    # "OK", "ALERTA_CAMADA_INCORRETA", "ALERTA_PARAFUSOS_INSUFICIENTES" ou
    # "ALERTA_ENCAIXE_INCOMPLETO"
    status = Column(String, index=True)
    tempo_ciclo_s = Column(Float)
    # Anuláveis: eventos enviados por clientes que não medem parafusos/encaixe
    # (ex.: o infer_webcam.py da Fase 1) continuam sendo aceitos.
    parafusos_detectados = Column(Integer, nullable=True)
    parafusos_esperados = Column(Integer, nullable=True)
    # Nomes das classes de encaixe detectadas/esperadas, separados por vírgula
    # (ex.: "encaixe_circular,encaixe_retangular"), ou "" se a estação não
    # exige nenhuma. Guardado como texto porque é uma lista pequena e de
    # tamanho variável -- não justifica uma tabela separada no protótipo.
    encaixes_detectados = Column(String, nullable=True)
    encaixes_esperados = Column(String, nullable=True)
    # Nome da pasta do treino que gerou o modelo usado (ex.: "lean_lab_v2"),
    # para não misturar nas estatisticas eventos de modelos diferentes.
    modelo_versao = Column(String, nullable=True, index=True)
