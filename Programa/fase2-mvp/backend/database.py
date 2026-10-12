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


def ensure_sqlite_columns(model):
    """
    `Base.metadata.create_all()` so cria tabelas que ainda nao existem -- se o
    arquivo eventos.db ja existir de uma versao anterior de models.py, colunas
    novas (ex.: encaixes_detectados) nao aparecem sozinhas, e qualquer consulta
    que as mencione falha. Isso adiciona as colunas que faltarem, sem apagar
    dados. So vale para SQLite (prototipo); um banco real usaria uma ferramenta
    de migracao (ex.: Alembic) em vez disso.

    Recebe a CLASSE do modelo (ex.: models.Evento) e descobre nome da tabela e
    colunas direto dela via introspeccao -- de proposito, para nao depender de
    uma lista de colunas escrita a mao em outro lugar (main.py) que poderia
    ficar desatualizada se alguem adicionar uma coluna em models.py e esquecer
    de repetir aqui.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return
    tabela = model.__tablename__
    with engine.connect() as conn:
        existentes = {row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({tabela})")}
        for coluna in model.__table__.columns:
            if coluna.name in existentes or coluna.primary_key:
                continue
            tipo_sql = coluna.type.compile(dialect=engine.dialect)
            conn.exec_driver_sql(f"ALTER TABLE {tabela} ADD COLUMN {coluna.name} {tipo_sql}")
        conn.commit()
