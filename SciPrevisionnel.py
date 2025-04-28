
import streamlit as st
import numpy_financial as npf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="Prévisionnel SCI à l'IS", layout="wide")
st.title("🏠 Simulation Financière SCI à l'IS")

# --- FONCTIONS ---
@st.cache_data  # Ajout de mise en cache pour améliorer les performances
def calculer_tableau_amortissement(montant, taux_annuel, duree_annees):
    """Calcule un tableau d'amortissement complet pour le prêt"""
    mensualite = npf.pmt(taux_annuel/12, duree_annees*12, -montant)
    
    # Utilisation de la compréhension de liste pour plus d'efficacité
    tableau = []
    reste_a_payer = montant
    
    for mois in range(1, duree_annees*12 + 1):
        interet_mois = reste_a_payer * (taux_annuel/12)
        capital_mois = mensualite - interet_mois
        reste_a_payer -= capital_mois
        
        tableau.append({
            'Mois': mois,
            'Mensualité': mensualite,
            'Intérêts': interet_mois,
            'Capital': capital_mois,
            'Capital Restant': max(0, reste_a_payer)
        })
    
    return pd.DataFrame(tableau)

@st.cache_data  # Ajout de mise en cache pour améliorer les performances
def calculs_financiers(params):
    """Effectue les calculs financiers année par année"""
    # Calcul du tableau d'amortissement
    tableau_amort = calculer_tableau_amortissement(params['emprunt'], params['taux_credit'], params['duree_credit'])
    
    # Préparation des calculs année par année
    resultats = []
    premiere_annee_is = None
    
    # Calcul de la valeur du bâti (hors terrain) pour l'amortissement
    valeur_bati = params['prix_achat'] * (1 - params.get('pourcentage_terrain', 0.2)) + params['travaux']
    
    for an in range(1, params['duree_projection'] + 1):
        # Loyers avec revalorisation
        loyer_annuel = params['loyers_mensuels'] * 12 * ((1 + params['revalorisation_loyers']) ** (an - 1))
        
        # Charges avec indexation
        charges_annuelles = sum([
            params['taxe_fonciere'],
            params['assurance'],
            params['frais_gestion'],
            params['entretien'],
            params['frais_comptable']
        ]) * ((1 + params['indexation_charges']) ** (an - 1))
        
        # Calcul des intérêts et du capital remboursé cette année
        debut_mois = (an-1) * 12 + 1
        fin_mois = an * 12
        amort_annuel = tableau_amort[(tableau_amort['Mois'] >= debut_mois) & (tableau_amort['Mois'] <= fin_mois)]
        
        interets_annuels = amort_annuel['Intérêts'].sum()
        capital_rembourse_annuel = amort_annuel['Capital'].sum()
        credit_annuel = amort_annuel['Mensualité'].sum() if not amort_annuel.empty else 0
        
        # Calcul amortissement comptable (uniquement sur le bâti, pas le terrain)
        duree_amortissement = params.get('duree_amortissement', 20)
        if an <= duree_amortissement:  # Amortissement sur la durée définie
            amortissement_annuel = valeur_bati / duree_amortissement
        else:
            amortissement_annuel = 0
            
        # Résultats
        resultat_comptable = loyer_annuel - charges_annuelles - interets_annuels - amortissement_annuel
        resultat_reel = loyer_annuel - charges_annuelles - interets_annuels
        
        # Calcul IS progressif
        impot_societe = 0
        if resultat_comptable > 0:
            # Mise à jour des seuils selon la législation française actuelle
            if resultat_comptable <= 42500:
                taux_is = 0.15
            else:
                # Différenciation des tranches
                impot_societe = 42500 * 0.15  # 15% sur les premiers 42 500€
                taux_is = 0.25  # 25% sur le reste
                impot_societe += (resultat_comptable - 42500) * taux_is
                taux_is = impot_societe / resultat_comptable  # Taux effectif moyen
            
            # Si on n'a pas encore calculé l'IS par tranches
            if impot_societe == 0:
                impot_societe = resultat_comptable * taux_is
        
        # Mémoriser la première année où l'IS est payé
        if premiere_annee_is is None and impot_societe > 0:
            premiere_annee_is = an
        
        # Cashflow annuel
        cashflow_annuel = loyer_annuel - charges_annuelles - credit_annuel - impot_societe
        
        # Cumuls
        if an == 1:
            cashflow_cumule = cashflow_annuel
            capital_rembourse_cumule = capital_rembourse_annuel
        else:
            previous = resultats[-1]
            cashflow_cumule = previous['Cashflow cumulé'] + cashflow_annuel
            capital_rembourse_cumule = previous['Capital remboursé cumulé'] + capital_rembourse_annuel
            
        # Valeur nette
        valeur_patrimoine = params['prix_achat'] * ((1 + params['appreciation_immobilier']) ** (an - 1))
        valeur_nette = valeur_patrimoine - (params['emprunt'] - capital_rembourse_cumule)
        
        # Rendement sur fonds propres
        rendement_fonds_propres = (cashflow_annuel / params['apport']) * 100 if params['apport'] > 0 else 0
        rendement_brut = (loyer_annuel / params['prix_achat']) * 100
        
        # Capital restant à rembourser
        capital_restant = params['emprunt'] - capital_rembourse_cumule
        
        resultats.append({
            # Informations générales
            "Année": an,
            
            # Revenus
            "Loyers annuels": int(loyer_annuel),
            
            # Charges
            "Charges annuelles": int(charges_annuelles),
            
            # Crédit
            "Mensualités crédit": int(credit_annuel),
            "dont Intérêts": int(interets_annuels),
            "dont Capital": int(capital_rembourse_annuel),
            "Capital remboursé cumulé": int(capital_rembourse_cumule),
            "Capital restant dû": int(capital_restant),
            
            # Comptabilité
            "Amortissement annuel": int(amortissement_annuel),
            "Résultat fiscal annuel": int(resultat_comptable),
            "IS annuel": int(impot_societe),
            
            # Résultats financiers
            "Résultat réel annuel": int(resultat_reel),
            "Cashflow annuel": int(cashflow_annuel),
            "Cashflow cumulé": int(cashflow_cumule),
            
            # Patrimoine
            "Valeur du bien": int(valeur_patrimoine),
            "Valeur nette": int(valeur_nette),
            "Rendement / fonds propres (%)": round(rendement_fonds_propres, 2),
            "Rendement brut (%)": round(rendement_brut, 2)
        })

    return pd.DataFrame(resultats), premiere_annee_is

def formatter_euros(valeur):
    """Formate un nombre en euros"""
    return f"{valeur:,.0f} €".replace(",", " ")

def export_csv(df):
    """Exporte le dataframe en CSV avec encodage UTF-8 et séparateur point-virgule"""
    # Création d'une copie pour éviter de modifier le dataframe original
    df_export = df.copy()
    
    # Renommage des colonnes pour retirer les caractères problématiques
    # et assurer la compatibilité avec les logiciels type Excel français
    colonnes_renommees = {}
    for col in df_export.columns:
        # Remplacer les caractères problématiques pour l'export
        colonnes_renommees[col] = col
    
    df_export = df_export.rename(columns=colonnes_renommees)
    
    # Conversion des nombres à virgule pour Excel français (remplacement du point par la virgule)
    for col in df_export.select_dtypes(include=['float']).columns:
        df_export[col] = df_export[col].apply(lambda x: str(x).replace('.', ','))
    
    # Export avec séparateur point-virgule et encodage UTF-8 avec BOM pour Excel
    csv_str = df_export.to_csv(index=False, sep=';', encoding='utf-8-sig')
    
    return csv_str

# --- SIDEBAR AVEC TABS ---
with st.sidebar:
    st.header("⚙️ Paramètres")
    
    tabs = st.tabs(["📊 Général", "🏠 Bien", "🏦 Financement", "📄 Charges"])
    
    with tabs[0]:  # Paramètres généraux
        duree_projection = st.slider("Durée de projection (ans)", 1, 40, 20)
        appreciation_immobilier = st.number_input("Appréciation immobilière annuelle (%)", value=1.0, step=0.1) / 100
        indexation_charges = st.number_input("Indexation annuelle des charges (%)", value=2.0, step=0.1) / 100
        duree_amortissement = st.slider("Durée d'amortissement (ans)", 10, 30, 20)
    
    with tabs[1]:  # Bien immobilier
        prix_achat = st.number_input("Prix d'achat (€)", value=200000, step=5000)
        frais_notaire = st.number_input("Frais de notaire (€)", value=15000, step=1000)
        travaux = st.number_input("Montant des travaux (€)", value=20000, step=1000)
        pourcentage_terrain = st.slider("Pourcentage terrain non amortissable (%)", 0, 50, 20) / 100
        loyers_mensuels = st.number_input("Loyers mensuels (€)", value=1200, step=50)
        revalorisation_loyers = st.number_input("Revalorisation loyers annuelle (%)", value=1.5, step=0.1) / 100
        vacance_locative = st.slider("Taux de vacance locative (%)", 0, 20, 0, step=1) / 100

    with tabs[2]:  # Financement
        apport = st.number_input("Apport (€)", value=20000, step=1000)
        emprunt = prix_achat + frais_notaire + travaux - apport
        st.info(f"Montant de l'emprunt : {formatter_euros(emprunt)}")
        taux_credit = st.number_input("Taux crédit (%)", value=2.5, step=0.1) / 100
        duree_credit = st.number_input("Durée crédit (ans)", value=20, step=1)
        mensualite = npf.pmt(taux_credit/12, duree_credit*12, -emprunt)
        st.info(f"Mensualité : {formatter_euros(mensualite)}")
        taux_assurance = st.number_input("Taux assurance prêt (%)", value=0.36, step=0.01) / 100
        assurance_pret = emprunt * taux_assurance / 12
        st.info(f"Assurance prêt mensuelle : {formatter_euros(assurance_pret)}")

    with tabs[3]:  # Charges annuelles
        taxe_fonciere = st.number_input("Taxe foncière (€)", value=1000, step=100)
        assurance = st.number_input("Assurance PNO (€)", value=200, step=50)
        frais_gestion = st.number_input("Frais de gestion (€)", value=500, step=100)
        entretien = st.number_input("Entretien/Divers (€)", value=300, step=100)
        frais_comptable = st.number_input("Frais de comptable (€)", value=1200, step=100)
        provision_travaux = st.number_input("Provision pour travaux (%)", value=0.5, step=0.1) / 100
        
    lancer = st.button("🚀 Lancer la simulation", type="primary")

# --- MAIN ---
if lancer:
    # Afficher un spinner pendant le calcul
    with st.spinner("Calcul en cours..."):
        # Préparation des paramètres
        params = {
            'prix_achat': prix_achat,
            'frais_notaire': frais_notaire,
            'travaux': travaux,
            'pourcentage_terrain': pourcentage_terrain,
            'loyers_mensuels': loyers_mensuels * (1 - vacance_locative),  # Ajustement pour la vacance locative
            'revalorisation_loyers': revalorisation_loyers,
            'appreciation_immobilier': appreciation_immobilier,
            'indexation_charges': indexation_charges,
            'apport': apport,
            'emprunt': emprunt,
            'taux_credit': taux_credit,
            'duree_credit': duree_credit,
            'mensualite': mensualite + assurance_pret,  # Ajout de l'assurance prêt
            'taxe_fonciere': taxe_fonciere,
            'assurance': assurance,
            'frais_gestion': frais_gestion,
            'entretien': entretien + (prix_achat * provision_travaux),  # Ajout provision travaux
            'frais_comptable': frais_comptable,
            'duree_projection': duree_projection,
            'duree_amortissement': duree_amortissement
        }

        df, premiere_annee_is = calculs_financiers(params)
        
        # --- TABLEAU DE BORD ---
        st.header("📊 Tableau de bord")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        # Valeurs pour les métriques
        valeur_finale = df.iloc[-1]['Valeur du bien']
        cashflow_cumule_final = df.iloc[-1]['Cashflow cumulé']
        valeur_nette_finale = df.iloc[-1]['Valeur nette']
        cashflow_moyen = int(df['Cashflow annuel'].mean())
        rendement_moyen = round(df['Rendement / fonds propres (%)'].mean(), 2)
        rendement_brut_moyen = round(df['Rendement brut (%)'].mean(), 2)
        
        # Affichage des métriques principales
        col1.metric("💰 Cashflow cumulé", formatter_euros(cashflow_cumule_final), 
                   f"{'+' if cashflow_moyen > 0 else ''}{formatter_euros(cashflow_moyen)}/an")
        
        col2.metric("🏠 Valeur finale", formatter_euros(valeur_finale), 
                   f"+{formatter_euros(valeur_finale - prix_achat)}")
        
        col3.metric("📈 Valeur nette", formatter_euros(valeur_nette_finale), 
                   f"+{formatter_euros(valeur_nette_finale - apport)}")
        
        # Seconde ligne de métriques
        col1, col2, col3 = st.columns([1, 1, 1])
        
        col1.metric("💹 Rendement/fonds propres", f"{rendement_moyen}%")
        col2.metric("📊 Rendement brut", f"{rendement_brut_moyen}%")
        col3.metric("⏱️ Durée du crédit", f"{duree_credit} ans")
        
        # Alerte sur l'IS
        if premiere_annee_is:
            st.warning(f"⚠️ IS à payer à partir de l'année {premiere_annee_is}")
        else:
            st.success("✅ Pas d'IS à payer sur toute la durée de projection")
        
        # --- RÉSULTATS DÉTAILLÉS ---
        st.header("📑 Résultats détaillés")
        
        # Filtrer pour les années clés pour l'affichage principal
        annees_cles = [1, 5, 10, 15, 20, 25, 30]
        if duree_projection not in annees_cles:
            annees_cles.append(duree_projection)
        annees_cles = sorted([a for a in annees_cles if a <= duree_projection])
        df_display = df[df['Année'].isin(annees_cles)].copy()
        
        st.subheader(f"📊 Résultats sur {', '.join(map(str, annees_cles[:-1]))} et {annees_cles[-1]} ans")
        
        tab1, tab2, tab3, tab4 = st.tabs(["💰 Résultats financiers", "📝 Comptabilité", "🏦 Crédit", "🏠 Patrimoine"])
        
        with tab1:
            # Affichage des résultats financiers
            cols_financiers = ["Année", "Loyers annuels", "Charges annuelles", "Mensualités crédit", "IS annuel", 
                              "Cashflow annuel", "Cashflow cumulé", "Rendement / fonds propres (%)", "Rendement brut (%)"]
            
            st.dataframe(df_display[cols_financiers].style.format({
                col: "{:,} €".replace(",", " ") if col != "Année" and "(%)" not in col else "{}"
                for col in cols_financiers
            }).format({"Rendement / fonds propres (%)": "{:.2f}", "Rendement brut (%)": "{:.2f}"}), use_container_width=True)
        
        with tab2:
            # Affichage des informations comptables
            cols_compta = ["Année", "Loyers annuels", "Charges annuelles", "dont Intérêts", "Amortissement annuel", 
                         "Résultat fiscal annuel", "IS annuel"]
            
            st.dataframe(df_display[cols_compta].style.format({
                col: "{:,} €".replace(",", " ") if col != "Année" else "{}"
                for col in cols_compta
            }), use_container_width=True)
        
        with tab3:
            # Affichage des informations crédit
            cols_credit = ["Année", "Mensualités crédit", "dont Intérêts", "dont Capital", 
                         "Capital remboursé cumulé", "Capital restant dû"]
            
            st.dataframe(df_display[cols_credit].style.format({
                col: "{:,} €".replace(",", " ") if col != "Année" else "{}"
                for col in cols_credit
            }), use_container_width=True)
        
        with tab4:
            # Affichage des informations patrimoine
            cols_patrimoine = ["Année", "Valeur du bien", "Capital restant dû", "Valeur nette"]
            
            st.dataframe(df_display[cols_patrimoine].style.format({
                col: "{:,} €".replace(",", " ") if col != "Année" else "{}"
                for col in cols_patrimoine
            }), use_container_width=True)

        # --- GRAPHIQUES ---
        st.header("📈 Graphiques")
        
        # Configuration des graphiques principales (sans le camembert qui cause l'erreur)
        fig1 = make_subplots(
            rows=2, cols=2,
            subplot_titles=("Évolution du Cashflow", "Évolution de la Valeur Patrimoniale", 
                           "Rendement sur fonds propres", ""),
            specs=[[{"secondary_y": True}, {"secondary_y": False}], 
                  [{"secondary_y": False}, {"type": "domain"}]],  # type "domain" pour le camembert
            vertical_spacing=0.12,
            horizontal_spacing=0.08
        )
        
        # Graphique 1: Cashflow et rendement
        fig1.add_trace(go.Bar(
            x=df["Année"], 
            y=df["Cashflow annuel"],
            name="Cashflow annuel (€)",
            marker_color='indianred'
        ), row=1, col=1)
        
        fig1.add_trace(go.Scatter(
            x=df["Année"], 
            y=df["Cashflow cumulé"],
            name="Cashflow cumulé (€)",
            mode='lines+markers',
            line=dict(color='firebrick', width=3)
        ), row=1, col=1)
        
        # Graphique 2: Valeur patrimoniale
        fig1.add_trace(go.Scatter(
            x=df["Année"], 
            y=df["Valeur du bien"],
            name="Valeur bien (€)",
            mode='lines',
            line=dict(color='royalblue')
        ), row=1, col=2)
        
        fig1.add_trace(go.Scatter(
            x=df["Année"], 
            y=df["Capital restant dû"],
            name="Capital restant dû (€)",
            mode='lines',
            line=dict(color='indianred')
        ), row=1, col=2)
        
        fig1.add_trace(go.Scatter(
            x=df["Année"], 
            y=df["Valeur nette"],
            name="Valeur nette (€)",
            mode='lines',
            line=dict(color='mediumseagreen')
        ), row=1, col=2)
        
        # Graphique 3: Rendement
        fig1.add_trace(go.Scatter(
            x=df["Année"], 
            y=df["Rendement / fonds propres (%)"],
            name="Rendement/fonds propres (%)",
            mode='lines+markers',
            line=dict(color='green', width=3)
        ), row=2, col=1)
        
        fig1.add_trace(go.Scatter(
            x=df["Année"], 
            y=df["Rendement brut (%)"],
            name="Rendement brut (%)",
            mode='lines+markers',
            line=dict(color='darkgreen', width=2, dash='dot')
        ), row=2, col=1)
        
        # Graphique 4: Décomposition première année (camembert)
        # Création d'un graphique de type 'pie' qui doit être dans un subplot de type 'domain'
        labels = ["Intérêts", "Charges", "IS", "Cashflow"]
        values = [
            df.iloc[0]["dont Intérêts"],
            df.iloc[0]["Charges annuelles"],
            df.iloc[0]["IS annuel"],
            df.iloc[0]["Cashflow annuel"]
        ]
        
        fig1.add_trace(go.Pie(
            labels=labels,
            values=values,
            name="Décomposition Année 1",
            hole=.4,
            title="Décomposition des charges"
        ), row=2, col=2)  # Cette case a le type "domain" approprié pour un camembert
        
        # Mise en forme
        fig1.update_layout(
            height=800,
            title_text="Projection Financière Détaillée",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            separators=', '
        )
        
        fig1.update_yaxes(title_text="Euros (€)", row=1, col=1)
        fig1.update_yaxes(title_text="Euros (€)", row=1, col=2)
        fig1.update_yaxes(title_text="Rendement (%)", row=2, col=1)
        fig1.update_xaxes(title_text="Années", row=2, col=1)

        st.plotly_chart(fig1, use_container_width=True)

        # --- Détail Année 1 ---
        st.header("🔍 Focus Année 1")
        
        annee1 = df[df['Année'] == 1].iloc[0]
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            st.markdown("### 💰 Revenus")
            st.markdown(f"- Revenus locatifs : **{formatter_euros(annee1['Loyers annuels'])}**")
            st.markdown(f"- Taux d'occupation : **{100 - vacance_locative*100:.0f}%**")

        with col2:
            st.markdown("### 📉 Dépenses")
            st.markdown(f"- Taxe foncière : **-{formatter_euros(taxe_fonciere)}**")
            st.markdown(f"- Assurance PNO : **-{formatter_euros(assurance)}**")
            st.markdown(f"- Frais de gestion : **-{formatter_euros(frais_gestion)}**")
            st.markdown(f"- Entretien / Provision : **-{formatter_euros(entretien)}**")
            st.markdown(f"- Frais comptable : **-{formatter_euros(frais_comptable)}**")
            st.markdown(f"- Intérêts d'emprunt : **-{formatter_euros(annee1['dont Intérêts'])}**")
            st.markdown(f"- IS : **-{formatter_euros(annee1['IS annuel'])}**")
        
        with col3:
            st.markdown("### 🏦 Crédit")
            st.markdown(f"- Mensualités totales : **{formatter_euros(annee1['Mensualités crédit'])}**")
            st.markdown(f"- dont Intérêts : **{formatter_euros(annee1['dont Intérêts'])}**")
            st.markdown(f"- dont Capital : **{formatter_euros(annee1['dont Capital'])}**")
            st.markdown(f"- Capital restant dû : **{formatter_euros(annee1['Capital restant dû'])}**")
        
        st.divider()
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"### ➡️ **Cashflow net Année 1 : {formatter_euros(annee1['Cashflow annuel'])}**")
            st.markdown(f"### 📊 **Rendement sur fonds propres : {annee1['Rendement / fonds propres (%)']:.2f}%**")
        
        with col2:
            st.markdown(f"### 🏠 **Valeur du bien : {formatter_euros(annee1['Valeur du bien'])}**")
            st.markdown(f"### 📈 **Valeur nette estimée : {formatter_euros(annee1['Valeur nette'])}**")

        # --- Données complètes ---
        with st.expander("🔎 Voir toutes les données année par année"):
            st.dataframe(df.style.format({
                col: "{:,} €".replace(",", " ") if col != "Année" and "(%)" not in col else "{}"
                for col in df.columns
            }).format({"Rendement / fonds propres (%)": "{:.2f}", "Rendement brut (%)": "{:.2f}"}), use_container_width=True)

        # --- Exporter les données ---
        # Utilisation de la fonction export_csv pour un CSV compatible Excel français
        csv_data = export_csv(df)
        st.download_button(
            label="📥 Télécharger les données",
            data=csv_data,
            file_name=f"simulation_sci_is_{time.strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv;charset=utf-8-sig"
        )

else:
    # Affichage par défaut quand l'application démarre
    st.info("👈 Configurez les paramètres dans le panneau de gauche puis cliquez sur 'Lancer la simulation'")
    
    # Description de l'application
    st.markdown("""
    ### À propos de ce simulateur
    
    Ce simulateur vous permet d'évaluer la rentabilité financière d'un investissement immobilier via une SCI soumise à l'impôt sur les sociétés (IS).
    
    #### Fonctionnalités principales:
    - Projection financière sur 1 à 40 ans
    - Calcul du cashflow et de la rentabilité
    - Amortissement comptable du bien immobilier (hors terrain)
    - Prise en compte de l'IS avec taxation progressive
    - Valorisation du patrimoine et calcul de la valeur nette
    
    #### Comment utiliser cet outil:
    1. Configurez les paramètres dans le panneau latéral
    2. Cliquez sur "Lancer la simulation"
    3. Analysez les graphiques et tableaux générés
    
    Pour toute question ou suggestion d'amélioration, n'hésitez pas à nous contacter.
    """)
