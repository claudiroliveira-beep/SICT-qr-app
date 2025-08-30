# app.py
# ==========================================
# Trabalhos & QR - versão consolidada (admin vs público)
# ==========================================
import os, io, uuid, sqlite3, datetime
import pandas as pd
import streamlit as st
from PIL import Image
import qrcode

# ---------------- Configurações -------------
st.set_page_config(page_title="Trabalhos & QR", layout="wide")
APP_TITLE = "Trabalhos & QR"

# Secrets / Env
ADMIN_PASS = st.secrets.get("STREAMLIT_ADMIN_PASS", os.getenv("STREAMLIT_ADMIN_PASS", ""))
SECRET_BASE_URL = st.secrets.get("BASE_URL", os.getenv("BASE_URL", "")).strip()

# DB (em produção, prefira banco externo; local pode perder dados em reimplantação)
DB_PATH = os.getenv("DB_PATH", "trabalhos.db")

# ----------------- DB helpers ----------------
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS trabalhos (
        id TEXT PRIMARY KEY,
        aluno TEXT,
        orientador TEXT,
        areas TEXT,
        titulo TEXT,
        avaliador1 TEXT,
        avaliador2 TEXT,
        painel INTEGER,
        created_at TEXT
    )
    """)
    return conn

def insert_trabalho(row):
    conn = get_conn()
    with conn:
        conn.execute("""
            INSERT INTO trabalhos 
              (id, aluno, orientador, areas, titulo, avaliador1, avaliador2, painel, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (row["id"], row["aluno"], row["orientador"], row["areas"], row["titulo"],
              row["avaliador1"], row["avaliador2"], row["painel"], row["created_at"]))

def update_trabalho(row):
    conn = get_conn()
    with conn:
        conn.execute("""
            UPDATE trabalhos SET
              aluno=?, orientador=?, areas=?, titulo=?, avaliador1=?, avaliador2=?, painel=?
            WHERE id=?
        """, (row["aluno"], row["orientador"], row["areas"], row["titulo"],
              row["avaliador1"], row["avaliador2"], row["painel"], row["id"]))

def get_trabalho_by_id(id_):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM trabalhos WHERE id=?", (id_,))
    row = cur.fetchone()
    if not row:
        return None
    cols = [d[0] for d in cur.description]
    return dict(zip(cols, row))

def list_trabalhos():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM trabalhos ORDER BY painel, aluno", conn)
    return df

def delete_trabalho(id_):
    conn = get_conn()
    with conn:
        conn.execute("DELETE FROM trabalhos WHERE id=?", (id_,))

# ----------------- Utils ---------------------
def normalize_header(s):
    if not isinstance(s, str):
        return s
    s = s.strip().lower()
    mapping = {
        "aluno": "aluno", "aluno(a)": "aluno", "aluna": "aluno",
        "orientador": "orientador",
        "áreas": "areas", "areas": "areas",
        "título": "titulo", "titulo": "titulo",
        "avaliador 1": "avaliador1", "avaliador1": "avaliador1",
        "avaliador 2": "avaliador2", "avaliador2": "avaliador2",
        "nº do painel": "painel", "no do painel": "painel", "n do painel": "painel",
        "painel": "painel"
    }
    return mapping.get(s, s)

def ensure_columns(df):
    df = df.copy()
    df.columns = [normalize_header(c) for c in df.columns]
    required = ["aluno", "orientador", "areas", "titulo", "avaliador1", "avaliador2", "painel"]
    for col in required:
        if col not in df.columns:
            df[col] = ""
    return df[required]

def build_detail_url(base_url: str, rec_id: str) -> str:
    base = (base_url or "").rstrip("/")
    return f"{base}/?id={rec_id}"

def make_qr_image(url: str) -> Image.Image:
    qr = qrcode.QRCode(version=2, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.convert("RGB")

def to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()

# -------------- UI: Header & Auth ------------
st.title(APP_TITLE)

with st.sidebar:
    st.header("Acesso")
    typed_pass = st.text_input("Senha de admin", type="password",
                               help="Necessária para cadastrar/importar/editar/excluir/exportar.")
    is_admin = (ADMIN_PASS != "" and typed_pass == ADMIN_PASS)
    if ADMIN_PASS and is_admin:
        st.success("Admin autenticado.")
    elif ADMIN_PASS and not is_admin:
        st.caption("Modo público: leitura apenas (QR, detalhes e lista).")
    else:
        st.info("Nenhuma senha configurada (edição aberta). Defina STREAMLIT_ADMIN_PASS em Secrets.")

# Base URL: em produção use sempre o secret BASE_URL; admin pode ajustar manualmente se vazio
with st.sidebar:
    st.header("Configuração de QR")
    if SECRET_BASE_URL:
        base_url = SECRET_BASE_URL
        st.caption(f"BASE_URL (secrets): {base_url}")
    else:
        base_url = st.text_input("Base URL para gerar QR",
                                 value="https://sict-qr-app.streamlit.app/",
                                 help="Defina BASE_URL em Secrets para fixar permanentemente.")

# -------------- Página de Detalhes via ?id=... (pública) --------------
query_params = st.query_params
rec_id = query_params.get("id")
if isinstance(rec_id, list):
    rec_id = rec_id[0]

if rec_id:
    rec = get_trabalho_by_id(rec_id)
    if not rec:
        st.error("Trabalho não encontrado.")
        st.stop()

    st.subheader("Detalhes do Trabalho")
    st.markdown(f"**Título:** {rec['titulo']}")
    st.markdown(f"**Aluno(a):** {rec['aluno']}")
    st.markdown(f"**Orientador:** {rec['orientador']}")
    st.markdown(f"**Áreas:** {rec['areas']}")
    st.markdown(f"**Avaliador 1:** {rec['avaliador1']}")
    st.markdown(f"**Avaliador 2:** {rec['avaliador2']}")
    st.markdown(f"**Nº do Painel:** {rec['painel']}")
    st.caption(f"Cadastrado em: {rec['created_at']}")
    st.stop()

# -------------- Abas (público vs admin) --------------
if is_admin:
    tab_cad, tab_import, tab_lista, tab_export, tab_print = st.tabs(
        ["Cadastrar", "Importar planilha", "Lista & QR", "Exportar", "Etiquetas p/ impressão"]
    )
else:
    (tab_lista,) = st.tabs(["Lista & QR"])

# -------------- Cadastro manual (ADMIN) --------------
if is_admin:
    with tab_cad:
        st.subheader("Cadastro manual")
        with st.form("form_cadastro"):
            aluno = st.text_input("Aluno(a)")
            orientador = st.text_input("Orientador")
            areas = st.text_input("Áreas")
            titulo = st.text_area("Título")
            avaliador1 = st.text_input("Avaliador 1")
            avaliador2 = st.text_input("Avaliador 2")
            painel = st.number_input("Nº do Painel", min_value=0, step=1)
            submitted = st.form_submit_button("Salvar")
            if submitted:
                rec = {
                    "id": str(uuid.uuid4()),
                    "aluno": aluno.strip(),
                    "orientador": orientador.strip(),
                    "areas": areas.strip(),
                    "titulo": titulo.strip(),
                    "avaliador1": avaliador1.strip(),
                    "avaliador2": avaliador2.strip(),
                    "painel": int(painel),
                    "created_at": datetime.datetime.now().isoformat(timespec="seconds")
                }
                insert_trabalho(rec)
                st.success("Registro salvo!")
                st.info(f"Link de detalhes: {build_detail_url(base_url, rec['id'])}")

# -------------- Importar planilha (ADMIN) --------------
if is_admin:
    with tab_import:
        st.subheader("Importar CSV/XLSX")
        up = st.file_uploader("Selecione a planilha", type=["csv", "xlsx"])
        if up is not None:
            df = pd.read_csv(up) if up.name.lower().endswith(".csv") else pd.read_excel(up)
            df = ensure_columns(df)
            st.write("Pré-visualização normalizada:")
            st.dataframe(df.head(20))
            if st.button("Importar tudo"):
                count = 0
                for _, r in df.iterrows():
                    rec = {
                        "id": str(uuid.uuid4()),
                        "aluno": str(r["aluno"]).strip(),
                        "orientador": str(r["orientador"]).strip(),
                        "areas": str(r["areas"]).strip(),
                        "titulo": str(r["titulo"]).strip(),
                        "avaliador1": str(r["avaliador1"]).strip(),
                        "avaliador2": str(r["avaliador2"]).strip(),
                        "painel": int(pd.to_numeric(r["painel"], errors="coerce") if pd.notna(r["painel"]) else 0),
                        "created_at": datetime.datetime.now().isoformat(timespec="seconds")
                    }
                    insert_trabalho(rec)
                    count += 1
                st.success(f"Importados {count} registros.")

# -------------- Lista & QR (PÚBLICO) --------------
# -------------- Lista & QR (PÚBLICO) --------------
with tab_lista:
    st.subheader("Lista + QR")
    df = list_trabalhos()

    # Busca
    q = st.text_input("Buscar por aluno, título, orientador, áreas…")
    if q:
        mask = (
            df["aluno"].str.contains(q, case=False, na=False) |
            df["titulo"].str.contains(q, case=False, na=False) |
            df["orientador"].str.contains(q, case=False, na=False) |
            df["areas"].str.contains(q, case=False, na=False)
        )
        df = df[mask]

    st.dataframe(df)

    st.markdown("---")
    st.subheader("Gerar QRs")
    modo = st.radio("Selecione o modo", ["Individual", "Grade"], horizontal=True)

    # ---- MODO INDIVIDUAL (público) ----
    if modo == "Individual":
        sel_id = st.selectbox("Selecione um ID", options=df["id"].tolist() if not df.empty else [])
        if sel_id:
            url = build_detail_url(base_url, sel_id)
            img = make_qr_image(url)
            st.image(img, caption=url, use_container_width=False)
            st.download_button("Baixar QR (PNG)", data=to_png_bytes(img), file_name=f"qr_{sel_id}.png")

            # Edição/Exclusão: somente admin
            if is_admin:
                with st.expander("Editar / Excluir"):
                    rec = get_trabalho_by_id(sel_id)
                    aluno = st.text_input("Aluno(a)", value=rec["aluno"], key="e_aluno")
                    orientador = st.text_input("Orientador", value=rec["orientador"], key="e_orientador")
                    areas = st.text_input("Áreas", value=rec["areas"], key="e_areas")
                    titulo = st.text_area("Título", value=rec["titulo"], key="e_titulo")
                    avaliador1 = st.text_input("Avaliador 1", value=rec["avaliador1"], key="e_av1")
                    avaliador2 = st.text_input("Avaliador 2", value=rec["avaliador2"], key="e_av2")
                    painel = st.number_input("Nº do Painel", min_value=0, step=1, value=int(rec["painel"]), key="e_painel")

                    c1, c2 = st.columns(2)
                    if c1.button("Salvar alterações"):
                        rec["aluno"] = aluno
                        rec["orientador"] = orientador
                        rec["areas"] = areas
                        rec["titulo"] = titulo
                        rec["avaliador1"] = avaliador1
                        rec["avaliador2"] = avaliador2
                        rec["painel"] = int(painel)
                        update_trabalho(rec)
                        st.success("Atualizado.")
                    if c2.button("Excluir registro", type="primary"):
                        delete_trabalho(sel_id)
                        st.warning("Excluído. Atualize a página.")

    # ---- MODO GRADE (público) ----
    else:
        if df.empty:
            st.info("Nenhum registro para gerar grade.")
        else:
            # seleção múltipla e parâmetros de layout
            ids = st.multiselect(
                "Escolha os trabalhos",
                options=df["id"].tolist(),
                default=df["id"].tolist()[:8],
                help="Selecione os IDs que deseja incluir na grade."
            )
            cols = st.number_input("Cartões por linha (sug.: 3)", min_value=1, max_value=5, value=3)

            if ids:
                rows = (len(ids) + cols - 1) // cols
                for r in range(rows):
                    cset = st.columns(int(cols))
                    for c, idx in enumerate(ids[r*int(cols):(r+1)*int(cols)]):
                        with cset[c]:
                            rec = get_trabalho_by_id(idx)
                            if not rec:
                                continue
                            url = build_detail_url(base_url, idx)
                            img = make_qr_image(url)
                            st.image(img, use_container_width=True)
                            st.caption(f"{rec['aluno']} — Painel {rec['painel']}")
                            st.caption(rec['titulo'][:80] + ("..." if len(rec['titulo']) > 80 else ""))
                            st.download_button("QR (PNG)", data=to_png_bytes(img), file_name=f"qr_{idx}.png")


# -------------- Exportar (ADMIN) --------------
if is_admin:
    with tab_export:
        st.subheader("Exportar CSV")
        df = list_trabalhos()
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Baixar CSV", data=csv, file_name="trabalhos_export.csv")

# -------------- Etiquetas / Cartões (ADMIN) --------------
if is_admin:
    with tab_print:
        st.subheader("Cartões com QR para impressão")
        df = list_trabalhos()
        ids = st.multiselect("Escolha os trabalhos", options=df["id"].tolist(), default=df["id"].tolist()[:8])
        cols = st.number_input("Cartões por linha (sug.: 3)", min_value=1, max_value=5, value=3)
        if ids:
            rows = (len(ids) + cols - 1) // cols
            for r in range(rows):
                cset = st.columns(int(cols))
                for c, idx in enumerate(ids[r*int(cols):(r+1)*int(cols)]):
                    with cset[c]:
                        rec = get_trabalho_by_id(idx)
                        url = build_detail_url(base_url, idx)
                        img = make_qr_image(url)
                        st.image(img, use_container_width=True)
                        st.caption(f"{rec['aluno']} — Painel {rec['painel']}")
                        st.caption(rec['titulo'][:80] + ("..." if len(rec['titulo']) > 80 else ""))
                        st.download_button("QR (PNG)", data=to_png_bytes(img), file_name=f"qr_{idx}.png")




