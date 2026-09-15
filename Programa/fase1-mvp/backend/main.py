"""
main.py

API do backend (FastAPI). Recebe os eventos enviados pelo infer_webcam.py
(uma peça observada por estação, com status OK ou de alerta), grava no
banco, e expõe endpoints de consulta para o dashboard.

Rodar:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Documentação automática (Swagger) disponível em:
    http://localhost:8000/docs
"""
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lean Lab - API de Eventos")

# CORS liberado para o dashboard (rodando em outra porta/processo) poder
# consultar a API sem bloqueio do navegador.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/eventos", response_model=schemas.EventoOut)
def criar_evento(evento: schemas.EventoCreate, db: Session = Depends(get_db)):
    db_evento = models.Evento(
        estacao=evento.estacao,
        classe_detectada=evento.classe_detectada,
        status=evento.status,
        tempo_ciclo_s=evento.tempo_ciclo_s,
        timestamp=evento.timestamp or datetime.utcnow(),
    )
    db.add(db_evento)
    db.commit()
    db.refresh(db_evento)
    return db_evento


@app.get("/eventos", response_model=List[schemas.EventoOut])
def listar_eventos(
    estacao: Optional[str] = None,
    status_evento: Optional[str] = Query(None, alias="status"),
    limit: int = 200,
    db: Session = Depends(get_db),
):
    query = db.query(models.Evento)
    if estacao:
        query = query.filter(models.Evento.estacao == estacao)
    if status_evento:
        query = query.filter(models.Evento.status == status_evento)
    return query.order_by(models.Evento.timestamp.desc()).limit(limit).all()


@app.get("/estatisticas", response_model=List[schemas.EstacaoStats])
def estatisticas(db: Session = Depends(get_db)):
    """Agrega os eventos por estação: total de peças, alertas, taxa de alerta e tempo médio de ciclo."""
    estacoes = [row[0] for row in db.query(models.Evento.estacao).distinct().all()]
    resultado = []
    for estacao in estacoes:
        eventos_da_estacao = db.query(models.Evento).filter(models.Evento.estacao == estacao)
        total = eventos_da_estacao.count()
        alertas = eventos_da_estacao.filter(models.Evento.status != "OK").count()
        tempo_medio = (
            db.query(func.avg(models.Evento.tempo_ciclo_s))
            .filter(models.Evento.estacao == estacao)
            .scalar()
            or 0.0
        )
        resultado.append(
            schemas.EstacaoStats(
                estacao=estacao,
                total_pecas=total,
                total_alertas=alertas,
                taxa_alerta=(alertas / total) if total else 0.0,
                tempo_medio_ciclo_s=float(tempo_medio),
            )
        )
    return resultado
