# app.py
# Streamlit — MEIs por município (Dados Abertos CNPJ/RFB)
# --------------------------------------------------------
import io
import os
import re
import zipfile
from datetime import datetime
from urllib.parse import urljoin

import requests
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from dateutil import parser as dtparse

# ------------------ Config & estilo ------------------
st.set_page_config(page_title="MEI por Município • Dados CNPJ", layout="wide")

HEADER_CSS = """
<style>
:root {
  --brand: #0b5cff;
  --bg: #0f172a;
  --card: #111827;
  --text: #e5e7eb;
  --muted: #9ca3af;
}
[data-testid="stHeader"] {visibility: hidden;}
.app-header {
  position: sticky; top: 0; z-index: 999;
  padding: 18px 18px 12px 18px; margin: -80px -16px 12px -16px;
  background: linear-gradient(180deg, rgba(2,6,23,0.9), rgba(2,6,23,0.65));
  border-bottom: 1px solid #1f2937;
  backdrop-filter: blur(6px);
}
.app-title {font-size: 22px; color: var(--text); margin: 0; font-weight: 700;}
.app-sub {font-size: 13px; color: var(--muted); margin: 2px 0 0 0;}
.block {background: #0b1220; border: 1px solid #1f2937; border-radius: 14px; padding: 16px;}
.metric-card {background: #0b1220; border: 1px solid #1f2937; border-radius: 14px; padding: 14px;}
</style>
<div class="app-header">
  <div class="app-title">MEI por Município • Dados Abertos CNPJ</div>
  <div class="app-sub">Consulta direta à base pública da Receita Federal do Brasil (CNPJ) + cruzamento com Simples/MEI</div>
</div>
"""
st.markdown(HEADER_CSS, unsafe_allow_html=True)

# ------------------ Constantes ------------------
RFB_BASE = "https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/"
IBGE_UFS = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT","PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"]

# ------------------ Funções utilitárias (cacheadas) ------------------
@st.cache_data(ttl=60*60)
def ibge_municipios_por_uf(uf: str) -> pd.DataFrame:
    """Carrega municípios do IBGE para a UF (id, nome, microrregião, mesorregião)."""
    url = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    js = r.json()
    # Monta DataFrame com código de 7 dígitos e nome
    rows = []
    for it in js:
        rows.append({
            "municipio_nome": it["nome"],
            "municipio_ibge": str(it["id"]).zfill(7),
        })
    df = pd.DataFrame(rows).sort_values("municipio_nome").reset_index(drop=True)
    return df

@st.cache_data(ttl=60*60)
def rfb_latest_folder() -> str:
    """Descobre a pasta mensal mais recente no diretório da RFB."""
    r = requests.get(RFB_BASE, timeout=60)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    folders = []
    for a in soup.find_all("a"):
        href = a.get("href") or ""
        m = re.match(r"(\d{4}-\d{2})/?$", href)
        if m:
            folders.append(m.group(1))
    folders.sort(key=lambda s: dtparse.parse(s + "-01"))
    if not folders:
        raise RuntimeError("Não foi possível localizar pastas mensais no diretório da RFB.")
    return folders[-1]

@st.cache_data(ttl=60*60)
def rfb_month_urls(folder: str) -> dict:
    """Retorna URLs dos zips de estabelecimentos e simples para a pasta."""
    base = urljoin(RFB_BASE, folder + "/")
    r = requests.get(base, timeout=120)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    hrefs = [a.get("href") for a in soup.find_all("a") if a.get("href")]
    def pick(pattern):
        for h in hrefs:
            if re.search(pattern, h, re.I):
                return urljoin(base, h)
        return None
    return {
        "estab": pick(r"(?:estabelecimento|estabelecimentos).*\.zip$"),
        "simples": pick(r"simples.*\.zip$"),
    }

def _concat_csvs_from_zip(zip_bytes: bytes, wanted_prefixes: list[str], status_text: str) -> pd.DataFrame:
    """Lê todos CSVs do ZIP que começam com os prefixos informados (em chunks)."""
    dfs = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        members = [m for m in z.infolist() if m.filename.lower().endswith(".csv")]
        picked = []
        for info in members:
            base = os.path.basename(info.filename).lower()
            if any(base.startswith(pref) for pref in wanted_prefixes):
                picked.append(info)

        if not picked:
            raise RuntimeError(f"Nenhum CSV com prefixos {wanted_prefixes} no ZIP.")

        for idx, info in enumerate(picked, 1):
            st.write(f"{status_text}: lendo {os.path.basename(info.filename)} ({idx}/{len(picked)})")
            with z.open(info) as f:
                for chunk in pd.read_csv(
                    f, dtype=str, sep=";", encoding="utf-8",
                    low_memory=False, chunksize=200_000
                ):
                    dfs.append(chunk)

    df = pd.concat(dfs, ignore_index=True)
    df.columns = [c.strip().lower() for c in df.columns]
    return df

def _http_get_bytes(url: str, label: str) -> bytes:
    with st.status(f"Baixando {label}…", expanded=False) as s:
        r = requests.get(url, stream=True, timeout=300)
        r.raise_for_status()
        content = r.content
        s.update(label=f"{label} baixado", state="complete")
    return content

# ------------------ Sidebar (inputs) ------------------
with st.sidebar:
    st.markdown("### Parâmetros")
    uf = st.selectbox("UF", IBGE_UFS, index=IBGE_UFS.index("CE"))
    muni_df = pd.DataFrame()
    try:
        muni_df = ibge_municipios_por_uf(uf)
        municipio_nome = st.selectbox(
            "Município",
            muni_df["municipio_nome"].tolist(),
            index=muni_df["municipio_nome"].tolist().index("Quixeramobim") if uf=="CE" and "Quixeramobim" in muni_df["municipio_nome"].values else 0
        )
        municipio_ibge = muni_df.loc[muni_df["municipio_nome"]==municipio_nome, "municipio_ibge"].iloc[0]
    except Exception as e:
        st.warning("Não consegui carregar a lista do IBGE. Informe manualmente o código IBGE (7 dígitos).")
        municipio_ibge = st.text_input("Código IBGE do município", value="2311309").strip()
        municipio_nome = "(custom)"
    top_n = st.slider("Top CNAEs no gráfico", min_value=5, max_value=30, value=20, step=1)
    st.caption("Dica: se der memória insuficiente, feche outras abas/processos e tente novamente.")

run_btn = st.button("Rodar análise")

# ------------------ Execução ------------------
if run_btn:
    try:
        with st.spinner("Descobrindo mês mais recente no portal da RFB…"):
            folder = rfb_latest_folder()
        st.success(f"Mês mais recente: {folder}")

        urls = rfb_month_urls(folder)
        if not urls["estab"] or not urls["simples"]:
            st.error("Não encontrei os arquivos necessários (estabelecimentos/simples) para este mês.")
            st.stop()

        # ---- Baixar zips
        estab_zip = _http_get_bytes(urls["estab"], "estabelecimentos.zip")
        simples_zip = _http_get_bytes(urls["simples"], "simples.zip")

        # ---- Ler CSVs
        estab = _concat_csvs_from_zip(estab_zip, ["estabelec"], "Estabelecimentos")
        simples = _concat_csvs_from_zip(simples_zip, ["simples"], "Simples/MEI")

        # ---- Validar colunas essenciais
        need_estab = ["cnpj_basico", "cnpj_ordem", "cnpj_dv", "municipio", "uf"]
        miss = [c for c in need_estab if c not in estab.columns]
        if miss:
            st.error(f"Colunas ausentes em 'estabelecimentos': {miss}")
            st.stop()

        need_s = ["cnpj_basico", "opcao_pelo_mei", "data_opcao_mei", "data_exclusao_mei"]
        miss_s = [c for c in need_s if c not in simples.columns]
        if miss_s:
            st.error(f"Colunas ausentes em 'simples': {miss_s}")
            st.stop()

        # ---- Preparar e filtrar município
        estab["cnpj_completo"] = (
            estab["cnpj_basico"].str.zfill(8)
            + estab["cnpj_ordem"].str.zfill(4)
            + estab["cnpj_dv"].str.zfill(2)
        )
        estab["municipio"] = estab["municipio"].astype(str).str.zfill(7)
        mask = (estab["municipio"] == str(municipio_ibge).zfill(7)) & (estab["uf"].str.upper() == uf.upper())
        estab_mun = estab.loc[mask, :].copy()

        if estab_mun.empty:
            st.warning("Nenhum estabelecimento encontrado para o recorte escolhido.")
            st.stop()

        # Detectar coluna de CNAE principal
        cnae_cols = [c for c in estab_mun.columns if "cnae" in c and "principal" in c]
        cnae_col = cnae_cols[0] if cnae_cols else ("cnae_fiscal" if "cnae_fiscal" in estab_mun.columns else None)

        # ---- Status MEI mais recente por CNPJ básico
        simples_last = (
            simples[["cnpj_basico", "opcao_pelo_mei", "data_opcao_mei", "data_exclusao_mei"]]
            .assign(is_mei=lambda d: d["opcao_pelo_mei"].str.upper().eq("S"))
            .sort_values(["cnpj_basico", "is_mei", "data_opcao_mei"], ascending=[True, False, False])
            .drop_duplicates(subset=["cnpj_basico"], keep="first")
        )

        out = estab_mun.merge(
            simples_last[["cnpj_basico", "is_mei", "data_opcao_mei", "data_exclusao_mei"]],
            on="cnpj_basico",
            how="left",
        )
        out["is_mei"] = out["is_mei"].fillna(False)

        resumo = out.groupby(["municipio", "uf"], as_index=False).agg(
            total_estab=("cnpj_completo", "nunique"),
            total_mei=("is_mei", "sum"),
        )
        resumo["perc_mei"] = (resumo["total_mei"] / resumo["total_estab"]).round(4)

        # ---- Métricas
        st.markdown("#### Resultado")
        c1, c2, c3 = st.columns(3)
        total_estab = int(resumo["total_estab"].iloc[0])
        total_mei = int(resumo["total_mei"].iloc[0])
        perc_mei = float(resumo["perc_mei"].iloc[0]) * 100
        c1.metric("Estabelecimentos", f"{total_estab:,}".replace(",", "."))
        c2.metric("MEIs", f"{total_mei:,}".replace(",", "."))
        c3.metric("% MEI", f"{perc_mei:.2f}%")

        # ---- Tabelas
        with st.expander("Resumo por município (CSV)", expanded=True):
            st.dataframe(resumo, use_container_width=True)

        with st.expander("Detalhado (amostra)", expanded=False):
            st.dataframe(out.head(100), use_container_width=True)

        # ---- Downloads
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        resumo_csv = resumo.to_csv(index=False).encode("utf-8")
        detalhado_csv = out.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Baixar resumo (CSV)",
            data=resumo_csv,
            file_name=f"mei_resumo_{municipio_ibge}_{uf}_{ts}.csv",
            mime="text/csv"
        )
        st.download_button(
            "Baixar detalhado (CSV)",
            data=detalhado_csv,
            file_name=f"mei_detalhado_{municipio_ibge}_{uf}_{ts}.csv",
            mime="text/csv"
        )

        # ---- Gráfico por CNAE (apenas MEIs)
        if cnae_col:
            top = (
                out.loc[out["is_mei"], cnae_col]
                .fillna("NA").astype(str).str.strip().replace("", "NA")
                .value_counts()
                .head(int(top_n))
                .sort_values()
            )
            if len(top) > 0:
                fig = plt.figure(figsize=(10, 6))
                top.plot(kind="barh")
                plt.title(f"MEIs por CNAE principal – {municipio_nome} ({municipio_ibge}/{uf})")
                plt.xlabel("Quantidade")
                plt.ylabel("CNAE (código)")
                plt.tight_layout()
                st.pyplot(fig)

                # botão de download do PNG
                buf = io.BytesIO()
                fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
                st.download_button(
                    "Baixar gráfico (PNG)",
                    data=buf.getvalue(),
                    file_name=f"mei_por_cnae_{municipio_ibge}_{uf}_{ts}.png",
                    mime="image/png"
                )
            else:
                st.info("Sem dados de CNAE para os MEIs neste recorte.")
        else:
            st.info("CNAE principal não identificado nesta versão do arquivo 'estabelecimentos'.")

        # ---- Avisos finais
        st.caption(
            "Observações: o status de MEI é identificado no arquivo 'simples' (coluna 'opcao_pelo_mei'). "
            "Os diretórios e nomes de arquivos podem variar por mês; este app tenta detectar automaticamente."
        )

    except requests.HTTPError as e:
        st.error(f"Erro HTTP ao acessar dados: {e}")
    except Exception as e:
        st.exception(e)
