"""
main.py

API do backend (FastAPI) da Fase 2. Recebe os eventos enviados pelo
infer_webcam_yolo.py (uma peça nova por evento, com a contagem de parafusos),
grava no banco e expõe endpoints de consulta para o dashboard.

Rodar (a partir da pasta backend/):
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Documentação automática (Swagger) em:
    http://localhost:8000/docs
"""
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import case, func
from sqlalchemy.orm import Session

import models
import schemas
from database import Base, engine, get_db

STATUS_OK = "OK"
STATUS_CAMADA_INCORRETA = "ALERTA_CAMADA_INCORRETA"
STATUS_PARAFUSOS = "ALERTA_PARAFUSOS_INSUFICIENTES"

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Lean Lab - API de Eventos (Fase 2)")

# CORS liberado para o dashboard (outro processo/porta) consultar a API.
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
        parafusos_detectados=evento.parafusos_detectados,
        parafusos_esperados=evento.parafusos_esperados,
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
    limit: int = Query(200, ge=1, le=5000),
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
    """
    Agrega os eventos por estação em uma única consulta: total de peças,
    OK, alertas (por tipo), taxa de alerta, tempo médio de ciclo e média de
    parafusos detectados.
    """
    Evento = models.Evento
    linhas = (
        db.query(
            Evento.estacao,
            func.count(Evento.id),
            func.sum(case((Evento.status == STATUS_OK, 1), else_=0)),
            func.sum(case((Evento.status == STATUS_CAMADA_INCORRETA, 1), else_=0)),
            func.sum(case((Evento.status == STATUS_PARAFUSOS, 1), else_=0)),
            func.avg(Evento.tempo_ciclo_s),
            func.avg(Evento.parafusos_detectados),
        )
        .group_by(Evento.estacao)
        .order_by(Evento.estacao)
        .all()
    )

    resultado = []
    for estacao, total, ok, camada, parafusos, tempo_medio, media_parafusos in linhas:
        alertas = total - (ok or 0)  # qualquer status diferente de OK conta como alerta
        resultado.append(
            schemas.EstacaoStats(
                estacao=estacao,
                total_pecas=total,
                total_ok=int(ok or 0),
                total_alertas=alertas,
                alertas_camada_incorreta=int(camada or 0),
                alertas_parafusos_insuficientes=int(parafusos or 0),
                taxa_alerta=(alertas / total) if total else 0.0,
                tempo_medio_ciclo_s=float(tempo_medio or 0.0),
                media_parafusos_detectados=(
                    float(media_parafusos) if media_parafusos is not None else None
                ),
            )
        )
    return resultado
