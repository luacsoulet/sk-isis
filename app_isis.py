import streamlit as st
import pandas as pd
import io
from difflib import SequenceMatcher

st.set_page_config(page_title="Isis Data Cleaning", layout="wide")

# Fonction pour calculer la ressemblance
def get_similarity(a, b):
    return SequenceMatcher(None, str(a), str(b)).ratio()

st.title("📂 Isis Data Cleaning - Analyseur de Doublons")

# 1. Légende mise à jour
st.subheader("Légende des couleurs")
col_leg1, col_leg2, col_leg3 = st.columns(3)
col_leg1.info("🔵 **Bleu** : Première occurrence (Originale) d'un groupe suspect")
col_leg2.error("🔴 **Rouge** : Doublon d'adresse (Ligne à vérifier/supprimer)")
col_leg3.warning("🟠 **Orange** : Nom ressemblant (Ligne à vérifier/supprimer)")

# 2. Upload du fichier CSV
uploaded_file = st.file_uploader("Choisir un fichier CSV", type=["csv"])

if uploaded_file is not None:
    file_name_no_ext = uploaded_file.name.rsplit('.', 1)[0]
    
    try:
        # Lecture avec l'encodage et le séparateur du notebook
        df = pd.read_csv(uploaded_file, encoding='WINDOWS-1252', sep=";")
        
        if st.button("Lancer l'analyse et regrouper"):
            
            # --- TRAITEMENT ---
            
            # Suppression de la colonne 'projet'
            df_final = df.drop(columns=['projet']) if 'projet' in df.columns else df.copy()
            
            # Initialisation des colonnes de marquage et de groupement
            df_final["dupliquer"] = False
            df_final["nom_ressemblant"] = False
            df_final["is_first_occurrence"] = False
            df_final["Group_ID"] = df_final.index  # Par défaut, chaque ligne est son propre groupe
            
            # Normalisation pour les comparaisons
            df_final['Nom_Norm'] = df_final['Nom du client'].astype(str).str.strip().str.upper()
            df_final['Addr_Norm'] = df_final['Adresse'].astype(str).str.strip().str.upper()
            
            # Suivi des originaux
            addr_to_orig_idx = {}
            names_uniques_vus = [] # Liste de tuples (index_original, nom_normalise)
            
            SEUIL = 0.9
            
            for index, row in df_final.iterrows():
                nom_actuel = row['Nom_Norm']
                addr_actuelle = row['Addr_Norm']
                
                # Vérification adresse exacte
                match_addr_idx = addr_to_orig_idx.get(addr_actuelle)
                
                # Recherche de ressemblance par nom
                match_name_idx = None
                if nom_actuel and nom_actuel != "NAN":
                    for idx_orig, nom_vu in names_uniques_vus:
                        if get_similarity(nom_actuel, nom_vu) >= SEUIL:
                            match_name_idx = idx_orig
                            break
                
                # Attribution du Group_ID et des couleurs
                if match_addr_idx is not None:
                    # Doublon d'adresse (Priorité Rouge)
                    df_final.at[index, 'dupliquer'] = True
                    df_final.at[index, 'Group_ID'] = match_addr_idx
                    df_final.at[match_addr_idx, 'is_first_occurrence'] = True
                elif match_name_idx is not None:
                    # Doublon de nom (Orange)
                    df_final.at[index, 'nom_ressemblant'] = True
                    df_final.at[index, 'Group_ID'] = match_name_idx
                    df_final.at[match_name_idx, 'is_first_occurrence'] = True
                else:
                    # C'est une nouvelle entité (potentiel futur original)
                    addr_to_orig_idx[addr_actuelle] = index
                    if nom_actuel and nom_actuel != "NAN":
                        names_uniques_vus.append((index, nom_actuel))

            # C. REGROUPEMENT : On trie par Group_ID pour coller les familles de doublons
            # On utilise l'index original comme second critère pour garder l'ordre dans le groupe
            df_final['Original_Order'] = df_final.index
            df_final = df_final.sort_values(by=['Group_ID', 'Original_Order'], ascending=True)
            
            # ------------------
            
            st.divider()
            
            # 3. Statistiques
            c1, c2 = st.columns(2)
            c1.metric("Doublons d'adresses (Rouge)", df_final["dupliquer"].sum())
            c2.metric("Noms ressemblants (Orange)", df_final["nom_ressemblant"].sum())
            
            # 4. Export vers Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                # Masquage des colonnes techniques pour l'export
                cols_to_export = [c for c in df_final.columns if c not in ['Nom_Norm', 'Addr_Norm', 'is_first_occurrence', 'Group_ID', 'Original_Order']]
                df_final[cols_to_export].to_excel(writer, index=False, sheet_name='Analyse_Groupee')
            
            st.download_button(
                label="📥 Télécharger le fichier Excel groupé",
                data=buffer.getvalue(),
                file_name=f"{file_name_no_ext}_analyse.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # 5. Affichage avec Style
            st.subheader("Aperçu des données groupées")
            
            df_display = df_final.copy()
            df_display["dupliquer"] = df_display["dupliquer"].astype(str)
            df_display["nom_ressemblant"] = df_display["nom_ressemblant"].astype(str)
            
            def apply_custom_style(row):
                idx = row.name
                if df_final.loc[idx, "dupliquer"]:
                    return ['background-color: rgba(255, 0, 0, 0.25)'] * len(row) # Rouge
                elif df_final.loc[idx, "nom_ressemblant"]:
                    return ['background-color: rgba(255, 165, 0, 0.25)'] * len(row) # Orange
                elif df_final.loc[idx, "is_first_occurrence"]:
                    return ['background-color: rgba(0, 100, 255, 0.20)'] * len(row) # Bleu
                return [''] * len(row)

            cols_to_show = [c for c in df_display.columns if c not in ['Nom_Norm', 'Addr_Norm', 'is_first_occurrence', 'Group_ID', 'Original_Order']]

            st.dataframe(
                df_display.style.apply(apply_custom_style, axis=1), 
                column_order=cols_to_show,
                use_container_width=True,
                height=800
            )

    except Exception as e:
        st.error(f"Erreur lors du traitement : {e}")

else:
    st.info("Veuillez charger un fichier CSV pour commencer.")