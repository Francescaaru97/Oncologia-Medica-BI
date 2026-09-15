import streamlit as st
from   pathlib import Path
import pandas as pd
import plotly.express as px
from   datetime import datetime

#py esterno
import funzioni as f

# =====================================================================
# CONFIGURAZIONE STREAMLIT
# =====================================================================

st.set_page_config(
    page_title="Oncologia Medica BI",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =====================================================================
# THEME / CSS
# =====================================================================

CSS_PATH = Path(__file__).parent / "styles" / "style.css"

@st.cache_data
def load_css():
    return CSS_PATH.read_text(encoding="utf-8")

def apply_styles():
    st.markdown(
        f"<style>{load_css()}</style>",
        unsafe_allow_html=True,
    )

apply_styles()

#creo le due tabelle
df_finale = f.load_dataset()
df_calendario = f.load_calendario()

# =====================================================================
# AUTENTICAZIONE UTENTE
# =====================================================================

def authenticate_user(username, password):
    connection = f.get_oracle_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT
                UTENTE_ID,
                USERNAME,
                PASSWORD_HASH,
                RUOLO,
                NOME,
                COGNOME,
                EMAIL
            FROM CPBI_UTENTI
            WHERE UPPER(USERNAME) = UPPER(:username)
              AND PASSWORD_HASH = :password
              AND FLG_ATTIVO = 1
            """,
            {
                "username": username,
                "password": password,
            }
        )

        return cursor.fetchone()
    finally:
        connection.close()

# =====================================================================
# SESSION STATE
# =====================================================================

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "username" not in st.session_state:
    st.session_state.username = None

if "role" not in st.session_state:
    st.session_state.role = None

if "first_name" not in st.session_state:
    st.session_state.first_name = None

if "last_name" not in st.session_state:
    st.session_state.last_name = None

if "email" not in st.session_state:
    st.session_state.email = None

# =====================================================================
# LOGIN
# =====================================================================

if not st.session_state.authenticated:
    #st.markdown('<div class="login-box">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:
        st.markdown( """
            <div class="login-title"><h1>Oncologia Medica BI </h1></div>
            """,
            unsafe_allow_html=True
        )

        st.write("")
        st.write("")

        username = st.text_input("Username",placeholder="Inserisci username",key="login_username")
        password = st.text_input("Password",type="password",placeholder="Inserisci password",key="login_password")
        st.write("")

        if st.button("Accedi",use_container_width=True,type="primary"):
            if not username or not password:
                st.warning("Inserisci username e password.")
            else:
                try:
                    user = authenticate_user(username,password)
                    if user is None:
                        st.error("Username o password non corretti.")
                    else:
                        # -------------------------------------------------
                        # UTENTE TROVATO IN CPBI_UTENTI
                        # -------------------------------------------------
                        st.session_state.authenticated = True
                        st.session_state.user_id = user[0]
                        st.session_state.username = user[1]
                        st.session_state.role = user[3]
                        st.session_state.first_name = user[4]
                        st.session_state.last_name = user[5]
                        st.session_state.email = user[6]
                        st.rerun()

                except Exception as e:
                    st.error(f"Errore di connessione/autenticazione Oracle: {e}")

        st.write("")
        st.caption("Accesso riservato agli utenti autorizzati.")

    # se non autenticato, il resto dell'app NON viene eseguito
    st.stop()

# =====================================================================
# DA QUI IN POI L'UTENTE È AUTENTICATO
# =====================================================================

# =====================================================================
# HEADER / PAGINE
# =====================================================================

if "page" not in st.session_state:
    st.session_state.page = "Dashboard"
    
if "selected_stay" not in st.session_state:
    st.session_state.selected_stay = None

with st.sidebar:
    st.markdown("## Oncologia Medica BI")

# ---------------------------------------------------------------
# PAGINE
# ---------------------------------------------------------------
    st.divider()

    if st.session_state.page != "Dettaglio ricovero":
        st.markdown('<div class="sidebar-section-title">Pagine</div><br>',unsafe_allow_html=True)
        page = st.radio(
            "",
            ["Dashboard", "Dettaglio Sottocategoria"],
            label_visibility="collapsed"
        )
        st.session_state.page = page
        st.divider()

    page = st.session_state.page

# ---------------------------------------------------------------
# INFORMAZIONI UTENTE -> UTENTE CONNESSO
# ---------------------------------------------------------------

    st.markdown('<div class="sidebar-section-title">Utente connesso</div><br>',unsafe_allow_html=True)

    nome_visualizzato = (
        f"{st.session_state.first_name or ''} "
        f"{st.session_state.last_name or ''}"
    ).strip()

    if nome_visualizzato:
        st.write(nome_visualizzato)
    else:
        st.write(st.session_state.username)

    st.caption(f"Username: {st.session_state.username}")
    st.caption(f"Ruolo: {st.session_state.role}")
    st.divider()

    # ---------------------------------------------------------------
    # LOGOUT
    # ---------------------------------------------------------------

    if st.button("Esci", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.username = None
        st.session_state.role = None
        st.session_state.first_name = None
        st.session_state.last_name = None
        st.session_state.email = None

        st.rerun()

# =====================================================================
# HEADER PRINCIPALE
# =====================================================================

st.title("Oncologia Medica BI")
st.divider()

# =====================================================================
# CREAZIONE TABELLA COMPLETA
# =====================================================================
    
completa = df_finale.merge(
    df_calendario,
    left_on="FK_CALENDARIO",
    right_on="DATA",
    how="left"
)

anno_corrente = datetime.now().year
anno_default = anno_corrente 
anni = sorted(completa["ANNO"].dropna().astype(int).unique(), reverse=True)

df_filtrato = completa.copy()
col1, col2, col3 = st.columns(3)

with col1:
    anno = st.selectbox(
        "Anno",
        anni,
        index=anni.index(anno_default) if anno_default in anni else 0
    )

#serve per ordinare la colonna NOME_MESE per la colonna MESE
mesi_ordinati = (
    completa[["MESE", "NOME_MESE"]]
    .dropna(subset=["NOME_MESE"])
    .drop_duplicates()
    .sort_values("MESE")
)
ordine_mesi = mesi_ordinati["NOME_MESE"].tolist()

with col2:
    mese = st.selectbox(
        "Mese",
        ["Tutti"] + mesi_ordinati["NOME_MESE"].tolist()
    )

with col3:
    sede = st.selectbox(
        "Sede",
        ["Tutte"] + sorted(completa["Sede"].dropna().unique())
    )

    # Applicazione filtri
df_filtrato = df_filtrato[df_filtrato["ANNO"] == anno]
if mese != "Tutti":
    df_filtrato = df_filtrato[df_filtrato["NOME_MESE"] == mese]
if sede != "Tutte":
    df_filtrato = df_filtrato[df_filtrato["Sede"] == sede]

# =====================================================================
# DASHBOARD
# =====================================================================
if page == "Dashboard": 

# Pivot per FONTE e mese ---------------------------------------------------------
    tabellaFonte = pd.pivot_table(
        df_filtrato,
        index="Provenienza Fonte",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabellaFonte = tabellaFonte.reindex(columns=ordine_mesi,fill_value=0)
    f.mostra_tabella_pivot(tabellaFonte)

# Pivot per INTERNO/ESTERNO e per Mese ----------------------------------------------
    tabella_INT_EST = pd.pivot_table(
        df_filtrato,
        index="INTERNO/ESTERNO",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabella_INT_EST = tabella_INT_EST.reindex(columns=ordine_mesi,fill_value=0)
    #ordinamento colonna INTERNO/ESTERNO per ORD INTERNO/ESTERNO
    ordine_int_est = (
        df_filtrato[
            ["INTERNO/ESTERNO", "ORD INTERNO/ESTERNO"]
        ]
        .drop_duplicates()
        .sort_values("ORD INTERNO/ESTERNO")
        ["INTERNO/ESTERNO"]
        .tolist()
    )
    tabella_INT_EST = tabella_INT_EST.reindex(ordine_int_est,fill_value=0)
    f.mostra_tabella_pivot(tabella_INT_EST)

# Pivot per SECOND_OPINION e per Mese ----------------------------------------------
    tabella_SECOND_OPINION = pd.pivot_table(
        df_filtrato,
        index="Second Opinion",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    #ordinamento colonna Second Opinion per colonna ORD SECOND OPINION
    tabella_SECOND_OPINION = tabella_SECOND_OPINION.reindex(columns=ordine_mesi,fill_value=0)
    ordine_second_opinion = (df_filtrato[["Second Opinion", "ORD SECOND OPINION"]]
        .drop_duplicates()
        .sort_values("ORD SECOND OPINION")
        ["Second Opinion"]
        .tolist()
    )
    tabella_SECOND_OPINION = tabella_SECOND_OPINION.reindex(ordine_second_opinion,fill_value=0)
    f.mostra_tabella_pivot(tabella_SECOND_OPINION)

# Pivot per VALORI_LINEA e per Mese ----------------------------------------------
    tabella_Linea = pd.pivot_table(
        df_filtrato,
        index="Linea",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabella_Linea = tabella_Linea.reindex(columns=ordine_mesi,fill_value=0)
    ordine_linea = (df_filtrato[["Linea", "ORD LINEA"]]
        .drop_duplicates()
        .sort_values("ORD LINEA")
        ["Linea"]
        .tolist()
    )
    tabella_Linea = tabella_Linea.reindex(ordine_linea,fill_value=0)
    f.mostra_tabella_pivot_totaliriga(tabella_Linea)

# Pivot per Stadio e per Mese ----------------------------------------------
    tabella_Stadio = pd.pivot_table(
        df_filtrato,
        index="Stadio",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabella_Stadio = tabella_Stadio.reindex(columns=ordine_mesi,fill_value=0)
    f.mostra_tabella_pivot(tabella_Stadio)

# Pivot per Destinazione e per Mese ----------------------------------------------
    tabella_Destinazione = pd.pivot_table(
        df_filtrato,
        index="Destinazione",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabella_Destinazione = tabella_Destinazione.reindex(columns=ordine_mesi,fill_value=0)
    f.mostra_tabella_pivot(tabella_Destinazione)

# Pivot per Studio e per Mese ----------------------------------------------
    tabella_Studio = pd.pivot_table(
        df_filtrato,
        index="Studio",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabella_Studio = tabella_Studio.reindex(columns=ordine_mesi,fill_value=0)
    ordine_Studio = (df_filtrato[["Studio", "ORD STUDIO"]]
        .drop_duplicates()
        .sort_values("ORD STUDIO")
        ["Studio"].tolist()
    )
    tabella_Studio = tabella_Studio.reindex(ordine_Studio,fill_value=0)
    f.mostra_tabella_pivot(tabella_Studio)

# Pivot per Sede e per Mese ----------------------------------------------
    tabella_Sede = pd.pivot_table(
        df_filtrato,
        index="Sede",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabella_Sede = tabella_Sede.reindex(columns=ordine_mesi,fill_value=0)
    f.mostra_tabella_pivot_totaliriga(tabella_Sede)

# =====================================================================
# DETTAGLIO SOTTOCATEGORIA
# =====================================================================

if page == "Dettaglio Sottocategoria": 
    tabella_Sottocategoria = pd.pivot_table(
        df_filtrato,
        index="Sottocategoria",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0,
        margins=True,
        margins_name="Totale"
    )

    # Ordine dei mesi + Totale alla fine
    tabella_Sottocategoria = tabella_Sottocategoria.reindex(
        columns=ordine_mesi + ["Totale"],
        fill_value=0
    )

    # Stile: grassetto per riga Totale e colonna Totale
    tabella_styled = (
        tabella_Sottocategoria.style
        .set_properties(
            subset=pd.IndexSlice[:, ["Totale"]],
            **{"font-weight": "bold"}
        )
        .set_properties(
            subset=pd.IndexSlice[["Totale"], :],
            **{"font-weight": "bold"}
        )
    )

    # Visualizzazione
    st.dataframe(
        tabella_styled,
        use_container_width=True,
        height=1400,
        column_config={
            # Prima colonna (indice Sottocategoria)
            "_index": st.column_config.Column(
                width=600
            ),

            # Colonne mesi e Totale
            **{
                col: st.column_config.Column(
                    width=60
                )
                for col in tabella_Sottocategoria.columns
            }
        }
    )

    st.write("")