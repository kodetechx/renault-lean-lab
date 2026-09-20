"""
app.py

Dashboard da Fase 2 (Streamlit). Consome a API do backend (backend/main.py) e
mostra: peças processadas por estação, taxa de alerta separada por tipo
(camada incorreta x parafusos insuficientes), tempo médio de ciclo e a
contagem de parafusos detectados vs. esperados.

Rodar (com o backend já rodando em outro terminal), a partir da pasta dashboard/:
    streamlit run app.py
"""
import time

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Lean Lab - Dashboard Fase 2", layout="wide")

st.sidebar.header("Configuração")
API_URL = st.sidebar.text_input("URL da API", "http://localhost:8000")
auto_refresh = st.sidebar.checkbox("Atualizar automaticamente (10s)", value=True)

st.title("🏭 Dashboard — Lean Manufacturing Lab (Fase 2 · YOLO)")
st.warning(
    "A contagem de parafusos é **preliminar**: o modelo atual foi treinado com pouquíssimos "
    "exemplos de parafuso. Os alertas de parafusos insuficientes só serão confiáveis depois do "
    "retreino com o dataset dedicado. A detecção da camada (cor) é o indicador confiável.",
    icon="⚠️",
)


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
    # Média ponderada pelo nº de peças: uma estação com mais peças pesa mais.
    tempo_medio = (
        float((df_stats["tempo_medio_ciclo_s"] * df_stats["total_pecas"]).sum() / total_pecas)
        if total_pecas
        else 0.0
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Peças processadas", total_pecas)
    col2.metric("Alertas", total_alertas)
    col3.metric("Taxa de alerta", f"{taxa_geral:.1%}")
    col4.metric("Tempo médio de ciclo", f"{tempo_medio:.1f} s")

    st.subheader("Indicadores por estação")
    tabela = df_stats.rename(
        columns={
            "estacao": "Estação",
            "total_pecas": "Peças",
            "total_ok": "OK",
            "total_alertas": "Alertas",
            "alertas_camada_incorreta": "Camada incorreta",
            "alertas_parafusos_insuficientes": "Parafusos insuficientes",
            "taxa_alerta": "Taxa de alerta",
            "tempo_medio_ciclo_s": "Tempo médio de ciclo (s)",
            "media_parafusos_detectados": "Média de parafusos detectados",
        }
    )
    tabela["Taxa de alerta"] = tabela["Taxa de alerta"] * 100
    st.dataframe(
        tabela,
        hide_index=True,
        column_config={
            "Taxa de alerta": st.column_config.NumberColumn(format="%.1f%%"),
            "Tempo médio de ciclo (s)": st.column_config.NumberColumn(format="%.1f"),
            "Média de parafusos detectados": st.column_config.NumberColumn(format="%.1f"),
        },
    )

    left, right = st.columns(2)
    with left:
        st.subheader("Peças processadas por estação")
        st.bar_chart(df_stats.set_index("estacao")["total_pecas"])
    with right:
        st.subheader("Alertas por tipo e estação")
        st.bar_chart(
            df_stats.set_index("estacao")[["alertas_camada_incorreta", "alertas_parafusos_insuficientes"]].rename(
                columns={
                    "alertas_camada_incorreta": "Camada incorreta",
                    "alertas_parafusos_insuficientes": "Parafusos insuficientes",
                }
            )
        )
else:
    st.info("Ainda não há dados. Rode o infer_webcam_yolo.py apontando para esta API para gerar eventos.")

if eventos:
    st.subheader("Últimos eventos")
    df_ev = pd.DataFrame(eventos)
    df_ev["timestamp"] = pd.to_datetime(df_ev["timestamp"])
    df_ev = df_ev.sort_values("timestamp", ascending=False).rename(
        columns={
            "timestamp": "Horário (UTC)",
            "estacao": "Estação",
            "classe_detectada": "Camada detectada",
            "status": "Status",
            "tempo_ciclo_s": "Ciclo (s)",
            "parafusos_detectados": "Parafusos detectados",
            "parafusos_esperados": "Parafusos esperados",
        }
    )
    st.dataframe(df_ev.drop(columns=["id"]), hide_index=True)

if auto_refresh:
    time.sleep(10)
    st.rerun()
