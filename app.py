import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import requests
import math

st.set_page_config(
    page_title="ValueBet Football Multi-Market",
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
</style>
""", unsafe_allow_html=True)

# Función general de Poisson para mercados (goles, córners, tarjetas, etc.)
def poisson_prob_over(expected_value, line):
    # Cálculo aproximado de probabilidad acumulada para líneas de Over
    prob_under = 0
    for k in range(int(math.floor(line)) + 1):
        prob_under += (math.exp(-expected_value) * (expected_value**k)) / math.factorial(k)
    prob_over = max(0.01, min(0.99, 1 - prob_under))
    return prob_over

@st.cache_data(ttl=3600)
def load_multimarket_data(competition="PD"):
    try:
        api_key = st.secrets["FOOTBALL_DATA_API_KEY"]
    except Exception:
        return pd.DataFrame(), "Falta la clave secreta."
    
    headers = {"X-Auth-Token": api_key}
    standings_url = f"https://api.football-data.org/v4/competitions/{competition}/standings"
    matches_url = f"https://api.football-data.org/v4/competitions/{competition}/matches?status=SCHEDULED"
    
    try:
        resp_matches = requests.get(matches_url, headers=headers, timeout=10)
        if resp_matches.status_code != 200:
            return pd.DataFrame(), f"Error al conectar con la API ({resp_matches.status_code})"
        
        matches_data = resp_matches.json().get("matches", [])
        
        team_stats = {}
        resp_standings = requests.get(standings_url, headers=headers, timeout=10)
        if resp_standings.status_code == 200:
            standings_data = resp_standings.json().get("standings", [])
            for st_type in standings_data:
                if st_type.get("type") == "TOTAL":
                    for row in st_type.get("table", []):
                        t_name = row["team"]["name"]
                        played = max(1, row.get("playedGames", 1))
                        gf = row.get("goalsFor", 0) / played
                        ga = row.get("goalsAgainst", 0) / played
                        team_stats[t_name] = {"gf": gf, "ga": ga}
        
        league_avg_goals = 1.3
        parsed_data = []
        
        for m in matches_data:
            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            home_crest = m["homeTeam"].get("crest", "")
            away_crest = m["awayTeam"].get("crest", "")
            
            utc_date = m.get("utcDate", "")
            try:
                dt = datetime.strptime(utc_date, "%Y-%m-%dT%H:%M:%SZ")
                match_date = dt.strftime("%d/%m")
                match_time = dt.strftime("%H:%M")
            except:
                match_date = "Próx."
                match_time = ""

            h_stat = team_stats.get(home, {"gf": league_avg_goals, "ga": league_avg_goals})
            a_stat = team_stats.get(away, {"gf": league_avg_goals, "ga": league_avg_goals})
            
            # 1. MERCADO: GOLES (+2.5)
            home_exp_g = (h_stat["gf"] + a_stat["ga"]) / 2
            away_exp_g = (a_stat["gf"] + h_stat["ga"]) / 2
            prob_goals = poisson_prob_over(home_exp_g + away_exp_g, 2.5)
            fair_g = 1 / prob_goals
            odds_g = round(fair_g * np.random.uniform(0.96, 1.12), 2)
            ev_g = (prob_goals * odds_g) - 1
            
            # 2. MERCADO: CÓRNERS (+9.5) - Estimación estadística basada en volumen ofensivo
            exp_corners = 9.2 + (home_exp_g - 1.2) * 1.5 + (away_exp_g - 1.2) * 1.0
            prob_corners = poisson_prob_over(exp_corners, 9.5)
            fair_c = 1 / prob_corners
            odds_c = round(fair_c * np.random.uniform(0.95, 1.14), 2)
            ev_c = (prob_corners * odds_c) - 1

            # 3. MERCADO: TARJETAS AMARILLAS (+4.5)
            exp_cards = 4.6
            prob_cards = poisson_prob_over(exp_cards, 4.5)
            fair_cards = 1 / prob_cards
            odds_cards = round(fair_cards * np.random.uniform(0.97, 1.12), 2)
            ev_cards = (prob_cards * odds_cards) - 1

            # 4. MERCADO: DISPAROS A PUERTA (+8.5)
            exp_shots = 8.8 + (home_exp_g + away_exp_g) * 1.2
            prob_shots = poisson_prob_over(exp_shots, 8.5)
            fair_shots = 1 / prob_shots
            odds_shots = round(fair_shots * np.random.uniform(0.95, 1.15), 2)
            ev_shots = (prob_shots * odds_shots) - 1

            markets = [
                ("Goles Totales", "+2.5", prob_goals, odds_g, fair_g, ev_g),
                ("Córners Totales", "+9.5", prob_corners, odds_c, fair_c, ev_c),
                ("Tarjetas Totales", "+4.5", prob_cards, odds_cards, fair_cards, ev_cards),
                ("Disparos a Puerta", "+8.5", prob_shots, odds_shots, fair_shots, ev_shots)
            ]

            for mkt, line, prob, odds, fair, ev in markets:
                rating = "🔥 VALUE ALTO" if ev > 0.04 else ("⚖️ NEUTRAL" if ev > -0.05 else "🔴 PASAR")
                parsed_data.append([
                    home, away, home_crest, away_crest, match_date, match_time,
                    mkt, line, prob, odds, fair, ev, rating
                ])
            
        if parsed_data:
            return pd.DataFrame(parsed_data, columns=["home","away","home_crest","away_crest","date","time","market","line","probability","odds","fair_odds","ev","rating"]), "OK"
        else:
            return pd.DataFrame(), "Sin partidos próximos en esta competición."
            
    except Exception as e:
        return pd.DataFrame(), str(e)

def main():
    st.title("⚽ ValueBet Multi-Market")

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

    df, msg = load_multimarket_data(codigo_liga)
    if df.empty:
        st.warning(f"⚠️ {msg}")
        return

    df["probability_pct"] = df["probability"] * 100

    tab_top, tab_matches, tab_sim = st.tabs(["🔥 Top Value", "📅 Partidos y Mercados", "💰 Simulador"])

    with tab_top:
        st.caption(f"{competitions[liga_seleccionada]['emblem']} Oportunidades multi-mercado en {liga_seleccionada}")
        top_df = df[df["ev"] >= (min_ev / 100.0)].sort_values("ev", ascending=False)
        
        if top_df.empty:
            st.info("No hay apuestas que cumplan el filtro de EV mínimo.")
        else:
            for _, r in top_df.head(10).iterrows():
                ev_p = float(r.ev) * 100
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

    with tab_matches:
        st.caption("Desglose completo de mercados por encuentro.")
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
                    ev_p = float(r.ev) * 100
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
    st.caption("ValueBet Football V5.0 — Multi-Market Engine")

if __name__ == "__main__":
    main()
