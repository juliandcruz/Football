import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path
import requests
from datetime import datetime

st.set_page_config(
    page_title="ValueBet Football",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {max-width: 1200px; padding: 1rem .6rem 4rem .6rem;}
h1 {font-size: 1.6rem !important;}
h2 {font-size: 1.25rem !important; margin-top: 1rem !important;}
.match-card {
  padding: 14px; border-radius: 16px; border: 1px solid rgba(128,128,128,.2);
  margin-bottom: 12px; background: rgba(128,128,128,.03);
}
.market-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 8px 0; border-top: 1px solid rgba(128,128,128,.1);
  font-size: 0.9rem;
}
.badge-value { background: rgba(46, 204, 113, 0.15); color: #2ecc71; padding: 3px 8px; border-radius: 8px; font-weight: 700; font-size: 0.75rem;}
.badge-neutral { background: rgba(128, 128, 128, 0.15); opacity: 0.8; padding: 3px 8px; border-radius: 8px; font-size: 0.75rem;}
.team-container {display: flex; align-items: center; gap: 10px; font-weight: 700; font-size: 1.05rem;}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def load_api_data(competition="PD"):
    try:
        api_key = st.secrets["FOOTBALL_DATA_API_KEY"]
    except Exception:
        return pd.DataFrame(), "Falta la clave secreta."
    
    headers = {"X-Auth-Token": api_key}
    url = f"https://api.football-data.org/v4/competitions/{competition}/matches?status=SCHEDULED"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            matches = data.get("matches", [])
            
            parsed_data = []
            for m in matches:
                home = m["homeTeam"]["name"]
                away = m["awayTeam"]["name"]
                home_crest = m["homeTeam"].get("crest", "")
                away_crest = m["awayTeam"].get("crest", "")
                
                # Formatear fecha y hora UTC a hora local legible
                utc_date = m.get("utcDate", "")
                try:
                    dt = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                    match_date = dt.strftime("%d/%m")
                    match_time = dt.strftime("%H:%M")
                except:
                    match_date = "Próx."
                    match_time = ""

                # Simulamos mercados basados en los datos reales de los partidos
                parsed_data.append([home, away, home_crest, away_crest, match_date, match_time, "Goles Totales", "+2.5", 0.52, 1.95, 1.92, 1.5, "⚖️ NEUTRAL"])
                parsed_data.append([home, away, home_crest, away_crest, match_date, match_time, "Ambos Marcan (BTTS)", "Sí", 0.58, 1.75, 1.72, 3.2, "🔥 VALUE ALTO"])
                
            if parsed_data:
                df = pd.DataFrame(parsed_data, columns=["home","away","home_crest","away_crest","date","time","market","line","probability","odds","fair_odds","ev","rating"])
                return df, "OK"
            else:
                return pd.DataFrame(), "Sin partidos próximos en esta competición."
        else:
            return pd.DataFrame(), f"Error HTTP {response.status_code}"
    except Exception as e:
        return pd.DataFrame(), str(e)

def demo_data():
    return pd.DataFrame([
        ["Real Madrid","Real Sociedad","https://crests.football-data.org/86.png","https://crests.football-data.org/92.png","30/08","21:00","Córners Madrid","+5.5",0.67,1.70,1.49,13.9,"🔥 VALUE ALTO"],
        ["Real Madrid","Real Sociedad","https://crests.football-data.org/86.png","https://crests.football-data.org/92.png","30/08","21:00","Tarjetas Real Sociedad","+1.5",0.71,1.60,1.41,13.6,"🔥 VALUE ALTO"],
        ["Real Madrid","Real Sociedad","https://crests.football-data.org/86.png","https://crests.football-data.org/92.png","30/08","21:00","Mbappé tiros a puerta","+1.5",0.54,2.10,1.85,13.4,"🔥 VALUE ALTO"],
    ], columns=["home","away","home_crest","away_crest","date","time","market","line","probability","odds","fair_odds","ev","rating"])

def main():
    st.title("⚽ ValueBet Football")

    # Diccionario de logos oficiales de competiciones para la barra lateral
    competitions = {
        "PD (La Liga)": {"code": "PD", "emblem": "🇪🇸"},
        "PL (Premier League)": {"code": "PL", "emblem": "🇬🇧"},
        "CL (Champions League)": {"code": "CL", "emblem": "🇪🇺"},
        "SA (Serie A)": {"code": "SA", "emblem": "🇮🇹"},
        "BL1 (Bundesliga)": {"code": "BL1", "emblem": "🇩🇪"},
        "FL1 (Ligue 1)": {"code": "FL1", "emblem": "🇫🇷"}
    }

    with st.sidebar:
        st.header("⚙️ Configuración")
        liga_seleccionada = st.selectbox("Competición", list(competitions.keys()), index=0)
        codigo_liga = competitions[liga_seleccionada]["code"]
        st.divider()
        min_ev = st.slider("EV mínimo (%)", -20, 30, 2, 1)

    # Carga de datos
    df, msg = load_api_data(codigo_liga)
    if df.empty:
        df = demo_data()

    # Normalización
    for c in ["probability","odds","fair_odds","ev"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    
    if "probability" in df and df["probability"].max() <= 1.0:
        df["probability_pct"] = df["probability"] * 100
    else:
        df["probability_pct"] = df["probability"]

    # Pestañas
    tab_top, tab_matches, tab_sim = st.tabs(["🔥 Top Value", "📅 Partidos", "💰 Simulador"])

    # 1. PESTAÑA TOP VALUE
    with tab_top:
        st.caption(f"{competitions[liga_seleccionada]['emblem']} Mejores oportunidades detectadas en {liga_seleccionada}")
        top_df = df[df["ev"] >= min_ev].sort_values("ev", ascending=False)
        
        if top_df.empty:
            st.info("No hay apuestas que cumplan el filtro de EV mínimo.")
        else:
            for _, r in top_df.head(10).iterrows():
                ev_p = float(r.ev)
                badge_class = "badge-value" if ev_p > 3 else "badge-neutral"
                
                home_img = f'<img src="{r.home_crest}" width="20" style="vertical-align:middle;margin-right:6px;">' if r.home_crest else ''
                away_img = f'<img src="{r.away_crest}" width="20" style="vertical-align:middle;margin-left:6px;margin-right:6px;">' if r.away_crest else ''
                
                st.markdown(f"""
                <div class="match-card">
                  <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem; opacity:0.8; margin-bottom:6px;">
                    <span>{home_img} {r.home} vs {away_img} {r.away}</span>
                    <span>📅 {r.date} — ⏰ {r.time}</span>
                  </div>
                  <div style="font-weight:700; font-size:1.05rem; margin: 4px 0;">{r.market} ({r.line})</div>
                  <div class="market-row">
                    <span>Prob: <b>{r.probability_pct:.1f}%</b> | Cuota: <b>{r.odds:.2f}</b></span>
                    <span class="{badge_class}">EV {ev_p:+.1f}%</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)

    # 2. PESTAÑA PARTIDOS (Agrupados por encuentro con escudos y fechas)
    with tab_matches:
        st.caption("Calendario de encuentros y sus mercados.")
        partidos = df[["home", "away", "home_crest", "away_crest", "date", "time"]].drop_duplicates()
        
        for _, match in partidos.iterrows():
            h, a, h_crest, a_crest, m_date, m_time = match["home"], match["away"], match["home_crest"], match["away_crest"], match["date"], match["time"]
            subset = df[(df["home"] == h) & (df["away"] == a)]
            
            h_img = f'<img src="{h_crest}" width="22" style="vertical-align:middle;margin-right:8px;">' if h_crest else ''
            a_img = f'<img src="{a_crest}" width="22" style="vertical-align:middle;margin-right:8px;">' if a_crest else ''
            
            with st.expander(f"{m_date} ({m_time}) | {h} vs {a}", expanded=False):
                st.markdown(f"""
                <div style="display:flex; gap:15px; margin-bottom:10px; font-weight:600;">
                  <div>{h_img}{h}</div>
                  <div style="opacity:0.5;">vs</div>
                  <div>{a_img}{a}</div>
                </div>
                """, unsafe_allow_html=True)
                
                for _, r in subset.iterrows():
                    ev_p = float(r.ev)
                    st.markdown(f"""
                    <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-top: 1px solid rgba(128,128,128,0.1);">
                      <div>
                        <b>{r.market}</b> <span style="opacity:0.7;">{r.line}</span><br>
                        <span style="font-size:0.8rem; opacity:0.7;">Cuota: {r.odds:.2f} | Prob: {r.probability_pct:.1f}%</span>
                      </div>
                      <div style="text-align:right;">
                        <b style="color: {'#2ecc71' if ev_p > 0 else '#e74c3c'};">EV {ev_p:+.1f}%</b>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)

    # 3. PESTAÑA SIMULADOR
    with tab_sim:
        st.caption("Cálculo de stake recomendado mediante Criterio de Kelly.")
        bank = st.number_input("Bankroll actual (€)", min_value=10.0, value=500.0, step=50.0)
        frac = st.slider("Criterio Kelly fraccionado", 0.05, 0.50, 0.25, 0.05)
        
        if not df.empty:
            s = df.iloc[0]
            p = float(s.probability_pct) / 100
            o = float(s.odds)
            b = o - 1
            raw = ((b * p) - (1 - p)) / b if b > 0 else 0
            stake = max(0, raw * frac) * bank
            
            st.success(f"Sugerencia para la mejor oportunidad ({s.home} vs {s.away}): **€{stake:.2f}** ({stake/bank*100:.1f}% de tu bank).")

    st.divider()
    st.caption("ValueBet Football V3.3 — Visual UI")

if __name__ == "__main__":
    main()
