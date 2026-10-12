"""
app.py

Dashboard da Fase 2 (Streamlit). Consome a API do backend (backend/main.py) e
mostra: peças processadas por estação, taxa de alerta por tipo (camada
incorreta x parafusos insuficientes x encaixe incompleto), tempo médio de
ciclo, parafusos/encaixes detectados vs. esperados, tendência de eventos ao
longo do tempo, estações sem evento recente, e filtros por estação/status/
versão do modelo.

Rodar (com o backend já rodando em outro terminal), a partir da pasta dashboard/:
    streamlit run app.py
"""
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Lean Lab - Dashboard Fase 2", layout="wide")

FUSO_LOCAL = ZoneInfo("America/Sao_Paulo")
# Estações conhecidas (mesma lista de ESTACAO_RECEITA em infer_webcam_yolo.py),
# usada para apontar estação que nunca recebeu evento, não só a que parou.
ESTACOES_CONHECIDAS = ["camada_base", "camada_verde", "camada_amarela", "camada_azul", "camada_vermelha"]


def para_horario_local(serie_utc: pd.Series) -> pd.Series:
    """Timestamps do backend são UTC ingênuo (sem fuso); converte para horário local para exibição."""
    return pd.to_datetime(serie_utc).dt.tz_localize("UTC").dt.tz_convert(FUSO_LOCAL)


st.sidebar.header("Configuração")
API_URL = st.sidebar.text_input(
    "URL da API", "http://127.0.0.1:8000",
    help="127.0.0.1 em vez de 'localhost': em alguns Windows, 'localhost' resolve para IPv6 (::1) primeiro, "
         "e como o backend so escuta IPv4, cada chamada perderia ~2s tentando IPv6 antes de cair para IPv4.",
)
auto_refresh = st.sidebar.checkbox("Atualizar automaticamente (10s)", value=True)


def fetch(endpoint, params=None, default=None):
    try:
        resp = requests.get(f"{API_URL}{endpoint}", params=params, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Não foi possível conectar à API em {API_URL}: {e}")
        return default if default is not None else []


st.title("🏭 Dashboard — Lean Manufacturing Lab (Fase 2 · YOLO)")
st.warning(
    "A contagem de parafusos/encaixe depende do retreino e das condições de captura (ver README da "
    "fase2-mvp). A detecção da camada (cor) é o indicador mais confiável.",
    icon="⚠️",
)

versoes = fetch("/versoes-modelo", default=[])

st.sidebar.header("Filtros")
versao_selecionada = st.sidebar.selectbox("Versão do modelo", ["Todas"] + versoes)
versao_param = None if versao_selecionada == "Todas" else versao_selecionada

estacao_selecionada = st.sidebar.selectbox("Estação (tabela de eventos e tendência)", ["Todas"] + ESTACOES_CONHECIDAS)
status_selecionado = st.sidebar.selectbox(
    "Status (tabela de eventos e tendência)",
    ["Todos", "OK", "ALERTA_CAMADA_INCORRETA", "ALERTA_PARAFUSOS_INSUFICIENTES", "ALERTA_ENCAIXE_INCOMPLETO"],
)
limite_eventos = st.sidebar.number_input("Nº de eventos a carregar", min_value=50, max_value=5000, value=300, step=50)
limiar_parada_min = st.sidebar.number_input("Avisar estação parada após (min)", min_value=1, value=15)

# --- /estatisticas e /eventos, já filtrados pela versão do modelo (global) ---
stats = fetch("/estatisticas", params={"modelo_versao": versao_param} if versao_param else None)
# Sem filtro de versão: usada só para o aviso de "estação parada" (seção abaixo), que precisa
# refletir a saúde real das estações, não ficar escondendo estações ativas em outra versão do modelo.
stats_todas_versoes = stats if versao_param is None else fetch("/estatisticas")

params_eventos = {"limit": int(limite_eventos)}
if versao_param:
    params_eventos["modelo_versao"] = versao_param
if estacao_selecionada != "Todas":
    params_eventos["estacao"] = estacao_selecionada
if status_selecionado != "Todos":
    params_eventos["status"] = status_selecionado
eventos = fetch("/eventos", params=params_eventos)

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

    # --- Estações sem evento recente (ou que nunca enviaram nenhum) ---
    # Usa stats_todas_versoes (nunca filtrada por versão): uma estação ativa na v1 nao pode aparecer
    # como "parada" so porque o filtro de versao da tela esta em v2.
    agora_utc = datetime.utcnow()
    por_estacao = {row["estacao"]: row for row in stats_todas_versoes}
    paradas, nunca_vistas = [], []
    for est in ESTACOES_CONHECIDAS:
        row = por_estacao.get(est)
        if row is None or row.get("ultimo_evento") is None:
            nunca_vistas.append(est)
            continue
        ultimo = datetime.fromisoformat(row["ultimo_evento"])
        minutos = (agora_utc - ultimo).total_seconds() / 60
        if minutos > limiar_parada_min:
            paradas.append((est, minutos))
    if paradas or nunca_vistas:
        partes = []
        if paradas:
            partes.append(
                "sem evento há mais de "
                f"{limiar_parada_min} min: " + ", ".join(f"{e} ({m:.0f} min)" for e, m in paradas)
            )
        if nunca_vistas:
            partes.append("nunca receberam evento: " + ", ".join(nunca_vistas))
        st.warning("⏸️ Estações paradas — " + " · ".join(partes), icon="⏸️")

    st.subheader("Indicadores por estação")
    tabela = df_stats.copy()
    tabela["ultimo_evento"] = para_horario_local(tabela["ultimo_evento"]).dt.strftime("%d/%m %H:%M:%S")
    tabela = tabela.rename(
        columns={
            "estacao": "Estação",
            "total_pecas": "Peças",
            "total_ok": "OK",
            "total_alertas": "Alertas",
            "alertas_camada_incorreta": "Camada incorreta",
            "alertas_parafusos_insuficientes": "Parafusos insuficientes",
            "alertas_encaixe_incompleto": "Encaixe incompleto",
            "taxa_alerta": "Taxa de alerta",
            "tempo_medio_ciclo_s": "Tempo médio de ciclo (s)",
            "media_parafusos_detectados": "Média de parafusos detectados",
            "ultimo_evento": "Último evento (local)",
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
            df_stats.set_index("estacao")[
                ["alertas_camada_incorreta", "alertas_parafusos_insuficientes", "alertas_encaixe_incompleto"]
            ].rename(
                columns={
                    "alertas_camada_incorreta": "Camada incorreta",
                    "alertas_parafusos_insuficientes": "Parafusos insuficientes",
                    "alertas_encaixe_incompleto": "Encaixe incompleto",
                }
            )
        )
else:
    st.info("Ainda não há dados. Rode o infer_webcam_yolo.py apontando para esta API para gerar eventos.")

if eventos:
    df_ev = pd.DataFrame(eventos)
    df_ev["horario_local"] = para_horario_local(df_ev["timestamp"])

    st.subheader("Tendência de eventos ao longo do tempo")
    granularidade = st.selectbox("Agrupar por", ["1min", "5min", "15min", "1h"], index=1)
    tendencia = (
        df_ev.set_index("horario_local")
        .groupby([pd.Grouper(freq=granularidade), "status"])
        .size()
        .unstack(fill_value=0)
    )
    if not tendencia.empty:
        st.bar_chart(tendencia)
    else:
        st.caption("Sem eventos suficientes para montar a tendência com os filtros atuais.")

    st.subheader("Últimos eventos")
    st.caption(f"Mostrando até {int(limite_eventos)} eventos, filtros da barra lateral aplicados.")
    df_ev_tabela = df_ev.sort_values("horario_local", ascending=False).rename(
        columns={
            "estacao": "Estação",
            "classe_detectada": "Camada detectada",
            "status": "Status",
            "tempo_ciclo_s": "Ciclo (s)",
            "parafusos_detectados": "Parafusos detectados",
            "parafusos_esperados": "Parafusos esperados",
            "encaixes_detectados": "Encaixes detectados",
            "encaixes_esperados": "Encaixes esperados",
            "modelo_versao": "Versão do modelo",
            "horario_local": "Horário (local)",
        }
    )
    colunas_exibidas = [
        "Horário (local)", "Estação", "Camada detectada", "Status", "Ciclo (s)",
        "Parafusos detectados", "Parafusos esperados", "Encaixes detectados", "Encaixes esperados",
        "Versão do modelo",
    ]
    st.dataframe(df_ev_tabela[colunas_exibidas], hide_index=True)

    st.download_button(
        "⬇️ Baixar eventos filtrados (CSV)",
        data=df_ev_tabela[colunas_exibidas].to_csv(index=False).encode("utf-8"),
        file_name=f"eventos_fase2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
elif stats:
    st.info("Nenhum evento encontrado com os filtros atuais.")

if auto_refresh:
    time.sleep(10)
    st.rerun()
