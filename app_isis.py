import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="Isis Data Cleaning", layout="wide")

st.title("📂 Isis Data Cleaning")
st.write("Analyse des doublons avec affichage limité à 50 lignes et défilement.")

# 1. Upload du fichier CSV
uploaded_file = st.file_uploader("Choisir un fichier CSV", type=["csv"])

if uploaded_file is not None:
    file_name_no_ext = uploaded_file.name.rsplit('.', 1)[0]
    
    try:
        # Lecture avec l'encodage et le séparateur du notebook
        df = pd.read_csv(uploaded_file, encoding='WINDOWS-1252', sep=";")
        
        st.success(f"Fichier '{uploaded_file.name}' chargé !")
        
        # 2. Bouton de traitement
        if st.button("Afficher les doublons"):
            
            # --- TRAITEMENT (Logique du Notebook) ---
            
            # Suppression de la colonne 'projet'
            if 'projet' in df.columns:
                df_final = df.drop(columns=['projet'])
            else:
                df_final = df.copy()
            
            # Marquage des doublons sur 'Adresse'
            df_final["dupliquer"] = df_final.duplicated(subset=["Adresse"], keep='first')
            
            # ---------------------------------------
            
            st.divider()
            
            # 3. Statistiques
            nb_doublons = df_final["dupliquer"].sum()
            st.warning(f"⚠️ {nb_doublons} doublons détectés (marqués en rouge).")
            
            # 4. Export Excel
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_final.to_excel(writer, index=False, sheet_name='Isis_Analysis')
            
            st.download_button(
                label="📥 Télécharger le fichier Excel complet",
                data=buffer.getvalue(),
                file_name=f"{file_name_no_ext}_analyse.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # 5. Affichage du tableau avec SCROLLBAR
            st.subheader("Aperçu des données (50 lignes visibles)")
            
            # Préparation de l'affichage (Texte pour la colonne dupliquer)
            df_display = df_final.copy()
            df_display["dupliquer"] = df_display["dupliquer"].astype(str)
            
            # Style : Rouge bien visible (opacité 0.25)
            def highlight_red(row):
                is_dup = df_final.loc[row.name, "dupliquer"]
                if is_dup:
                    return ['background-color: rgba(255, 0, 0, 0.25)'] * len(row)
                return [''] * len(row)

            # Fixer la hauteur pour environ 50 lignes (approx 35px par ligne)
            # Si le tableau a moins de 50 lignes, il s'adaptera, sinon il affichera la scrollbar.
            fixed_height = 800 
            
            st.dataframe(
                df_display.style.apply(highlight_red, axis=1), 
                use_container_width=True,
                height=fixed_height # Active la scrollbar interne
            )

    except Exception as e:
        st.error(f"Erreur : {e}")

else:
    st.info("Veuillez déposer un fichier CSV.")