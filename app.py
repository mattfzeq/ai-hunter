import streamlit as st
import os
from openai import OpenAI

# Configuration minimale
st.set_page_config(page_title="Crash Test OpenAI")

# Titre
st.title("🛠️ DIAGNOSTIC OPENAI")

# 1. Vérification de la Clé
api_key = os.getenv("OPENAI_API_KEY")
st.write("État de la clé API :")
if api_key:
    st.success(f"Clé trouvée (commence par {api_key[:7]}...)")
else:
    st.error("❌ AUCUNE CLÉ DÉTECTÉE DANS LES SECRETS !")

# Bouton de test
if st.button("Lancer le test de connexion"):
    client = OpenAI(api_key=api_key)
    
    st.info("Tentative de connexion avec le modèle 'gpt-3.5-turbo' (le moins cher)...")
    
    # PAS DE TRY/EXCEPT : On veut que ça plante si ça doit planter
    response = client.chat.completions.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": "Réponds juste par le mot : SUCCÈS."}]
    )
    
    # Si on arrive ici, c'est que ça marche
    st.success("✅ RÉPONSE REÇUE :")
    st.write(response.choices[0].message.content)