"""
database.py

Configuração da conexão com o banco de dados.

Usamos SQLite para o protótipo (zero configuração, um único arquivo
`eventos.db`). Como o acesso ao banco é feito via SQLAlchemy (ORM), trocar
para PostgreSQL no futuro é só mudar a variável DATABASE_URL — o resto do
código (models.py, main.py) não precisa mudar.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./eventos.db"
# Exemplo de troca futura para PostgreSQL:
# DATABASE_URL = "postgresql://usuario:senha@localhost:5432/lean_lab"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
