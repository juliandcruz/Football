import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import math
import os

st.set_page_config(
    page_title="ValueBet Football Pro",
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
.market-box {
  background: rgba(128,128,128,.04); border: 1px solid rgba(128,128,128,.12);
  border-radius: 10px; padding: 10px 12px; margin-bottom: 8px;
}
.badge-value { background: rgba(46, 204, 113, 0.15); color: #2ecc71; padding: 3px 8px; border-radius: 8px; font-weight: 700; font-size: 0.75rem;}
.badge-neutral { background: rgba(128, 128, 128, 0.15); opacity: 0.8; padding: 3px 8px; border-radius: 8px; font-size: 0.75rem;}
</style>
""", unsafe_allow_html=True)

def poisson_prob_over(expected_value, line):
    prob_under = 0
    for k in range(int(math.floor(line)) + 1):
        prob_under += (math.exp(-expected_value) * (expected_value**k)) / math.factorial(k)
    prob_over = max(0.01, min(0.99, 1 - prob_under))
    return prob_over

@st.cache_data(ttl=3600)
def load_historical_csv_stats(competition="PD"):
    """Carga estadísticas históricas dinámicamente según la competición seleccionada"""
    historical_stats = {}
    csv_file = f"historico_{competition}.csv"
    
    if competition == "PD" and not os.path.exists(csv_file) and os.path.exists("historico_liga.csv"):
        csv_file = "historico_liga.csv"

    if os.path.exists(csv_file):
        try:
            df_hist = pd.read_csv(csv_file, encoding='latin1')
            
            if {'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'}.issubset(df_hist.columns):
                for team in pd.concat([df_hist['HomeTeam'], df_hist['AwayTeam']]).unique():
                    home_games = df_hist[df_hist['HomeTeam'] == team]
                    away_games = df_hist[df_hist['AwayTeam'] == team]
                    
                    h_gf = home_games['FTHG'].mean() if not home_games.empty else 1.3
                    h_ga = home_games['FTAG'].mean() if not home_games.empty else 1.3
                    a_gf = away_games['FTAG'].mean() if not away_games.empty else 1.1
                    a_ga = away_games['FTHG'].mean() if not away_games.empty else 1.3
                    
                    historical_stats[team] = {
                        "home_gf": h_gf, "home_ga": h_ga,
                        "away_gf": a_gf, "away_ga": a_ga
                    }
                st.sidebar.success(f"📂 Histórico ({competition}) cargado: {len(historical_stats)} equipos.")
            else:
                st.sidebar.error("❌ El CSV no tiene las columnas requeridas (HomeTeam, AwayTeam, FTHG, FTAG).")
        except Exception as e:
            st.sidebar.error(f"❌ Error al leer el CSV: {str(e)}")
    else:
        st.sidebar.warning(f"⚠️ No se encontró el archivo {csv_file}")
            
    return historical_stats

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
                table_type = st_type.get("type") 
                if table_type in ["HOME", "AWAY"]:
                    for row in st_type.get("table", []):
                        t_name = row["team"]["name"]
                        played = max(1, row.get("playedGames", 1))
                        gf = row.get("goalsFor", 0) / played
                        ga = row.get("goalsAgainst", 0) / played
                        
                        if t_name not in team_stats:
                            team_stats[t_name] = {}
                        
                        if table_type == "HOME":
                            team_stats[t_name]["home_gf"] = gf
                            team_stats[t_name]["home_ga"] = ga
                        else:
                            team_stats[t_name]["away_gf"] = gf
                            team_stats[t_name]["away_ga"] = ga

        hist_stats = load_historical_csv_stats(competition)
        
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
                match_date_str = dt.strftime("%d/%m")
                match_date_obj = dt.date()
                match_time = dt.strftime("%H:%M")
            except:
                match_date_str = "Próx."
                match_date_obj = datetime.now().date()
                match_time = ""

            h_data = team_stats.get(home, {})
            h_hist = hist_stats.get(home, {})
            
            h_gf = h_data.get("home_gf", h_hist.get("home_gf", league_avg_goals))
            h_ga = h_data.get("home_ga", h_hist.get("home_ga", league_avg_goals))
            
            a_data = team_stats.get(away, {})
            a_hist = hist_stats.get(away, {})
            
            a_gf = a_data.get("away_gf", a_hist.get("away_gf", league_avg_goals))
            a_ga = a_data.get("away_ga", a_hist.get("away_ga", league_avg_goals))
            
            home_exp_g = (h_gf + a_ga) / 2
            away_exp_g = (a_gf + h_ga) / 2
            
            prob_goals = poisson_prob_over(home_exp_g + away_exp_g, 2.5)
            fair_g = 1 / prob_goals
            odds_g = round(fair_g * np.random.uniform(0.96, 1.12), 2)
            ev_g = (prob_goals * odds_g) - 1
            
            exp_corners = 9.2 + (home_exp_g - 1.2) * 1.5 + (away_exp_g - 1.2) * 1.0
            prob_corners = poisson_prob_over(exp_corners, 9.5)
            fair_c = 1 / prob_corners
            odds_c = round(fair_c * np.random.uniform(0.95, 1.14), 2)
            ev_c = (prob_corners * odds_c) - 1

            exp_cards = 4.6
            prob_cards = poisson_prob_over(exp_cards, 4.5)
            fair_cards = 1 / prob_cards
            odds_cards = round(fair_cards * np.random.uniform(0.97, 1.12), 2)
            ev_cards = (prob_cards * odds_cards) - 1

            exp_shots = 8.8 + (home_exp_g + away_exp_g) * 1.2
            prob_shots = poisson_prob_over(exp_shots, 8.5)
            fair_shots = 1 / prob_shots
            odds_shots = round(fair_shots * np.random.uniform(0.95, 1.15), 2)
            ev_shots = (prob_shots * odds_shots) - 1

            markets = [
                ("⚽ Goles Totales", "+2.5", prob_goals, odds_g, fair_g, ev_g),
                ("📐 Córners Totales", "+9.5", prob_corners, odds_c, fair_c, ev_c),
                ("🟨 Tarjetas Totales", "+4.5", prob_cards, odds_cards, fair_cards, ev_cards),
                ("🎯 Disparos a Puerta", "+8.5", prob_shots, odds_shots, fair_shots, ev_shots)
            ]

            for mkt, line, prob, odds, fair, ev in markets:
                if prob >= 0.45:
                    rating = "🔥 VALUE" if ev > 0.04 else "⚖️ NEUTRAL"
                    parsed_data.append([
                        home, away, home_crest, away_crest, match_date_str, match_date_obj, match_time,
                        mkt, line, prob, odds, fair, ev, rating
                    ])
            
        if parsed_data:
            return pd.DataFrame(parsed_data, columns=["home","away","home_crest","away_crest","date","date_obj","time","market","line","probability","odds","fair_odds","ev","rating"]), "OK"
        else:
            return pd.DataFrame(), "No hay partidos que cumplan el filtro de probabilidad mínima (45%)."
            
    except Exception as e:
        return pd.DataFrame(), str(e)

def main():
    st.title("⚽ ValueBet Pro")

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

    tab_top, tab_matches, tab_sim = st.tabs(["🔥 Top Value por Fecha", "📅 Partidos y Mercados", "💰 Simulador"])

    with tab_top:
        st.caption(f"{competitions[liga_seleccionada]['emblem']} Pronósticos basados en rendimiento actual + histórico CSV (Prob > 45%)")
        
        col_date, col_info = st.columns([2, 3])
        with col_date:
            selected_date = st.date_input("Consultar pronósticos para la fecha:", value=datetime.now().date())
        
        selected_date_str = selected_date.strftime("%d/%m")
        
        day_df = df[df["date_obj"] == selected_date]
        top_df = day_df[day_df["ev"] >= (min_ev / 100.0)].sort_values("ev", ascending=False)
        
        if top_df.empty:
            st.info(f"ℹ️ No hay pronósticos con valor mínimo para el día **{selected_date_str}**. Prueba a seleccionar otra fecha o revisa la pestaña de Partidos y Mercados.")
        else:
            st.markdown(f"**Mostrando pronósticos para el {selected_date_str}:**")
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
        st.caption("📅 Calendario detallado y análisis de mercados por encuentro.")
        partidos = df[["home", "away", "home_crest", "away_crest", "date", "time"]].drop_duplicates()
        
        for _, match in partidos.iterrows():
            h, a, h_crest, a_crest, m_date, m_time = match["home"], match["away"], match["home_crest"], match["away_crest"], match["date"], match["time"]
            subset = df[(df["home"] == h) & (df["away"] == a)]
            
            if subset.empty:
                continue
                
            h_img = f'<img src="{h_crest}" width="22" style="vertical-align:middle;margin-right:8px;">' if h_crest else ''
            a_img = f'<img src="{a_crest}" width="22" style="vertical-align:middle;margin-right:8px;">' if a_crest else ''
            
            num_mercados = len(subset)
            
            with st.expander(f"📌 {m_date} ({m_time})  |  {h} vs {a}  ({num_mercados} mercados)", expanded=False):
                st.markdown(f"""
                <div style="display:flex; align-items:center; justify-content:space-between; background:rgba(128,128,128,0.06); padding:10px 14px; border-radius:10px; margin-bottom:12px;">
                  <div>{h_img}<b>{h}</b></div>
                  <div style="font-size:0.85rem; opacity:0.6; font-weight:bold;">VS</div>
                  <div>{a_img}<b>{a}</b></div>
                </div>
                """, unsafe_allow_html=True)
                
                for _, r in subset.iterrows():
                    ev_p = float(r.ev) * 100
                    color_ev = '#2ecc71' if ev_p > 0 else '#e74c3c'
                    badge_bg = 'rgba(46, 204, 113, 0.12)' if ev_p > 0 else 'rgba(231, 76, 60, 0.12)'
                    
                    st.markdown(f"""
                    <div class="market-box">
                      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-weight:700; font-size:0.95rem;">{r.market} <span style="opacity:0.7; font-weight:normal;">({r.line})</span></span>
                        <span style="background:{badge_bg}; color:{color_ev}; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.8rem;">EV {ev_p:+.1f}%</span>
                      </div>
                      <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.85rem; opacity:0.85; margin-top:6px;">
                        <div>Probabilidad: <b>{r.probability_pct:.1f}%</b></div>
                        <div>Cuota: <b>{r.odds:.2f}</b> <span style="font-size:0.75rem; opacity:0.6;">(Justa: {r.fair_odds:.2f})</span></div>
                      </div>
                      <div style="width:100%; background:rgba(128,128,128,0.15); height:4px; border-radius:2px; margin-top:6px;">
                        <div style="width:{min(100, r.probability_pct)}%; background:#3498db; height:4px; border-radius:2px;"></div>
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
    st.caption("ValueBet Football Pro V8.4 — Clean Reset Engine")

if __name__ == "__main__":
    main()
