# app.py — Painel Time Paulo Ferreira (sem sidebar, com gráfico de meses e filtro de período deslizante)
import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import plotly.express as px

st.set_page_config(
    page_title="📊 Painel — Time Paulo Ferreira",
    page_icon="🟥",
    layout="wide"
)

# ---------------------------- THEME / STYLES ----------------------------
st.markdown("""
    <style>
    :root {
        --brand: #e11d2e;       /* vermelho principal (PT/Time Paulo Ferreira) */
        --brand-2: #9f1239;     /* vermelho escuro */
        --accent: #fde047;      /* amarelo destaque */
        --bg: #0b0f14;          /* fundo escuro elegante */
        --card: #121821;
        --text: #f1f5f9;
        --muted: #a3acb5;
        --ring: #2b3540;
        --radius: 18px;
        --shadow: 0 10px 30px rgba(0,0,0,.28);
        --grad: linear-gradient(135deg, #e11d2e 0%, #9f1239 60%);
    }
    .block-container {padding-top: 1.2rem !important;}
    .topbar {
        background: var(--grad);
        border-bottom: 2px solid rgba(255,255,255,.12);
        box-shadow: var(--shadow);
        padding: 14px 18px;
        border-radius: 16px;
        display:flex; align-items:center; gap:14px; justify-content:space-between;
        color: white;
    }
    .topbar .title {font-size: 18px; font-weight: 800; letter-spacing: .2px;}
    .kpi {background: var(--card); border:1px solid var(--ring); padding:-18px; border-radius: var(--radius); box-shadow: var(--shadow);}
    .kpi h3 {margin: 0 0 8px 0; font-size: 13px; color: var(--muted); font-weight: 700; letter-spacing: .3px; text-transform:uppercase;}
    .kpi .big {font-size: 30px; font-weight: 900; color: var(--text);}
    .chip {display:inline-flex; gap:8px; align-items:center; background:#181f2a; border:1px solid var(--ring); padding:6px 10px; border-radius:999px; font-size:12px; color:var(--muted);}
    .card {background: var(--card); border:1px solid var(--ring); padding:16px; border-radius: var(--radius); box-shadow: var(--shadow);}
    .footer {color: var(--muted); font-size: 12px; margin-top: 28px;}
    .stDataFrame {border: 1px solid var(--ring); border-radius: var(--radius);}
    .metric-badge {font-size:12px; color:var(--muted);}
    .accent-btn > button {background: var(--brand); color: white; border:0; font-weight:700;}
    .accent-btn > button:hover {filter: brightness(1.05);}
    .stSlider > div {padding-top: 8px;}
    </style>
""", unsafe_allow_html=True)

# ---------------------------- HEADER ----------------------------
col_title, col_right = st.columns([0.7, 0.3])
with col_title:
    st.markdown('<div class="topbar"><div class="title">📊 Painel — Time Paulo Ferreira</div><div>🔎 Explore os dados com filtros no corpo da página</div></div>', unsafe_allow_html=True)
with col_right:
    st.markdown('<div style="text-align:right;padding-top:-20px;"><span class="chip">Tema • Vermelho PT</span></div>', unsafe_allow_html=True)

# ---------------------------- LOAD DATA ----------------------------
@st.cache_data
def load_data(path: str):
    df = pd.read_csv(path, sep=",", low_memory=False)

    # Datas -> datetime
    for col in ["DATA_INICIO_ATIVIDADE", "DATA_SITUACAO_CADASTRAL"]:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True, infer_datetime_format=True)
            except Exception:
                df[col] = pd.to_datetime(df[col], errors="coerce")

    # Ano e mês de início
    if "DATA_INICIO_ATIVIDADE" in df.columns:
        df["ANO_INICIO"] = df["DATA_INICIO_ATIVIDADE"].dt.year
        df["MES_INICIO_NUM"] = df["DATA_INICIO_ATIVIDADE"].dt.month
        df["DATA_COMPLETA"] = df["DATA_INICIO_ATIVIDADE"].dt.to_period('M').dt.to_timestamp()
    else:
        df["ANO_INICIO"] = np.nan
        df["MES_INICIO_NUM"] = np.nan
        df["DATA_COMPLETA"] = np.nan

    meses = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
    df["MES_INICIO"] = df["MES_INICIO_NUM"].apply(lambda m: meses[int(m)-1] if pd.notna(m) and 1 <= int(m) <= 12 else np.nan)

    # Padronização de texto
    for col in ["UF","MUNICIPIO","SITUACAO_CADASTRAL","NOME_FANTASIA","CNAE_FISCAL_PRINCIPAL"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df

# Caminho fixo (sem upload)
DEFAULT_PATH = "baseqxbim_modelo.csv"
df = load_data(DEFAULT_PATH)

if df.empty:
    st.warning("Base vazia. Garanta que 'baseqxbim_modelo.csv' está na mesma pasta do app.")
    st.stop()

# ---------------------------- FILTERS (NO BODY) ----------------------------
st.markdown("### ⚙️ Filtros")

# 1) Período (menu deslizante para data completa)
if "DATA_COMPLETA" in df.columns:
    min_date = df["DATA_COMPLETA"].min().to_pydatetime()
    max_date = df["DATA_COMPLETA"].max().to_pydatetime()
    date_range = st.slider(
        "Selecione o período:",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
        format="MM/YYYY"
    )
else:
    st.warning("Dados de data incompletos - usando filtro por ano como fallback")
    anos_validos = sorted(df["ANO_INICIO"].dropna().unique().tolist())
    year_min, year_max = (int(min(anos_validos)), int(max(anos_validos))) if anos_validos else (2000, 2025)
    ano_range = st.slider("Período (ano de início)", min_value=year_min, max_value=year_max,
                          value=(year_min, year_max), step=1)

# 2) Linha de filtros adicional
csit, ccnae, csearch = st.columns([0.35, 0.35, 0.30])

with csit:
    situ_opts = sorted([s for s in df.get("SITUACAO_CADASTRAL", pd.Series(dtype=str)).dropna().unique().tolist() if s])
    situ_sel = st.multiselect("Situação Cadastral", options=situ_opts, default=[])

with ccnae:
    cnae_opts = sorted([c for c in df.get("CNAE_FISCAL_PRINCIPAL", pd.Series(dtype=str)).dropna().unique().tolist() if c])
    cnae_sel = st.multiselect("CNAE Principal", options=cnae_opts, default=[])

with csearch:
    search = st.text_input("Buscar por Nome Fantasia", placeholder="Digite parte do nome...")

# ---------------------------- FILTER LOGIC ----------------------------
if "DATA_COMPLETA" in df.columns:
    mask = (df["DATA_COMPLETA"] >= date_range[0]) & (df["DATA_COMPLETA"] <= date_range[1])
else:
    mask = (df["ANO_INICIO"].fillna(year_min) >= ano_range[0]) & (df["ANO_INICIO"].fillna(year_max) <= ano_range[1])

if situ_sel:
    mask &= df["SITUACAO_CADASTRAL"].isin(situ_sel)
if cnae_sel:
    mask &= df["CNAE_FISCAL_PRINCIPAL"].isin(cnae_sel)
if search and "NOME_FANTASIA" in df.columns:
    mask &= df["NOME_FANTASIA"].astype(str).str.contains(search, case=False, na=False)

fdf = df[mask].copy()

# ---------------------------- KPIs ----------------------------
st.markdown('<div class="chip">Filtro ativo • {} registros</div>'.format(len(fdf)), unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="kpi"><h3>Total de Empresas</h3><div class="big">{:,}</div></div>'.format(len(fdf)), unsafe_allow_html=True)
with col2:
    st.markdown('<div class="kpi"><h3>UFs</h3><div class="big">{:,}</div></div>'.format(fdf["UF"].nunique() if "UF" in fdf else 0), unsafe_allow_html=True)
with col3:
    st.markdown('<div class="kpi"><h3>Municípios</h3><div class="big">{:,}</div></div>'.format(fdf["MUNICIPIO"].nunique() if "MUNICIPIO" in fdf else 0), unsafe_allow_html=True)
with col4:
    st.markdown('<div class="kpi"><h3>Período</h3><div class="big">{}-{}</div></div>'.format(
        date_range[0].strftime("%Y") if "DATA_COMPLETA" in df.columns else ano_range[0],
        date_range[1].strftime("%Y") if "DATA_COMPLETA" in df.columns else ano_range[1]
    ), unsafe_allow_html=True)

# ---------------------------- CHARTS ----------------------------
c1, c2 = st.columns([1,1])

# 1) Situação Cadastral
with c1:
    if "SITUACAO_CADASTRAL" in fdf.columns and not fdf.empty:
        situ_counts = (
            fdf["SITUACAO_CADASTRAL"]
            .fillna("Não informado")
            .value_counts()
            .rename_axis("Situacao")
            .reset_index(name="Quantidade")
        )
        fig = px.bar(
            situ_counts, x="Situacao", y="Quantidade",
            title="Empresas por Situação Cadastral",
            labels={"Situacao":"Situação", "Quantidade":"Quantidade"},
            color_discrete_sequence=["#e11d2e"]
        )
        fig.update_layout(margin=dict(l=8,r=8,t=50,b=8), height=360, bargap=0.25,
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem coluna 'SITUACAO_CADASTRAL' ou dados.")

# 2) Top CNAE
with c2:
    if "CNAE_FISCAL_PRINCIPAL" in fdf.columns and not fdf.empty:
        top_cnae = (
            fdf["CNAE_FISCAL_PRINCIPAL"]
            .fillna("Não informado")
            .value_counts()
            .head(10)
            .rename_axis("CNAE")
            .reset_index(name="Quantidade")
        )
        fig = px.bar(
            top_cnae, x="CNAE", y="Quantidade",
            title="Top 10 CNAE Principal",
            labels={"CNAE":"CNAE", "Quantidade":"Quantidade"},
            color_discrete_sequence=["#9f1239"]
        )
        fig.update_layout(margin=dict(l=8,r=8,t=50,b=8), height=360, bargap=0.25,
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem coluna 'CNAE_FISCAL_PRINCIPAL' ou dados.")

# 3) Linha temporal por ano + 4) Distribuição por mês
c3, c4 = st.columns([1,1])

with c3:
    if "ANO_INICIO" in fdf.columns and not fdf.empty:
        serie = fdf.dropna(subset=["ANO_INICIO"]).groupby("ANO_INICIO").size().reset_index(name="Qtd")
        fig = px.line(serie, x="ANO_INICIO", y="Qtd", markers=True, 
                     title="Evolução de Aberturas por Ano",
                     line_shape="spline")
        fig.update_traces(line=dict(width=3, color="#e11d2e"))
        fig.update_layout(margin=dict(l=8,r=8,t=50,b=8), height=360,
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem a coluna 'DATA_INICIO_ATIVIDADE' para gerar a evolução.")

with c4:
    if "MES_INICIO" in fdf.columns and not fdf.empty:
        meses_ordem = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"]
        mes_counts = (
            fdf["MES_INICIO"]
            .dropna()
            .astype(pd.CategoricalDtype(categories=meses_ordem, ordered=True))
            .value_counts()
            .sort_index()
            .reset_index(name="Quantidade")
            .rename(columns={"index": "Mês"})
        )
        fig = px.bar(mes_counts, x="MES_INICIO", y="Quantidade",
                    title="Aberturas por Mês",
                    labels={"MES_INICIO": "Mês", "Quantidade": "Quantidade"},
                    color_discrete_sequence=["#e11d2e"])
        fig.update_layout(margin=dict(l=8,r=8,t=50,b=8), height=360, bargap=0.25,
                        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem base de datas para o gráfico mensal.")

# ---------------------------- TABELA ----------------------------
st.markdown("#### 📄 Registros filtrados")
st.dataframe(fdf, use_container_width=True, hide_index=True)

# ---------------------------- DOWNLOADS ----------------------------
def to_excel_bytes(df_: pd.DataFrame) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df_.to_excel(writer, index=False, sheet_name="dados")
    return out.getvalue()

c5, c6 = st.columns([1,1])
with c5:
    st.download_button(
        label="⬇️ Baixar CSV (filtro aplicado)",
        data=fdf.to_csv(index=False).encode("utf-8"),
        file_name="dados_filtrados.csv",
        mime="text/csv",
        key="dl_csv"
    )
with c6:
    st.download_button(
        label="⬇️ Baixar Excel (filtro aplicado)",
        data=to_excel_bytes(fdf),
        file_name="dados_filtrados.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="dl_xlsx"
    )

st.markdown('<div class="footer">Feito com ❤️ em Streamlit + Plotly • Tema: Time Paulo Ferreira</div>', unsafe_allow_html=True)
