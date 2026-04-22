import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import io
import base64

# --- 1. CONFIGURATION & BDD ---
st.set_page_config(page_title='ERP Huilerie Pro', layout='wide', page_icon='🌿')

# --- 1. PERSONNALISATION VISUELLE (ARRIÈRE-PLAN) ---
def set_bg_hack(main_bg_img):
    try:
        with open(main_bg_img, "rb") as f:
            bin_str = base64.b64encode(f.read()).decode()
        st.markdown(
            f"""
            <style>
            .stApp {{
                background: url("data:image/jpg;base64,{bin_str}");
                background-size: cover;
                background-attachment: fixed;
            }}
            /* Amélioration lisibilité blocs */
            [data-testid="stForm"], .stMetric, .stDataFrame, [data-testid="stTable"] {{
                background-color: rgba(255, 255, 255, 0.9) !important;
                padding: 20px;
                border-radius: 15px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.2);
            }}
            [data-testid="stSidebar"] {{
                background-color: rgba(244, 247, 241, 0.95) !important;
            }}
            </style>
            """,
            unsafe_allow_html=True
        )
    except FileNotFoundError:
        st.sidebar.warning("Fichier 'fond_huilerie.JPG' non trouvé.")

set_bg_hack('fond_huilerie.JPG')


def get_connection():
    return sqlite3.connect('huilerie.db')

def init_db():
    conn = get_connection(); c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS clients (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT, prenom TEXT, telephone TEXT)')
    c.execute('''CREATE TABLE IF NOT EXISTS production (id INTEGER PRIMARY KEY AUTOINCREMENT, client_id INTEGER, poids REAL, huile REAL, date_reception TEXT, date_prevue TEXT, statut TEXT, tarif REAL, cuve_id INTEGER)''')
    c.execute('CREATE TABLE IF NOT EXISTS cuves (id INTEGER PRIMARY KEY, nom TEXT, niveau_actuel REAL)')
    c.execute('''CREATE TABLE IF NOT EXISTS utilisateurs (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS sorties (id INTEGER PRIMARY KEY AUTOINCREMENT, production_id INTEGER, quantite REAL, date_sortie TEXT)''')
    c.execute("INSERT OR IGNORE INTO utilisateurs (username, password, role) VALUES ('admin', '1234', 'Administrateur')")
    # Initialisation cuves si vide
    c.execute("INSERT OR IGNORE INTO cuves (id, nom, niveau_actuel) VALUES (1, 'Cuve 1', 0), (2, 'Cuve 2', 0), (3, 'Cuve 3', 0), (4, 'Cuve 4', 0), (5, 'Cuve 5', 0)")
    conn.commit(); conn.close()

init_db()

# --- 2. FONCTION UTILITAIRE (Ticket) ---
def afficher_ticket(id_lot, nom_complet, poids, huile, cuve, tarif):
    total = poids * tarif
    st.markdown(f"""
    <div style="border: 2px dashed #4CAF50; padding: 20px; width: 350px; background-color: #fafafa; border-radius: 10px;">
        <h2 style="text-align: center;">TICKET LOT N° {id_lot}</h2>
        <p><b>Client:</b> {nom_complet}</p><hr>
        <p><b>Poids Olives:</b> {poids} kg</p>
        <p><b>Huile Obtenue:</b> {huile} L</p>
        <h3 style="text-align: right;">TOTAL: {total:,.2f} DA</h3>
        <p>Stocké en : <b>{cuve}</b></p>
    </div>
    """, unsafe_allow_html=True)

# --- 3. GESTION DES ACCÈS ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'ticket_data' not in st.session_state: st.session_state.ticket_data = None

if not st.session_state.logged_in:
    st.sidebar.title("🔒 Connexion")
    user = st.sidebar.text_input("Identifiant")
    pwd = st.sidebar.text_input("Mot de passe", type="password")
    if st.sidebar.button("Se connecter"):
        conn = get_connection()
        user_data = conn.execute("SELECT * FROM utilisateurs WHERE username=? AND password=?", (user, pwd)).fetchone()
        if user_data:
            st.session_state.logged_in = True
            st.session_state.role = user_data[3]
            st.rerun()
        else: st.error("Accès refusé")
    st.stop()

# --- 4. NAVIGATION ---
st.sidebar.title(f"🌿 Huilerie (Role: {st.session_state.role})")
menu = ['📥 Réception', '⚙️ Atelier Presse', '📤 Sorties', '🛢️ Stock', '📜 Traçabilité & Historique']
if st.session_state.role == 'Administrateur': 
    menu.insert(0, '👥 Clients')
    menu.append('👤 Administration')
choix = st.sidebar.radio("Navigation", menu)

# --- 5. LOGIQUE MODULES ---
if choix == '👥 Clients':
    st.header("👥 Gestion des Clients")
    with st.form("add_client"):
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nom"); prenom = c2.text_input("Prénom"); tel = c1.text_input("Téléphone")
        if st.form_submit_button("💾 Enregistrer"):
            conn = get_connection(); c = conn.cursor()
            c.execute('INSERT INTO clients (nom, prenom, telephone) VALUES (?,?,?)', (nom.upper(), prenom.capitalize(), tel))
            conn.commit(); conn.close(); st.success("Client ajouté !"); st.rerun()
    conn = get_connection(); df = pd.read_sql_query("SELECT * FROM clients", conn); conn.close()
    st.dataframe(df, use_container_width=True)

elif choix == '📥 Réception':
    st.header("📥 Bon de Réception")
    conn = get_connection(); df_c = pd.read_sql_query("SELECT id, nom, prenom FROM clients", conn); conn.close()
    with st.form("recep"):
        cl = st.selectbox("Client", [f"{r['id']} - {r['nom']} {r['prenom']}" for _, r in df_c.iterrows()])
        poids = st.number_input("Poids Olives (kg)", min_value=0.0)
        dt_p = st.date_input("Date prévue", datetime.now() + timedelta(days=2))
        if st.form_submit_button("💾 Créer Bon"):
            conn = get_connection(); c = conn.cursor()
            c.execute('INSERT INTO production (client_id, poids, date_reception, date_prevue, statut) VALUES (?,?,?,?,?)',
                      (cl.split(' - ')[0], poids, datetime.now().strftime('%d/%m/%Y'), dt_p.strftime('%d/%m/%Y'), 'En attente'))
            conn.commit(); conn.close(); st.success("Réception validée !"); st.rerun()

elif choix == '⚙️ Atelier Presse':
    st.header("⚙️ Atelier de Presse")
    conn = get_connection()
    df_att = pd.read_sql_query("SELECT p.id, c.nom, c.prenom, p.poids FROM production p JOIN clients c ON p.client_id = c.id WHERE p.statut = 'En attente'", conn)
    df_cuves = pd.read_sql_query("SELECT * FROM cuves", conn); conn.close()
    
    if st.session_state.ticket_data:
        t = st.session_state.ticket_data
        afficher_ticket(t['id'], t['nom'], t['poids'], t['huile'], t['cuve'], t['tarif'])
        if st.button("❌ Fermer"): st.session_state.ticket_data = None; st.rerun()
    
    if not df_att.empty:
        with st.form("form_presse"):
            col1, col2 = st.columns(2)
            lot_sel = col1.selectbox("Sélectionner Lot", [f"{r['id']} - {r['nom']} {r['prenom']} ({r['poids']}kg)" for _, r in df_att.iterrows()])
            qte_h = col2.number_input("Huile (L)", min_value=0.0)
            cuve_id = col1.selectbox("Cuve", [f"Cuve {r['id']}" for _, r in df_cuves.iterrows()])
            tarif_p = col2.number_input("Tarif Pressage (DA/kg)", value=8.0)
            if st.form_submit_button("✅ Finaliser & Imprimer Ticket"):
                l_id = lot_sel.split(' - ')[0]; c_id = cuve_id.split(' ')[1]
                conn = get_connection(); c = conn.cursor()
                c.execute('UPDATE production SET huile=?, cuve_id=?, statut=?, tarif=? WHERE id=?', (qte_h, c_id, 'Pressé', tarif_p, l_id))
                c.execute('UPDATE cuves SET niveau_actuel = niveau_actuel + ? WHERE id=?', (qte_h, c_id))
                inf = c.execute('SELECT c.nom, c.prenom, p.poids FROM production p JOIN clients c ON p.client_id = c.id WHERE p.id=?', (l_id,)).fetchone()
                conn.commit(); conn.close()
                st.session_state.ticket_data = {'id': l_id, 'nom': f"{inf[0]} {inf[1]}", 'poids': inf[2], 'huile': qte_h, 'cuve': f"Cuve {c_id}", 'tarif': tarif_p}
                st.rerun()
elif choix == '📤 Sorties':
    st.header("📤 Bon de Sortie")
    conn = get_connection()
    df_pret = pd.read_sql_query("SELECT p.id, c.nom, c.prenom, p.huile, p.cuve_id FROM production p JOIN clients c ON p.client_id = c.id WHERE p.statut = 'Pressé'", conn); conn.close()
    if df_pret.empty: st.info("Rien à livrer.")
    else:
        with st.form("f_sort"):
            lot_s = st.selectbox("Lot", [f"{r['id']} - {r['nom']} {r['prenom']} ({r['huile']}L)" for _, r in df_pret.iterrows()])
            if st.form_submit_button("📉 Confirmer Livraison"):
                p_id = lot_s.split(' - ')[0]; conn = get_connection(); c = conn.cursor()
                info = c.execute('SELECT huile, cuve_id FROM production WHERE id=?', (p_id,)).fetchone()
                c.execute('UPDATE cuves SET niveau_actuel = niveau_actuel - ? WHERE id=?', (info[0], info[1]))
                c.execute('UPDATE production SET statut=? WHERE id=?', ('Livré', p_id))
                c.execute('INSERT INTO sorties (production_id, quantite, date_sortie) VALUES (?,?,?)', (p_id, info[0], datetime.now().strftime('%d/%m/%Y')))
                conn.commit(); conn.close(); st.success("Sortie effectuée !"); st.rerun()

elif choix == '🛢️ Stock':
    st.header("🛢️ État des Cuves")
    conn = get_connection(); df_cv = pd.read_sql_query("SELECT * FROM cuves", conn); conn.close()
    cols = st.columns(5)
    for i, r in df_cv.iterrows():
        with cols[i]: st.metric(r['nom'], f"{r['niveau_actuel']} L"); st.progress(min(r['niveau_actuel']/1000, 1.0))

elif choix == '📜 Traçabilité & Historique':
    st.header("📜 Historique Global & Export Excel")
    conn = get_connection()
    query = """
        SELECT p.id as 'Lot', p.date_reception as 'Date', c.nom || ' ' || c.prenom as 'Client', 
               p.poids as 'Olives (kg)', p.huile as 'Huile (L)', (p.poids * p.tarif) as 'CA (DA)', p.statut as 'Statut'
        FROM production p JOIN clients c ON p.client_id = c.id ORDER BY p.id DESC
    """
    df_hist = pd.read_sql_query(query, conn); conn.close()
    
    st.metric("Total Chiffre d'Affaires", f"{df_hist['CA (DA)'].sum():,.2f} DA")
    
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_hist.to_excel(writer, index=False, sheet_name='Traçabilité')
    st.download_button("📥 Télécharger Rapport Excel", buffer.getvalue(), "Rapport_Huilerie.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    
    st.divider()
    st.dataframe(df_hist, use_container_width=True)
elif choix == '👤 Administration':
    st.header("👤 Gestion des Utilisateurs")
    with st.form("add_user"):
        new_user = st.text_input("Nouvel identifiant")
        new_pwd = st.text_input("Mot de passe", type="password")
        new_role = st.selectbox("Rôle", ["Utilisateur", "Administrateur"])
        if st.form_submit_button("Ajouter l'utilisateur"):
            conn = get_connection()
            try:
                conn.execute("INSERT INTO utilisateurs (username, password, role) VALUES (?, ?, ?)", (new_user, new_pwd, new_role))
                conn.commit(); st.success("Utilisateur ajouté !")
            except: st.error("Erreur (identifiant déjà utilisé).")
            conn.close()

# --- BOUTON DÉCONNEXION ---
if st.sidebar.button("Déconnexion"):
    st.session_state.logged_in = False
    st.rerun()