"""
app.py

Dashboard do protótipo (Streamlit). Consome a API do backend (main.py) e
mostra os indicadores pedidos no desafio: peças processadas por estação,
taxa de alerta (montagem incorreta) e tempo médio de ciclo.

Rodar (com o backend já rodando em outra janela de terminal):
    streamlit run app.py
"""
import time

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Lean Lab - Dashboard", layout="wide")

st.sidebar.header("Configuração")
API_URL = st.sidebar.text_input("URL da API", "http://localhost:8000")
auto_refresh = st.sidebar.checkbox("Atualizar automaticamente (10s)", value=True)

st.title("🏭 Dashboard — Lean Manufacturing Lab (Renault x UniSenai)")


def fetch(endpoint, params=None):
    try:
        resp = requests.get(f"{API_URL}{endpoint}", params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Não foi possível conectar à API em {API_URL}: {e}")
        return []


stats = fetch("/estatisticas")
eventos = fetch("/eventos", params={"limit": 200})

if stats:
    df_stats = pd.DataFrame(stats)

    total_pecas = int(df_stats["total_pecas"].sum())
    total_alertas = int(df_stats["total_alertas"].sum())
    taxa_geral = (total_alertas / total_pecas) if total_pecas else 0.0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de peças processadas", total_pecas)
    col2.metric("Total de alertas", total_alertas)
    col3.metric("Taxa de alerta geral", f"{taxa_geral:.1%}")

    st.subheader("Indicadores por estação")
    st.dataframe(
        df_stats.rename(
            columns={
                "estacao": "Estação",
                "total_pecas": "Peças processadas",
                "total_alertas": "Alertas",
                "taxa_alerta": "Taxa de alerta",
                "tempo_medio_ciclo_s": "Tempo médio de ciclo (s)",
            }
        ),
        use_container_width=True,
    )

    st.subheader("Peças processadas por estação")
    st.bar_chart(df_stats.set_index("estacao")["total_pecas"])
else:
    st.info("Ainda não há dados. Rode o infer_webcam.py apontando para esta API para gerar eventos.")

if eventos:
    st.subheader("Últimos eventos")
    df_ev = pd.DataFrame(eventos)
    df_ev["timestamp"] = pd.to_datetime(df_ev["timestamp"])
    st.dataframe(df_ev.sort_values("timestamp", ascending=False), use_container_width=True)

if auto_refresh:
    time.sleep(10)
    st.rerun()
