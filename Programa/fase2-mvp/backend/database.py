"""
database.py

Configuração da conexão com o banco de dados.

SQLite para o protótipo (um único arquivo `eventos.db`, criado dentro de
backend/ quando o servidor é iniciado a partir desta pasta). Como o acesso é
feito via SQLAlchemy, trocar para PostgreSQL é só mudar DATABASE_URL — pode
ser feito por variável de ambiente, sem editar o código.
"""
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./eventos.db")
# Exemplo de troca futura para PostgreSQL:
# DATABASE_URL=postgresql://usuario:senha@localhost:5432/lean_lab

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
