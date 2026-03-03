import streamlit as st
import pandas as pd
import io
import numpy as np
import os
from difflib import SequenceMatcher

st.set_page_config(page_title="Isis Data Cleaning Pro", layout="wide")

# Fonction de similarité
def get_similarity(a, b):
    return SequenceMatcher(None, str(a), str(b)).ratio()

st.title("📂 Isis Data Cleaning - Analyseur Expert")

# --- 1. LÉGENDE ---
st.subheader("Légende des couleurs")
l1, l2, l3, l4 = st.columns(4)
l1.info("🔵 **Bleu** : Original interne")
l2.error("🔴 **Rouge** : Doublon d'adresse")
l3.warning("🟠 **Orange** : Nom similaire")
l4.success("🟢 **Vert** : Présent dans l'Annuaire")

# --- 2. RÉFÉRENTIEL LOCAL ---
REF_FILE = "annuaire_comparaison.csv"

@st.cache_data
def load_reference_data(file_path):
    if os.path.exists(file_path):
        df_ref = pd.read_csv(file_path, low_memory=False)
        num_v = df_ref["numeroVoieEtablissement"].fillna("").astype(str).str.replace(r'\.0$', '', regex=True)
        typ_v = df_ref["typeVoieEtablissement"].fillna("").astype(str)
        lib_v = df_ref["libelleVoieEtablissement"].fillna("").astype(str)
        df_ref["addr_ref"] = (num_v + " " + typ_v + " " + lib_v).str.strip().str.upper().str.replace(r'\s+', ' ', regex=True)
        df_ref["nom_ref"] = df_ref["denominationUsuelleEtablissement"].astype(str).str.strip().str.upper()
        df_ref["siren_str"] = df_ref["siren"].astype(str).str.zfill(9) 
        return df_ref
    return None

df_ref = load_reference_data(REF_FILE)

# --- 3. TRAITEMENT ---
uploaded_isis = st.file_uploader("Charger le fichier ISIS (CSV)", type=["csv"])

if uploaded_isis is not None and df_ref is not None:
    file_name_no_ext = uploaded_isis.name.rsplit('.', 1)[0]
    
    try:
        df_isis = pd.read_csv(uploaded_isis, encoding='WINDOWS-1252', sep=";")
        
        if st.button("🚀 Lancer l'analyse complète"):
            
            # Préparation
            df_final = df_isis.drop(columns=['projet']) if 'projet' in df_isis.columns else df_isis.copy()
            df_final['Nom_Norm'] = df_final['Nom du client'].astype(str).str.strip().str.upper()
            df_final['Addr_Norm'] = df_final['Adresse'].astype(str).str.strip().str.upper().str.replace(r'\s+', ' ', regex=True)
            df_final["tel_clean"] = df_final["Téléphone"].astype(str).str.replace(r'\D', '', regex=True)
            
            df_final["dupliquer"] = False
            df_final["nom_ressemblant"] = False
            df_final["num_dupliquer"] = False
            df_final["is_first_occurrence"] = False
            df_final["deja_dans_annuaire"] = False
            df_final["Group_ID"] = df_final.index

            # Comparaison Annuaire
            df_match_nom = df_ref[['nom_ref', 'siren_str', 'etatAdministratifEtablissement']].drop_duplicates('nom_ref')
            df_final = pd.merge(df_final, df_match_nom, left_on="Nom_Norm", right_on="nom_ref", how="left")
            df_match_addr = df_ref[['addr_ref', 'siren_str', 'etatAdministratifEtablissement']].drop_duplicates('addr_ref')
            df_final = pd.merge(df_final, df_match_addr, left_on="Addr_Norm", right_on="addr_ref", how="left", suffixes=('', '_addr'))
            
            df_final["siren_final"] = df_final["siren_str"].fillna(df_final["siren_str_addr"])
            df_final["etat_final"] = df_final["etatAdministratifEtablissement"].fillna(df_final["etatAdministratifEtablissement_addr"])
            df_final["deja_dans_annuaire"] = df_final["siren_final"].notna()
            df_final["Ouverte"] = (df_final["deja_dans_annuaire"]) & (df_final["etat_final"] == "A")
            df_final["lien_annuaire"] = np.where(df_final["deja_dans_annuaire"], 
                "https://annuaire-entreprises.data.gouv.fr/entreprise/" + df_final["siren_final"], "Non dispo")

            # Doublons Internes
            addr_to_orig = {}
            names_vus = [] 
            for index, row in df_final.iterrows():
                if row["tel_clean"] not in ["", "nan"]:
                    df_final.at[index, "num_dupliquer"] = df_final.duplicated(subset=["tel_clean"], keep='first')[index]

                m_addr = addr_to_orig.get(row['Addr_Norm'])
                m_name = None
                if row['Nom_Norm'] not in ["", "NAN"]:
                    for idx_orig, n_vu in names_vus:
                        if get_similarity(row['Nom_Norm'], n_vu) >= 0.9:
                            m_name = idx_orig
                            break

                if m_addr is not None:
                    df_final.at[index, 'dupliquer'] = True
                    df_final.at[index, 'Group_ID'] = m_addr
                    df_final.at[m_addr, 'is_first_occurrence'] = True
                elif m_name is not None:
                    df_final.at[index, 'nom_ressemblant'] = True
                    df_final.at[index, 'Group_ID'] = m_name
                    df_final.at[m_name, 'is_first_occurrence'] = True
                else:
                    addr_to_orig[row['Addr_Norm']] = index
                    if row['Nom_Norm'] not in ["", "NAN"]:
                        names_vus.append((index, row['Nom_Norm']))

            df_final['Original_Order'] = df_final.index
            df_final = df_final.sort_values(by=['Group_ID', 'Original_Order'])

            # --- 4. SECTION STATISTIQUES (RÉTABLIE) ---
            st.divider()
            st.subheader("📊 Statistiques de l'Analyse")
            s1, s2, s3, s4 = st.columns(4)
            
            s1.metric("Doublons d'Adresses", f"{df_final['dupliquer'].sum()}", delta_color="inverse")
            s2.metric("Similitudes de Noms", f"{df_final['nom_ressemblant'].sum()}")
            s3.metric("Doublons Téléphone", f"{df_final['num_dupliquer'].sum()}")
            s4.metric("Trouvés dans l'Annuaire", f"{df_final['deja_dans_annuaire'].sum()}", delta="OK")

            # Export Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                cols_tech = ['Nom_Norm', 'Addr_Norm', 'tel_clean', 'nom_ref', 'addr_ref', 'siren_str', 
                             'siren_str_addr', 'etatAdministratifEtablissement', 
                             'etatAdministratifEtablissement_addr', 'Group_ID', 'Original_Order', 
                             'is_first_occurrence', 'siren_final', 'etat_final']
                df_export = df_final.drop(columns=[c for c in cols_tech if c in df_final.columns])
                df_export.to_excel(writer, index=False, sheet_name='Analyse')
            
            st.download_button("📥 Télécharger les résultats", data=buffer.getvalue(), 
                               file_name=f"{file_name_no_ext}_final.xlsx")

            # Affichage
            df_display = df_final.copy()
            for c in ["dupliquer", "nom_ressemblant", "num_dupliquer", "deja_dans_annuaire"]:
                df_display[c] = df_display[c].astype(str)

            def style_rows(row):
                idx = row.name
                if df_final.loc[idx, "deja_dans_annuaire"]:
                    return ['background-color: rgba(40, 167, 69, 0.15)'] * len(row)
                if df_final.loc[idx, "dupliquer"]:
                    return ['background-color: rgba(220, 53, 69, 0.20)'] * len(row)
                if df_final.loc[idx, "nom_ressemblant"]:
                    return ['background-color: rgba(255, 193, 7, 0.25)'] * len(row)
                if df_final.loc[idx, "is_first_occurrence"]:
                    return ['background-color: rgba(0, 123, 255, 0.15)'] * len(row)
                return [''] * len(row)

            cols_show = [c for c in df_display.columns if c not in cols_tech]
            st.dataframe(
                df_display.style.apply(style_rows, axis=1), 
                column_order=cols_show,
                use_container_width=True, height=600,
                column_config={"lien_annuaire": st.column_config.LinkColumn("Lien Annuaire", display_text="Consulter la fiche")}
            )

    except Exception as e:
        st.error(f"Erreur : {e}")