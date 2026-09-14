import streamlit as st
import oracledb
from   pathlib import Path
import pandas as pd
import plotly.express as px
from   datetime import datetime

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

# =====================================================================
# CONNESSIONE ORACLE
# =====================================================================

def get_oracle_connection():
    oracledb.init_oracle_client(lib_dir=r"C:\Oracle\instantclient_23_0")
    
    return oracledb.connect(
        user="DWH",
        password="DWH",
        dsn="10.4.128.12:1522/EXTBOARD"
    )

    # return oracledb.connect(
    #     user="1",
    #     password="2",
    #     dsn="path/boh"
    # )


def calcola_sede(row):

    if pd.notna(row["TIPOTUMORE"]):
        return row["TIPOTUMORE"]
    
    if (
        pd.notna(row["STANZA"])
        and "BLOCCO E - SECONDO PIANO - STANZA 4" in str(row["STANZA"]).upper()
    ):
        return "Fase I"

    if pd.notna(row["Valore Sede_x"]):
        return row["Valore Sede_x"]
    
    if pd.notna(row["Valore Sede_y"]):
        return row["Valore Sede_y"]
    return "Completare Dizionario"

@st.cache_data(ttl=300)
def load_prime_visite():
    connection = get_oracle_connection()
    try:
        df = pd.read_sql("""
            SELECT  \
            KEY_ABM, QUERY, DATA_CUP, TIMESTAMPINSERT,  \
            DS_PRESTAZIONE, NUMERO_PRENOTAZIONE,   \
            STANZA, CD_AGENDA, RECID,  IDANAG, MODULO_CCE, VISITNUMBER,   \
            AUTHOR_INSERT,  \
            case when "stadio_malattia" is null then 'Non noto' \
                 when "stadio_malattia" = '' then 'Non noto' \
            else "stadio_malattia" end as STADIO_MALATTIA ,  \
            CASE WHEN TIPOTUMORE = 'Gastroenterica' THEN 'Gastro-entero-bilio-pancreatica'  \
            WHEN TIPOTUMORE = 'Fegato e vie biliari' THEN 'Gastro-entero-bilio-pancreatica'  \
            ELSE TIPOTUMORE end as TIPOTUMORE,  \
            DIAGNOSI_1LIV, DIAGNOSI_2LIV,  \
            case when LINEA is null then 'Non noto' \
                 when LINEA = '' then 'Non noto' \
            else LINEA end as LINEA,  \
            PROVENIENZA, ALTRO_CENTRO, ALTRO_CENTRO_DES, PROSECUZIONE, \
            CANDIDATO_PROTOCOLLO, NUM_PROTOCOLLO  \
            FROM DWH.STOR_ABM_PRIMEVISITE
            """
            ,
            connection
        )
        return df
    finally:
        connection.close()

# =====================================================================
# CARICAMENTO DATI
# =====================================================================

@st.cache_data
def load_dataset():

    connection = get_oracle_connection()

    try:
        df_prime_visite = load_prime_visite()

    finally:
        connection.close()

    # Dizionari
    diz_agende = pd.read_excel("data/diz_agende.xlsx")
    diz_diagnosi1 = pd.read_excel("data/diz_diagnosi1.xlsx")
    diz_validitàriga = pd.read_excel("data/diz_validitàriga.xlsx")

    # Join agenda
    amb_l_agenda = df_prime_visite.merge(
        diz_agende,
        left_on="CD_AGENDA",
        right_on="Agenda",
        how="left"
    )

    # Join diagnosi
    amb_agenda_l_diagnosi = amb_l_agenda.merge(
        diz_diagnosi1,
        left_on="DIAGNOSI_1LIV",
        right_on="Diagnosi 1 ",
        how="left"
    )

    # Trasformazioni
    amb_agenda_l_diagnosi["INTERNO/ESTERNO"] = \
        amb_agenda_l_diagnosi["PROVENIENZA"].apply(
            lambda x: "Interno"
            if x == "INT"
            else ("Non noto" if pd.isna(x) else "Esterno")
        )

    amb_agenda_l_diagnosi["Second Opinion"] = \
        amb_agenda_l_diagnosi["ALTRO_CENTRO"].apply(
            lambda x: "Si"
            if pd.notna(x) and "NO - Second opinion" in str(x)
            else (
                "Non Noto"
                if pd.isna(x) or str(x).strip() == ""
                else "No"
            )
        )

    amb_agenda_l_diagnosi["Destinazione"] = \
        amb_agenda_l_diagnosi["PROSECUZIONE"].apply(
            lambda x: "Altrove"
            if pd.notna(x) and "ALTROVE" in str(x).upper()
            else (
                "INT"
                if pd.notna(x) and "INT" in str(x).upper()
                else "Non Noto"
            )
        )

    amb_agenda_l_diagnosi["Studio"] = \
        amb_agenda_l_diagnosi["CANDIDATO_PROTOCOLLO"].fillna("Non Noto")

    amb_agenda_l_diagnosi["Provenienza Fonte"] = \
        amb_agenda_l_diagnosi["QUERY"].apply(
            lambda x: "CUP prima visita"
            if x == 4
            else "Maschera CCE"
        )

    amb_agenda_l_diagnosi["Sede"] = \
        amb_agenda_l_diagnosi.apply(calcola_sede, axis=1)

    amb_agenda_l_diagnosi["Sottocategoria"] = \
        amb_agenda_l_diagnosi["DIAGNOSI_2LIV"].str.split("#").str[0]

    amb_agenda_l_diagnosi["FK_SedeSottocategoria"] = (
        amb_agenda_l_diagnosi["Sede"].fillna("")
        + "_"
        + amb_agenda_l_diagnosi["Sottocategoria"].fillna("")
    )

    finale = amb_agenda_l_diagnosi.merge(
        diz_validitàriga,
        left_on="FK_SedeSottocategoria",
        right_on="Key_Val_Riga",
        how="left"
    )

    finale["Valore_Validità"] = \
        finale["Valore_Validità"].fillna("Non Noto")

    finale.rename(
        columns={
            "LINEA": "Linea",
            "PROVENIENZA": "Provenienza",
            "STADIO_MALATTIA": "Stadio",
            "Valore_Validità": "Valore_Validità_Riga"
        },
        inplace=True
    )

    finale.drop(
        columns=[
            "Valore Sede_x",
            "Valore Sede_y"
        ],
        errors="ignore",
        inplace=True
    )

    #normalizzo la DATA_CUP e TIMESTAMPINSERT
    finale["DATA_CUP"] = pd.to_datetime(finale["DATA_CUP"]).dt.normalize()
    finale["TIMESTAMPINSERT"] = pd.to_datetime(finale["TIMESTAMPINSERT"]).dt.normalize()

    return finale 
df_finale = load_dataset()


def load_calendario():
    calendario = pd.DataFrame({
        "DATA": pd.date_range(
            start="2024-12-01",
            end="2035-12-31",
            freq="D"
        )
    })

    calendario["ANNO"] = calendario["DATA"].dt.year
    calendario["MESE"] = calendario["DATA"].dt.month
    calendario["NOME_MESE"] = calendario["DATA"].dt.month_name(locale="it_IT")
    calendario["TRIMESTRE"] = calendario["DATA"].dt.quarter

    calendario["DATA"] = pd.to_datetime(calendario["DATA"]).dt.normalize()
    return calendario

df_calendario = load_calendario()

#capire come forzare la prima colonna ad una grandezza esatta. in modo che tutte le tabelle siano allineate
def mostra_tabella_pivot(df, titolo=None):
    if titolo:
        st.subheader(titolo)

    df = df.copy()

    # Totale di riga
    df["Totale"] = df.select_dtypes(include="number").sum(axis=1)

    # Grassetto sulla colonna Totale
    df_styled = df.style.set_properties(
        subset=["Totale"],
        **{"font-weight": "bold"}
    )

    st.dataframe(
        df_styled,
        use_container_width=True,
        hide_index=False,
        column_config={
            col: st.column_config.Column(width="small")
            for col in df.columns
        }
    )


# =====================================================================
# AUTENTICAZIONE UTENTE
# =====================================================================

def authenticate_user(username, password):
    connection = get_oracle_connection()
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
    st.markdown("<br><br>", unsafe_allow_html=True)
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
        st.markdown("**Pagine**")
        page = st.radio(
            "",
            ["Dashboard", "Dettaglio Sottocategoria"],
            label_visibility="collapsed"
        )
        st.session_state.page = page
        st.divider()

    page = st.session_state.page

# ---------------------------------------------------------------
# INFORMAZIONI UTENTE
# ---------------------------------------------------------------

    st.markdown("**Utente connesso**")

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
# DASHBOARD
# =====================================================================

#if page == "Dashboard":
completa = df_finale.merge(
    df_calendario,
    left_on="DATA_CUP",
    right_on="DATA",
    how="left"
)

anno_corrente = datetime.now().year
anno_default = anno_corrente - 1
anni = sorted(completa["ANNO"].dropna().astype(int).unique())

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

if page == "Dashboard":

# Tabella dati COMPLETI ---------------------------------------------------------
    st.dataframe(
        df_filtrato,
        use_container_width=True,
        hide_index=True,
        height=300
    )

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
    mostra_tabella_pivot(tabellaFonte)

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
    mostra_tabella_pivot(tabella_INT_EST)

# Pivot per SECOND_OPINION e per Mese ----------------------------------------------
    tabella_INT_EST = pd.pivot_table(
        df_filtrato,
        index="Second Opinion",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabella_INT_EST = tabella_INT_EST.reindex(columns=ordine_mesi,fill_value=0)
    mostra_tabella_pivot(tabella_INT_EST)

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
    mostra_tabella_pivot(tabella_Linea)

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
    mostra_tabella_pivot(tabella_Stadio)

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
    mostra_tabella_pivot(tabella_Destinazione)

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
    mostra_tabella_pivot(tabella_Studio)

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
    mostra_tabella_pivot(tabella_Sede)

if page == "Dettaglio Sottocategoria": 

    tabella_Sottocategoria = pd.pivot_table(
        df_filtrato,
        index="Sottocategoria",
        columns="NOME_MESE",
        values="KEY_ABM",
        aggfunc="count",
        fill_value=0
    )

    tabella_Sottocategoria  = tabella_Sottocategoria .reindex(columns=ordine_mesi,fill_value=0)
    mostra_tabella_pivot(tabella_Sottocategoria)

    st.write("")

