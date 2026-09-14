# funzioni.py

import oracledb
import pandas as pd
import streamlit as st


def get_oracle_connection():
    oracledb.init_oracle_client(lib_dir=r"C:\Oracle\instantclient_23_0")

    return oracledb.connect(
        user="DWH",
        password="DWH",
        dsn="10.4.128.12:1522/EXTBOARD"
    )


@st.cache_data(ttl=300)
def load_prime_visite():
    conn = get_oracle_connection()

    query = """
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
             FROM DWH.STOR_CCE_PRIMEVISITE
         """

    df = pd.read_sql(query, conn)
    conn.close()

    return df


def calcola_sede(row):
    if pd.notna(row["TIPOTUMORE"]):
        return row["TIPOTUMORE"]

    if (
        pd.notna(row["STANZA"])
        and "BLOCCO E - SECONDO PIANO - STANZA 4"
        in str(row["STANZA"]).upper()
    ):
        return "Fase I"

    if pd.notna(row["Valore Sede_x"]):
        return row["Valore Sede_x"]

    if pd.notna(row["Valore Sede_y"]):
        return row["Valore Sede_y"]

    return "Completare Dizionario"


def load_dataset():
    # tutto il tuo codice attuale di caricamento,
    # merge e trasformazione
   # Dizionari
    diz_agende = pd.read_excel("data/diz_agende.xlsx")
    diz_diagnosi1 = pd.read_excel("data/diz_diagnosi1.xlsx")
    diz_validitàriga = pd.read_excel("data/diz_validitàriga.xlsx")

    df_prime_visite = load_prime_visite()

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

    amb_agenda_l_diagnosi["ORD INTERNO/ESTERNO"] = (
        amb_agenda_l_diagnosi["INTERNO/ESTERNO"].map({
            "Interno": 1,
            "Esterno": 2,
            "Non noto": 3
        })
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

