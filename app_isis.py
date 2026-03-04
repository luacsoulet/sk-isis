import streamlit as st
import pandas as pd
import io
import os
import pickle
from difflib import SequenceMatcher

st.set_page_config(page_title="Isis Cleaning - Persistence", layout="wide")

def get_similarity(a, b):
    return SequenceMatcher(None, str(a), str(b)).ratio()

# --- 1. LOGIQUE DE PERSISTANCE (Simulation LocalStorage) ---
CACHE_DIR = "cache_nettoyage"
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def get_cache_path(filename):
    """Crée un chemin de fichier unique pour le cache"""
    return os.path.join(CACHE_DIR, f"cache_{filename}.pkl")

def save_to_disk():
    """Sauvegarde le DataFrame actuel sur le disque"""
    if "current_file" in st.session_state and "df_processed" in st.session_state:
        path = get_cache_path(st.session_state.current_file)
        with open(path, "wb") as f:
            pickle.dump(st.session_state.df_processed, f)

def load_from_disk(filename):
    """Charge le cache si il existe"""
    path = get_cache_path(filename)
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    return None

# --- 2. CALLBACKS ---
def handle_editor_change():
    if "main_editor" in st.session_state:
        changes = st.session_state["main_editor"]["edited_rows"]
        for row_idx_str, updated_values in changes.items():
            row_idx = int(row_idx_str)
            actual_index = st.session_state.df_processed.index[row_idx]
            if "Traité" in updated_values:
                st.session_state.df_processed.at[actual_index, "Traité"] = updated_values["Traité"]
        # Sauvegarde automatique sur le disque après chaque clic
        save_to_disk()

def reset_state():
    # Optionnel : décommenter pour supprimer le cache au changement de fichier
    # if "current_file" in st.session_state:
    #    path = get_cache_path(st.session_state.current_file)
    #    if os.path.exists(path): os.remove(path)
    if "df_processed" in st.session_state:
        del st.session_state.df_processed

st.title("📂 Isis Cleaning - Mode Persistant")

# --- 3. LÉGENDE ---
l1, l2, l3, l4 = st.columns(4)
l1.info("🔵 **Bleu** : Original")
l2.error("🔴 **Rouge** : Doublon Adresse")
l3.warning("🟠 **Orange** : Nom Similaire")
l4.markdown('<p style="background-color:rgba(255, 20, 147, 0.25); padding:10px; border-radius:5px; border: 1px solid pink;">💗 <b>Rose</b> : Doublon Téléphone</p>', unsafe_allow_html=True)

# --- 4. IMPORT ---
uploaded_file = st.file_uploader("Charger le fichier ISIS", type=["csv"], on_change=reset_state)

if uploaded_file is not None:
    filename = uploaded_file.name
    st.session_state.current_file = filename

    # On vérifie si un cache existe déjà pour ce fichier sur le disque
    if "df_processed" not in st.session_state:
        cached_data = load_from_disk(filename)
        
        if cached_data is not None:
            st.session_state.df_processed = cached_data
            st.success(f"✅ Session restaurée pour : {filename}")
        else:
            with st.spinner("Analyse initiale..."):
                df = pd.read_csv(uploaded_file, encoding='WINDOWS-1252', sep=";")
                df_final = df.drop(columns=['projet']) if 'projet' in df.columns else df.copy()
                
                # Nettoyage & Normalisation
                df_final['Nom_Norm'] = df_final['Nom du client'].astype(str).str.strip().str.upper()
                df_final['Addr_Norm'] = df_final['Adresse'].astype(str).str.strip().str.upper().str.replace(r'\s+', ' ', regex=True)
                df_final["tel_clean"] = df_final["Téléphone"].astype(str).str.replace(r'\D', '', regex=True)
                
                df_final["dupliquer"], df_final["nom_ressemblant"] = False, False
                df_final["num_dupliquer"], df_final["is_first"] = False, False
                df_final["Group_ID"] = df_final.index
                df_final["Traité"] = False

                addr_map, tel_map, names_vus = {}, {}, []
                for idx, row in df_final.iterrows():
                    t, a, n = row["tel_clean"], row['Addr_Norm'], row['Nom_Norm']
                    # Logique Tel + Première occurrence
                    if t not in ["", "nan"]:
                        if t in tel_map:
                            df_final.at[idx, "num_dupliquer"] = True
                            df_final.at[idx, "Group_ID"] = tel_map[t]
                            df_final.at[tel_map[t], "is_first"] = True
                        else: tel_map[t] = idx
                    # Logique Adresse + Nom
                    m_addr = addr_map.get(a)
                    m_name = None
                    if n not in ["", "NAN"]:
                        for i, v in names_vus:
                            if get_similarity(n, v) >= 0.9: m_name = i; break
                    if m_addr is not None:
                        df_final.at[idx, 'dupliquer'], df_final.at[idx, 'Group_ID'] = True, m_addr
                        df_final.at[m_addr, 'is_first'] = True
                    elif m_name is not None:
                        df_final.at[idx, 'nom_ressemblant'], df_final.at[idx, 'Group_ID'] = True, m_name
                        df_final.at[m_name, 'is_first'] = True
                    else:
                        if a not in addr_map: addr_map[a] = idx
                        if n not in ["", "NAN"]: names_vus.append((idx, n))

                df_final = df_final.sort_values(by=['Group_ID', 'Nom du client'])
                st.session_state.df_processed = df_final
                save_to_disk()

    # --- 5. AFFICHAGE ET INTERACTION ---
    df_ref = st.session_state.df_processed
    st.divider()
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Doublons Adresse", df_ref["dupliquer"].sum())
    s2.metric("Doublons Tel", df_ref["num_dupliquer"].sum())
    s3.metric("Similitudes Nom", df_ref["nom_ressemblant"].sum())
    s4.metric("Traitées", df_ref["Traité"].sum())

    def apply_style(row):
        idx = row.name
        if df_ref.loc[idx, "dupliquer"]: return ['background-color: rgba(255, 0, 0, 0.20)'] * len(row)
        if df_ref.loc[idx, "num_dupliquer"]: return ['background-color: rgba(255, 20, 147, 0.20)'] * len(row)
        if df_ref.loc[idx, "nom_ressemblant"]: return ['background-color: rgba(255, 165, 0, 0.25)'] * len(row)
        if df_ref.loc[idx, "is_first"]: return ['background-color: rgba(0, 100, 255, 0.15)'] * len(row)
        return [''] * len(row)

    cols_tech = ['Nom_Norm', 'Addr_Norm', 'tel_clean', 'Group_ID', 'is_first']
    df_to_edit = df_ref.drop(columns=[c for c in cols_tech if c in df_ref.columns])
    ordered_cols = ["Traité"] + [c for c in df_to_edit.columns if c != "Traité"]

    st.data_editor(
        df_to_edit.style.apply(apply_style, axis=1),
        column_order=ordered_cols, use_container_width=True, height=600,
        disabled=[c for c in df_to_edit.columns if c != "Traité"],
        column_config={"Traité": st.column_config.CheckboxColumn("Traité", default=False)},
        key="main_editor",
        on_change=handle_editor_change
    )

    if st.button("🗑️ Effacer le cache de ce fichier"):
        path = get_cache_path(filename)
        if os.path.exists(path): os.remove(path)
        reset_state()
        st.rerun()