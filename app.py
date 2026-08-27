import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import math
import os
import re
import unicodedata
import difflib

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

def render_html(content: str):
    """
    Igual que st.markdown(..., unsafe_allow_html=True) pero quitando
    la sangría de cada línea antes de renderizar.

    Streamlit interpreta con reglas de Markdown estándar: cualquier
    línea que empieza con 4+ espacios se trata como un bloque de
    código preformateado, no como HTML. Como las tarjetas de este
    archivo se escriben con f-strings indentadas (por estilo de
    código), sin este arreglo se mostraría el HTML como texto plano
    en vez de renderizarse.
    """
    lines = content.split("\n")
    dedented = "\n".join(line.lstrip() for line in lines)
    st.markdown(dedented, unsafe_allow_html=True)


def poisson_prob_over(expected_value, line):
    prob_under = 0
    for k in range(int(math.floor(line)) + 1):
        prob_under += (math.exp(-expected_value) * (expected_value**k)) / math.factorial(k)
    return max(0.01, min(0.99, 1 - prob_under))


# ============================================================
# MATCHING DE EQUIPOS (API football-data.org  ↔  CSV histórico)
# ============================================================
#
# El código original comparaba solo la PRIMERA PALABRA del nombre
# en minúsculas ("Real Madrid" -> "real"), lo que mezclaba
# estadísticas de equipos totalmente distintos que comparten esa
# primera palabra: Real Madrid / Real Sociedad / Real Betis / Real
# Valladolid, o Atlético Madrid / Athletic Club, etc.
#
# Esta versión: normaliza acentos/mayúsculas, quita sufijos de club
# poco informativos (FC, CF, AFC...), aplica un diccionario de alias
# para los casos más conflictivos de las 6 competiciones, y si nada
# de eso encuentra nada usa un match aproximado (difflib) con un
# umbral mínimo — si ni así hay una coincidencia fiable, NO se
# inventa una: el equipo se queda sin histórico de CSV y se avisa
# en el panel de diagnóstico en vez de mezclar datos de otro equipo.

TEAM_NAME_STOPWORDS = {
    "fc", "cf", "afc", "ac", "sc", "ssc", "cd", "ud", "rc", "rcd",
    "ca", "cfc", "club", "calcio", "futbol", "football", "de",
    "the", "1899", "1900", "1904", "1907", "1909", "1913", "1919",
}

# Fragmentos ya normalizados (nombre "oficial" de la API) -> nombre
# tal como aparece en los CSV de football-data.co.uk.
TEAM_ALIASES = {
    "atletico madrid": "ath madrid",
    "club atletico madrid": "ath madrid",
    "athletic club": "ath bilbao",
    "athletic bilbao": "ath bilbao",
    "real betis balompie": "betis",
    "real sociedad futbol": "sociedad",
    "real sociedad": "sociedad",
    "rayo vallecano madrid": "vallecano",
    "rayo vallecano": "vallecano",
    "celta vigo": "celta",
    "rcd espanyol barcelona": "espanol",
    "espanyol": "espanol",
    "real valladolid": "valladolid",
    "deportivo alaves": "alaves",
    "leganes": "leganes",
    "ud almeria": "almeria",
    "internazionale milano": "inter",
    "inter milan": "inter",
    "ac milan": "milan",
    "manchester united": "man united",
    "manchester city": "man city",
    "newcastle united": "newcastle",
    "wolverhampton wanderers": "wolves",
    "tottenham hotspur": "tottenham",
    "brighton hove albion": "brighton",
    "nottingham forest": "nott m forest",
    "west ham united": "west ham",
    "west bromwich albion": "west brom",
    "sheffield united": "sheffield united",
    "borussia dortmund": "dortmund",
    "borussia monchengladbach": "gladbach",
    "vfl borussia monchengladbach": "gladbach",
    "fc bayern munchen": "bayern munich",
    "bayer 04 leverkusen": "leverkusen",
    "eintracht frankfurt": "ein frankfurt",
    "tsg 1899 hoffenheim": "hoffenheim",
    "vfl wolfsburg": "wolfsburg",
    "vfb stuttgart": "stuttgart",
    "paris saint germain": "paris sg",
    "olympique marseille": "marseille",
    "olympique lyonnais": "lyon",
    "saint etienne": "st etienne",
    "as saint etienne": "st etienne",
}


def normalize_team_name(name: str) -> str:
    if not name:
        return ""

    text = unicodedata.normalize("NFKD", str(name))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    tokens = [
        t for t in text.split()
        if t and t not in TEAM_NAME_STOPWORDS
    ]

    return " ".join(tokens).strip()


@st.cache_data(ttl=3600)
def build_team_name_resolver(csv_team_names_tuple):
    """
    Precalcula, para cada nombre de equipo del CSV, su forma
    normalizada. Se cachea por CSV (la tupla de nombres forma parte
    de la clave de caché, así que cambiar de liga/CSV no reutiliza
    el resolver de otra liga).
    """
    return {
        normalize_team_name(name): name
        for name in csv_team_names_tuple
        if name
    }


def resolve_team_to_csv(api_team_name: str, csv_norm_to_original: dict):
    """
    Devuelve (nombre_exacto_en_csv, confianza) o (None, 0.0) si no
    hay una coincidencia suficientemente fiable. Nunca devuelve un
    match "a ciegas": mejor sin histórico que con el equipo
    equivocado.
    """
    if not csv_norm_to_original:
        return None, 0.0

    norm = normalize_team_name(api_team_name)

    if norm in TEAM_ALIASES:
        norm = TEAM_ALIASES[norm]

    # 1) coincidencia exacta tras normalizar / alias
    if norm in csv_norm_to_original:
        return csv_norm_to_original[norm], 1.0

    # 2) contención de subcadena en cualquier dirección, exigiendo
    #    solapamiento real (evita que "Real" case con cualquier
    #    "Real X" solo por 4 letras compartidas)
    best_name = None
    best_score = 0.0

    for csv_norm, original in csv_norm_to_original.items():

        if len(norm) < 4 or len(csv_norm) < 4:
            continue

        if norm in csv_norm or csv_norm in norm:
            score = (
                min(len(norm), len(csv_norm))
                / max(len(norm), len(csv_norm))
            )
            if score > best_score:
                best_score = score
                best_name = original

    if best_name and best_score >= 0.5:
        return best_name, best_score

    # 3) último recurso: coincidencia aproximada (fuzzy)
    close = difflib.get_close_matches(
        norm,
        list(csv_norm_to_original.keys()),
        n=1,
        cutoff=0.75,
    )

    if close:
        return csv_norm_to_original[close[0]], 0.75

    return None, 0.0

HISTORY_WINDOW_YEARS = 2

MARKET_LINES = {
    "⚽ Goles Totales": [1.5, 2.5, 3.5],
    "📐 Córners Totales": [8.5, 9.5, 10.5],
    "🟨 Tarjetas Totales": [2.5, 3.5, 4.5, 5.5],
    "🎯 Disparos a Puerta": [6.5, 8.5, 10.5],
}


def parse_csv_date_column(series: pd.Series) -> pd.Series:
    """
    Los CSV de football-data.co.uk usan fechas dd/mm/yy o dd/mm/yyyy
    según la temporada. Probamos ambos formatos.
    """
    parsed = pd.to_datetime(series, format="%d/%m/%y", errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed_alt = pd.to_datetime(
            series[missing], format="%d/%m/%Y", errors="coerce"
        )
        parsed.loc[missing] = parsed_alt
    return parsed


@st.cache_data(ttl=3600)
def load_multimarket_data(competition="PD"):
    try:
        api_key = st.secrets["FOOTBALL_DATA_API_KEY"]
    except Exception:
        return pd.DataFrame(), "Falta la clave secreta en st.secrets.", []

    headers = {"X-Auth-Token": api_key}
    matches_url = f"https://api.football-data.org/v4/competitions/{competition}/matches?status=SCHEDULED"

    try:
        resp_matches = requests.get(matches_url, headers=headers, timeout=10)
        if resp_matches.status_code != 200:
            return pd.DataFrame(), f"Error al conectar con la API ({resp_matches.status_code})", []

        matches_data = resp_matches.json().get("matches", [])

        csv_file = f"historico_{competition}.csv"
        if competition == "PD" and not os.path.exists(csv_file) and os.path.exists("historico_liga.csv"):
            csv_file = "historico_liga.csv"

        df_hist = pd.DataFrame()
        if os.path.exists(csv_file):
            try:
                df_hist = pd.read_csv(csv_file, encoding='latin1')
                df_hist.columns = df_hist.columns.str.replace('ï»¿', '').str.strip()
                if 'HomeTeam' in df_hist.columns:
                    df_hist['HomeTeam'] = df_hist['HomeTeam'].astype(str).str.strip().str.lower()
                if 'AwayTeam' in df_hist.columns:
                    df_hist['AwayTeam'] = df_hist['AwayTeam'].astype(str).str.strip().str.lower()

                # Ventana de 2 años: si el CSV trae columna de fecha,
                # descartamos partidos más antiguos. Si no hay columna
                # de fecha reconocible, usamos el CSV completo (mejor
                # eso que quedarnos sin histórico).
                if 'Date' in df_hist.columns:
                    parsed_dates = parse_csv_date_column(df_hist['Date'])
                    cutoff = datetime.now() - timedelta(days=365 * HISTORY_WINDOW_YEARS)
                    keep_mask = parsed_dates.isna() | (parsed_dates >= cutoff)
                    df_hist = df_hist[keep_mask]

            except Exception:
                df_hist = pd.DataFrame()

        # Resolver de nombres de equipo (API -> nombre exacto del CSV).
        csv_team_names = tuple(sorted(set(
            list(df_hist['HomeTeam'].unique()) + list(df_hist['AwayTeam'].unique())
        ))) if not df_hist.empty and 'HomeTeam' in df_hist.columns and 'AwayTeam' in df_hist.columns else tuple()

        csv_norm_to_original = build_team_name_resolver(csv_team_names)

        unmatched_teams = set()
        match_confidence = {}

        parsed_data = []
        league_avg_goals = 1.3

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

            h_gf, h_ga, a_gf, a_ga = league_avg_goals, league_avg_goals, league_avg_goals, league_avg_goals
            h_c, a_c = 4.8, 4.2
            h_y, a_y = 2.2, 2.4
            h_s, a_s = 4.5, 4.0

            has_required_cols = (
                not df_hist.empty
                and {'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'}.issubset(df_hist.columns)
            )

            if has_required_cols:

                resolved_home, score_home = resolve_team_to_csv(
                    home, csv_norm_to_original
                )
                resolved_away, score_away = resolve_team_to_csv(
                    away, csv_norm_to_original
                )

                match_confidence[home] = (resolved_home, score_home)
                match_confidence[away] = (resolved_away, score_away)

                if resolved_home is None:
                    unmatched_teams.add(home)
                if resolved_away is None:
                    unmatched_teams.add(away)

                home_games = (
                    df_hist[df_hist['HomeTeam'] == resolved_home]
                    if resolved_home else pd.DataFrame()
                )
                away_games_as_home = (
                    df_hist[df_hist['AwayTeam'] == resolved_home]
                    if resolved_home else pd.DataFrame()
                )

                away_games = (
                    df_hist[df_hist['AwayTeam'] == resolved_away]
                    if resolved_away else pd.DataFrame()
                )
                home_games_as_away = (
                    df_hist[df_hist['HomeTeam'] == resolved_away]
                    if resolved_away else pd.DataFrame()
                )

                hg_list, ha_list, hc_list, hy_list, hs_list = [], [], [], [], []
                if not home_games.empty:
                    hg_list.append(home_games['FTHG'].mean())
                    ha_list.append(home_games['FTAG'].mean())
                    if 'HC' in home_games.columns: hc_list.append(home_games['HC'].mean())
                    if 'HY' in home_games.columns: hy_list.append(home_games['HY'].mean())
                    if 'HST' in home_games.columns: hs_list.append(home_games['HST'].mean())
                if not away_games_as_home.empty:
                    hg_list.append(away_games_as_home['FTAG'].mean())
                    ha_list.append(away_games_as_home['FTHG'].mean())
                    if 'AC' in away_games_as_home.columns: hc_list.append(away_games_as_home['AC'].mean())
                    if 'AY' in away_games_as_home.columns: hy_list.append(away_games_as_home['AY'].mean())
                    if 'AST' in away_games_as_home.columns: hs_list.append(away_games_as_home['AST'].mean())

                if hg_list: h_gf = sum(hg_list) / len(hg_list)
                if ha_list: h_ga = sum(ha_list) / len(ha_list)
                if hc_list: h_c = sum(hc_list) / len(hc_list)
                if hy_list: h_y = sum(hy_list) / len(hy_list)
                if hs_list: h_s = sum(hs_list) / len(hs_list)

                ag_list, aa_list, ac_list, ay_list, as_list = [], [], [], [], []
                if not away_games.empty:
                    ag_list.append(away_games['FTAG'].mean())
                    aa_list.append(away_games['FTHG'].mean())
                    if 'AC' in away_games.columns: ac_list.append(away_games['AC'].mean())
                    if 'AY' in away_games.columns: ay_list.append(away_games['AY'].mean())
                    if 'AST' in away_games.columns: as_list.append(away_games['AST'].mean())
                if not home_games_as_away.empty:
                    ag_list.append(home_games_as_away['FTHG'].mean())
                    aa_list.append(home_games_as_away['FTAG'].mean())
                    if 'HC' in home_games_as_away.columns: ac_list.append(home_games_as_away['HC'].mean())
                    if 'HY' in home_games_as_away.columns: ay_list.append(home_games_as_away['HY'].mean())
                    if 'HST' in home_games_as_away.columns: as_list.append(home_games_as_away['HST'].mean())

                if ag_list: a_gf = sum(ag_list) / len(ag_list)
                if aa_list: a_ga = sum(aa_list) / len(aa_list)
                if ac_list: a_c = sum(ac_list) / len(ac_list)
                if ay_list: a_y = sum(ay_list) / len(ay_list)
                if as_list: a_s = sum(as_list) / len(as_list)

            home_exp_g = max(0.3, (h_gf + a_ga) / 2)
            away_exp_g = max(0.3, (a_gf + h_ga) / 2)
            total_exp_goals = home_exp_g + away_exp_g

            exp_corners = max(4.0, h_c + a_c)
            exp_cards = max(1.5, h_y + a_y)
            exp_shots = max(3.0, h_s + a_s)

            rand_factor = (hash(home + away) % 15) / 100.0

            expected_by_market = {
                "⚽ Goles Totales": (total_exp_goals, rand_factor),
                "📐 Córners Totales": (exp_corners, rand_factor / 2),
                "🟨 Tarjetas Totales": (exp_cards, rand_factor),
                "🎯 Disparos a Puerta": (exp_shots, rand_factor),
            }

            for market_name, lines in MARKET_LINES.items():

                expected_value, margin_factor = expected_by_market[market_name]

                for line in lines:

                    prob = poisson_prob_over(expected_value, line)
                    fair = 1 / prob
                    odds = round(fair * (0.92 + margin_factor), 2)
                    ev = (prob * odds) - 1

                    if prob >= 0.20:
                        rating = "🔥 VALUE" if ev > 0.02 else "⚖️ NEUTRAL"
                        parsed_data.append([
                            home, away, home_crest, away_crest, match_date_str, match_date_obj, match_time,
                            market_name, f"+{line}", prob, odds, fair, ev, rating
                        ])

        diagnostics = sorted(unmatched_teams)

        if parsed_data:
            df_out = pd.DataFrame(
                parsed_data,
                columns=["home","away","home_crest","away_crest","date","date_obj","time","market","line","probability","odds","fair_odds","ev","rating"]
            )
            return df_out, "OK", diagnostics
        else:
            return pd.DataFrame(), "No hay suficientes datos.", diagnostics

    except Exception as e:
        return pd.DataFrame(), str(e), []

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

    df, msg, unmatched_teams = load_multimarket_data(codigo_liga)
    if df.empty:
        st.warning(f"⚠️ {msg}")
        return

    df["probability_pct"] = df["probability"] * 100

    if unmatched_teams:
        with st.sidebar:
            with st.expander(
                f"⚠️ {len(unmatched_teams)} equipo(s) sin histórico "
                f"CSV fiable"
            ):
                st.caption(
                    "Estos equipos no encontraron una coincidencia "
                    "suficientemente segura en el CSV, así que sus "
                    "predicciones usan medias de liga genéricas en "
                    "vez de su propio historial. Revisa si el "
                    "nombre en el CSV es muy distinto o si falta "
                    "ese equipo."
                )
                for team in unmatched_teams:
                    st.caption(f"• {team}")

    tab_top, tab_matches, tab_sim = st.tabs(["🔥 Top Value por Fecha", "📅 Partidos y Mercados", "💰 Simulador"])

    with tab_top:
        st.caption(f"{competitions[liga_seleccionada]['emblem']} Pronósticos basados en métricas históricas reales por equipo")
        
        selected_date = st.date_input("Consultar pronósticos para la fecha:", value=datetime.now().date())
        selected_date_str = selected_date.strftime("%d/%m")
        
        day_df = df[df["date_obj"] == selected_date]
        top_df = day_df[day_df["ev"] >= (min_ev / 100.0)].sort_values("ev", ascending=False)
        
        if top_df.empty:
            st.info(f"ℹ️ No hay pronósticos con valor mínimo para el día **{selected_date_str}**. Prueba seleccionando otra fecha en el calendario.")
        else:
            st.markdown(f"**Mostrando pronósticos para el {selected_date_str}:**")
            for _, r in top_df.head(10).iterrows():
                ev_p = float(r.ev) * 100
                badge_class = "badge-value" if ev_p > 3 else "badge-neutral"
                
                home_img = f'<img src="{r.home_crest}" width="20" style="vertical-align:middle;margin-right:6px;">' if r.home_crest else ''
                away_img = f'<img src="{r.away_crest}" width="20" style="vertical-align:middle;margin-left:6px;margin-right:6px;">' if r.away_crest else ''
                
                render_html(f"""
                <div class="match-card">
                  <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem; opacity:0.8; margin-bottom:6px;">
                    <span>{home_img} {r.home} vs {away_img} {r.away}</span>
                    <span>📅 {r.date} — ⏰ {r.time}</span>
                  </div>
                  <div style="font-weight:700; font-size:1.05rem; margin: 4px 0;">{r.market} ({r.line})</div>
                  <div>Prob: <b>{r.probability_pct:.1f}%</b> | Cuota: <b>{r.odds:.2f}</b> <span class="{badge_class}">EV {ev_p:+.1f}%</span></div>
                </div>
                """)

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
            
            with st.expander(f"📌 {m_date} ({m_time})  |  {h} vs {a}  ({len(subset)} mercados)", expanded=False):
                render_html(f"""
                <div style="display:flex; align-items:center; justify-content:space-between; background:rgba(128,128,128,0.06); padding:10px 14px; border-radius:10px; margin-bottom:12px;">
                  <div>{h_img}<b>{h}</b></div>
                  <div style="font-size:0.85rem; opacity:0.6; font-weight:bold;">VS</div>
                  <div>{a_img}<b>{a}</b></div>
                </div>
                """)
                
                for _, r in subset.iterrows():
                    ev_p = float(r.ev) * 100
                    color_ev = '#2ecc71' if ev_p > 0 else '#e74c3c'
                    badge_bg = 'rgba(46, 204, 113, 0.12)' if ev_p > 0 else 'rgba(231, 76, 60, 0.12)'
                    
                    render_html(f"""
                    <div class="market-box">
                      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-weight:700; font-size:0.95rem;">{r.market} <span style="opacity:0.7; font-weight:normal;">({r.line})</span></span>
                        <span style="background:{badge_bg}; color:{color_ev}; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.8rem;">EV {ev_p:+.1f}%</span>
                      </div>
                      <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.85rem; opacity:0.85; margin-top:6px;">
                        <div>Probabilidad: <b>{r.probability_pct:.1f}%</b></div>
                        <div>Cuota: <b>{r.odds:.2f}</b> <span style="font-size:0.75rem; opacity:0.6;">(Justa: {r.fair_odds:.2f})</span></div>
                      </div>
                    </div>
                    """)

    with tab_sim:
        st.caption("Cálculo de stake mediante Criterio de Kelly.")
        bank = st.number_input("Bankroll actual (€)", min_value=10.0, value=500.0, step=50.0)
        frac = st.slider("Criterio Kelly fraccionado", 0.05, 0.50, 0.25, 0.05)

        if not df.empty:

            df_sim = df.copy()
            df_sim["label"] = (
                df_sim["date"] + " " + df_sim["time"] + " · "
                + df_sim["home"] + " vs " + df_sim["away"] + " — "
                + df_sim["market"] + " " + df_sim["line"]
                + " (EV " + (df_sim["ev"] * 100).round(1).astype(str) + "%)"
            )

            df_sim = df_sim.sort_values("ev", ascending=False)

            selected_label = st.selectbox(
                "Partido y mercado a simular",
                df_sim["label"].tolist(),
            )

            s = df_sim[df_sim["label"] == selected_label].iloc[0]

            p = float(s.probability_pct) / 100
            o = float(s.odds)
            b = o - 1
            raw = ((b * p) - (1 - p)) / b if b > 0 else 0
            stake = max(0, raw * frac) * bank

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Probabilidad", f"{p * 100:.1f}%")
            with col2:
                st.metric("Cuota", f"{o:.2f}")
            with col3:
                st.metric("EV", f"{(s.ev * 100):+.1f}%")

            st.success(
                f"Sugerencia para **{s.home} vs {s.away}** · "
                f"{s.market} {s.line}: **€{stake:.2f}** "
                f"({stake/bank*100:.1f}% de tu bank)."
            )

            if s.ev <= 0:
                st.caption(
                    "⚠️ Esta selección tiene EV ≤ 0 según el modelo — "
                    "el Kelly recomendado es 0€. Elige una opción con "
                    "EV positivo si buscas una apuesta de valor."
                )

    st.divider()
    st.caption("ValueBet Football Pro V9.2 — Matching de equipos + ventana 2 años + fix HTML")

if __name__ == "__main__":
    main()
