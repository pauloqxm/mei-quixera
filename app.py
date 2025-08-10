
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

# ---------------------------- THEME / STYLES (Time Paulo Ferreira) ----------------------------
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
    .kpi {background: var(--card); border:1px solid var(--ring); padding:18px; border-radius: var(--radius); box-shadow: var(--shadow);}
    .kpi h3 {margin: 0 0 8px 0; font-size: 13px; color: var(--muted); font-weight: 700; letter-spacing: .3px; text-transform:uppercase;}
    .kpi .big {font-size: 30px; font-weight: 900; color: var(--text);}
    .chip {display:inline-flex; gap:8px; align-items:center; background:#181f2a; border:1px solid var(--ring); padding:6px 10px; border-radius:999px; font-size:12px; color:var(--muted);}
    .card {background: var(--card); border:1px solid var(--ring); padding:16px; border-radius: var(--radius); box-shadow: var(--shadow);}
    .footer {color: var(--muted); font-size: 12px; margin-top: 28px;}
    .stDataFrame {border: 1px solid var(--ring); border-radius: var(--radius);}
    .metric-badge {font-size:12px; color:var(--muted);}
    .accent-btn > button {background: var(--brand); color: white; border:0; font-weight:700;}
    .accent-btn > button:hover {filter: brightness(1.05);}
    </style>
""", unsafe_allow_html=True)

# ---------------------------- HEADER BAR ----------------------------
col_logo, col_title, col_right = st.columns([0.12, 0.64, 0.24])
with col_logo:
    logo = st.file_uploader("Logo (opcional)", type=["png","jpg","jpeg"], label_visibility="collapsed")
    if logo:
        st.image(logo, width=64)
with col_title:
    st.markdown('<div class="topbar"><div class="title">📊 Painel — Time Paulo Ferreira</div><div>🔎 Explore os dados com filtros dinâmicos</div></div>', unsafe_allow_html=True)
with col_right:
    st.markdown('<div style="text-align:right;padding-top:8px;"><span class="chip">Tema • Vermelho PT</span></div>', unsafe_allow_html=True)

# ---------------------------- LOAD DATA ----------------------------
@st.cache_data
def load_data(file):
    df = pd.read_csv(file, sep=",", low_memory=False)
    # datas
    for col in ["DATA_INICIO_ATIVIDADE", "DATA_SITUACAO_CADASTRAL"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True, infer_datetime_format=True)
    df["ANO_INICIO"] = df["DATA_INICIO_ATIVIDADE"].dt.year if "DATA_INICIO_ATIVIDADE" in df.columns else np.nan
    # texto
    for col in ["UF","MUNICIPIO","SITUACAO_CADASTRAL","NOME_FANTASIA","CNAE_FISCAL_PRINCIPAL"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df

DEFAULT_PATH = "baseqxbim_modelo.csv"
up = st.file_uploader("📥 Envie a base CSV (ou deixe em branco para usar o arquivo local 'baseqxbim_modelo.csv')", type=["csv"])
df = load_data(up if up is not None else DEFAULT_PATH)

if df.empty:
    st.warning("Base vazia. Envie um CSV válido.")
    st.stop()

# ---------------------------- SIDEBAR FILTERS ----------------------------
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Red_star.svg/240px-Red_star.svg.png", caption="Time Paulo Ferreira", use_column_width=True)
    st.markdown("## ⚙️ Filtros")
    anos_validos = sorted(df["ANO_INICIO"].dropna().unique().tolist())
    year_min, year_max = (int(min(anos_validos)), int(max(anos_validos))) if anos_validos else (2000, 2025)
    ano_range = st.slider("Período (ano de início)", min_value=year_min, max_value=year_max, value=(year_min, year_max), step=1)

    ufs = sorted([u for u in df.get("UF", pd.Series(dtype=str)).dropna().unique().tolist() if u])
    uf_sel = st.multiselect("UF", options=ufs, default=ufs if len(ufs) <= 8 else [])

    munis = sorted([m for m in df.get("MUNICIPIO", pd.Series(dtype=str)).dropna().unique().tolist() if m])
    muni_sel = st.multiselect("Município", options=munis, default=[])

    situ_opts = sorted([s for s in df.get("SITUACAO_CADASTRAL", pd.Series(dtype=str)).dropna().unique().tolist() if s])
    situ_sel = st.multiselect("Situação Cadastral", options=situ_opts, default=[])

    cnae_opts = sorted([c for c in df.get("CNAE_FISCAL_PRINCIPAL", pd.Series(dtype=str)).dropna().unique().tolist() if c])
    cnae_sel = st.multiselect("CNAE Principal", options=cnae_opts, default=[])

    search = st.text_input("Buscar por Nome Fantasia", placeholder="Digite parte do nome...")

# ---------------------------- FILTER ----------------------------
mask = (df["ANO_INICIO"].fillna(year_min) >= ano_range[0]) & (df["ANO_INICIO"].fillna(year_max) <= ano_range[1])
if uf_sel:   mask &= df["UF"].isin(uf_sel)
if muni_sel: mask &= df["MUNICIPIO"].isin(muni_sel)
if situ_sel: mask &= df["SITUACAO_CADASTRAL"].isin(situ_sel)
if cnae_sel: mask &= df["CNAE_FISCAL_PRINCIPAL"].isin(cnae_sel)
if search:   mask &= df.get("NOME_FANTASIA", "").astype(str).str.contains(search, case=False, na=False)

fdf = df[mask].copy()

# ---------------------------- KPIs ----------------------------
st.markdown('<div class="chip">Filtro ativo • {} registros</div>'.format(len(fdf)), unsafe_allow_html=True)
col1, col2, col3, col4 = st.columns(4)
with col1: st.markdown('<div class="kpi"><h3>Total de Empresas</h3><div class="big">{:,}</div></div>'.format(len(fdf)), unsafe_allow_html=True)
with col2: st.markdown('<div class="kpi"><h3>UFs</h3><div class="big">{:,}</div></div>'.format(fdf["UF"].nunique() if "UF" in fdf else 0), unsafe_allow_html=True)
with col3: st.markdown('<div class="kpi"><h3>Municípios</h3><div class="big">{:,}</div></div>'.format(fdf["MUNICIPIO"].nunique() if "MUNICIPIO" in fdf else 0), unsafe_allow_html=True)
with col4: st.markdown('<div class="kpi"><h3>Anos</h3><div class="big">{:,}</div></div>'.format(fdf["ANO_INICIO"].nunique()), unsafe_allow_html=True)

# ---------------------------- CHARTS ----------------------------
c1, c2 = st.columns([1,1])
with c1:
    if "SITUACAO_CADASTRAL" in fdf.columns and not fdf.empty:
        situ_counts = fdf["SITUACAO_CADASTRAL"].fillna("Não informado").value_counts().reset_index()
        situ_fig = px.bar(situ_counts, x="index", y="SITUACAO_CADASTRAL",
                          title="Empresas por Situação Cadastral",
                          labels={"index":"Situação", "SITUACAO_CADASTRAL":"Quantidade"})
        situ_fig.update_layout(margin=dict(l=8,r=8,t=50,b=8), height=380, bargap=0.25,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(situ_fig, use_container_width=True)
    else:
        st.info("Sem coluna 'SITUACAO_CADASTRAL' ou dados.")

with c2:
    if "CNAE_FISCAL_PRINCIPAL" in fdf.columns and not fdf.empty:
        top_cnae = fdf["CNAE_FISCAL_PRINCIPAL"].fillna("Não informado").value_counts().head(10).reset_index()
        cnae_fig = px.bar(top_cnae, x="index", y="CNAE_FISCAL_PRINCIPAL",
                          title="Top 10 CNAE Principal", labels={"index":"CNAE", "CNAE_FISCAL_PRINCIPAL":"Quantidade"})
        cnae_fig.update_layout(margin=dict(l=8,r=8,t=50,b=8), height=380, bargap=0.25,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(cnae_fig, use_container_width=True)
    else:
        st.info("Sem coluna 'CNAE_FISCAL_PRINCIPAL' ou dados.")

c3, c4 = st.columns([1,1])
with c3:
    if "MUNICIPIO" in fdf.columns and not fdf.empty:
        top_muni = fdf["MUNICIPIO"].fillna("Não informado").value_counts().head(10).reset_index()
        muni_fig = px.bar(top_muni, x="index", y="MUNICIPIO",
                          title="Top 10 Municípios", labels={"index":"Município", "MUNICIPIO":"Quantidade"})
        muni_fig.update_layout(margin=dict(l=8,r=8,t=50,b=8), height=380, bargap=0.25,
                               plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(muni_fig, use_container_width=True)
    else:
        st.info("Sem coluna 'MUNICIPIO' ou dados.")

with c4:
    if "ANO_INICIO" in fdf.columns and not fdf.empty:
        serie = fdf.dropna(subset=["ANO_INICIO"]).groupby("ANO_INICIO").size().reset_index(name="Qtd")
        serie_fig = px.line(serie, x="ANO_INICIO", y="Qtd", markers=True, title="Evolução de Aberturas por Ano")
        serie_fig.update_traces(line=dict(width=3))
        serie_fig.update_layout(margin=dict(l=8,r=8,t=50,b=8), height=380,
                                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(serie_fig, use_container_width=True)
    else:
        st.info("Sem a coluna 'DATA_INICIO_ATIVIDADE' para gerar a evolução.")

# ---------------------------- TABLE ----------------------------
st.markdown("#### 📄 Registros filtrados")
st.dataframe(fdf, use_container_width=True, hide_index=True)

# ---------------------------- DOWNLOADS ----------------------------
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="dados")
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
