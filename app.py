import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, timezone
import requests
import math
from pathlib import Path

# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="ValueBet Football Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {
    max-width: 1200px;
    padding: 1rem .6rem 4rem .6rem;
}

h1 {
    font-size: 1.6rem !important;
}

h2 {
    font-size: 1.25rem !important;
    margin-top: 1rem !important;
}

.match-card {
    padding: 14px;
    border-radius: 16px;
    border: 1px solid rgba(128,128,128,.2);
    margin-bottom: 12px;
    background: rgba(128,128,128,.03);
}

.market-box {
    background: rgba(128,128,128,.04);
    border: 1px solid rgba(128,128,128,.12);
    border-radius: 10px;
    padding: 10px 12px;
    margin-bottom: 8px;
}

.badge-value {
    background: rgba(46, 204, 113, 0.15);
    color: #2ecc71;
    padding: 3px 8px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 0.75rem;
}

.badge-neutral {
    background: rgba(128, 128, 128, 0.15);
    opacity: 0.8;
    padding: 3px 8px;
    border-radius: 8px;
    font-size: 0.75rem;
}

.badge-pass {
    background: rgba(231, 76, 60, 0.12);
    color: #e74c3c;
    padding: 3px 8px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 0.75rem;
}

.stat-line {
    font-size: .85rem;
    opacity: .85;
}

.warning-box {
    padding: 12px;
    border-radius: 10px;
    background: rgba(241,196,15,.10);
    border: 1px solid rgba(241,196,15,.25);
    margin-bottom: 12px;
}
</style>
""", unsafe_allow_html=True)


# ============================================================
# CONSTANTES
# ============================================================

MIN_PROBABILITY = 0.45
MIN_EV = 0.03

KELLY_FRACTION_DEFAULT = 0.25
MAX_KELLY_STAKE = 0.02

DEFAULT_LEAGUE_GOALS = 2.60
DEFAULT_CORNERS = 9.5
DEFAULT_CARDS = 4.5
DEFAULT_SOT = 8.5


# ============================================================
# UTILIDADES
# ============================================================

def safe_float(value, default=np.nan):
    try:
        return float(value)
    except Exception:
        return default


def poisson_pmf(k, lam):
    if lam <= 0:
        return 0.0

    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def poisson_prob_over(expected_value, line):
    """
    P(X > line)

    Para una línea 2.5:
        P(X >= 3)

    Para una línea 2.0:
        P(X >= 3)
    """

    expected_value = max(0.01, float(expected_value))
    line = float(line)

    threshold = math.floor(line) + 1

    prob_under_or_equal = sum(
        poisson_pmf(k, expected_value)
        for k in range(threshold)
    )

    probability = 1.0 - prob_under_or_equal

    return max(0.001, min(0.999, probability))


def fair_odds(probability):
    if probability <= 0:
        return np.nan

    return 1.0 / probability


def implied_probability(odds):
    if odds is None or pd.isna(odds) or odds <= 1:
        return np.nan

    return 1.0 / odds


def expected_value(probability, odds):
    if odds is None or pd.isna(odds) or odds <= 1:
        return np.nan

    return (probability * odds) - 1


def edge_probability(probability, odds):
    implied = implied_probability(odds)

    if pd.isna(implied):
        return np.nan

    return probability - implied


def fractional_kelly(
    probability,
    odds,
    fraction=KELLY_FRACTION_DEFAULT,
    max_stake=MAX_KELLY_STAKE
):
    """
    Kelly fraccionado y limitado.

    max_stake=0.02 significa máximo 2% del bankroll.
    """

    if pd.isna(odds) or odds <= 1:
        return 0.0

    p = float(probability)
    q = 1.0 - p
    b = odds - 1.0

    raw_kelly = ((b * p) - q) / b

    if raw_kelly <= 0:
        return 0.0

    stake = raw_kelly * fraction

    return min(stake, max_stake)


def classify_value(ev):
    if pd.isna(ev):
        return "📊 SIN CUOTA"

    ev_pct = ev * 100

    if ev_pct >= 8:
        return "🔥 VALUE ALTO"

    if ev_pct >= 3:
        return "🟢 VALUE"

    if ev_pct >= 0:
        return "⚖️ NEUTRAL"

    return "🔴 PASAR"


def confidence_score(probability, sample_quality):
    """
    Indicador sencillo de confianza.
    NO representa una probabilidad de acierto adicional.
    """

    distance = abs(probability - 0.5)

    score = 50 + distance * 100

    score *= sample_quality

    return max(0, min(100, score))


# ============================================================
# PARSEO DE FECHAS
# ============================================================

def parse_utc_datetime(utc_date):
    if not utc_date:
        return None

    try:
        dt = datetime.fromisoformat(
            utc_date.replace("Z", "+00:00")
        )

        return dt

    except Exception:
        return None


def local_match_info(utc_date):
    dt = parse_utc_datetime(utc_date)

    if dt is None:
        now = datetime.now()

        return (
            "Próx.",
            now.date(),
            "",
        )

    # Streamlit se ejecutará en el servidor.
    # Mostramos UTC explícitamente para evitar inventar
    # una zona horaria local del usuario.
    dt_utc = dt.astimezone(timezone.utc)

    return (
        dt_utc.strftime("%d/%m"),
        dt_utc.date(),
        dt_utc.strftime("%H:%M UTC"),
    )


# ============================================================
# CARGA DE CUOTAS REALES
# ============================================================

@st.cache_data(ttl=300)
def load_real_odds():
    """
    Carga cuotas desde data/odds.csv si existe.

    Formato recomendado:

    home,away,market,line,odds,bookmaker
    Real Madrid,Real Sociedad,goals,+2.5,1.90,Betfair
    """

    path = Path("data/odds.csv")

    if not path.exists():
        return pd.DataFrame()

    try:
        odds = pd.read_csv(path)

        required = [
            "home",
            "away",
            "market",
            "line",
            "odds",
        ]

        missing = [
            c for c in required
            if c not in odds.columns
        ]

        if missing:
            return pd.DataFrame()

        odds["odds"] = pd.to_numeric(
            odds["odds"],
            errors="coerce"
        )

        odds = odds[
            odds["odds"] > 1
        ].copy()

        return odds

    except Exception:
        return pd.DataFrame()


def find_real_odds(
    odds_df,
    home,
    away,
    market,
    line
):
    """
    Busca una cuota real.

    La comparación utiliza nombres de equipos,
    mercado y línea.
    """

    if odds_df.empty:
        return np.nan, ""

    candidates = odds_df[
        (odds_df["home"].astype(str).str.lower() == str(home).lower()) &
        (odds_df["away"].astype(str).str.lower() == str(away).lower()) &
        (odds_df["market"].astype(str).str.lower() == str(market).lower()) &
        (odds_df["line"].astype(str) == str(line))
    ]

    if candidates.empty:
        return np.nan, ""

    row = candidates.iloc[0]

    bookmaker = (
        str(row["bookmaker"])
        if "bookmaker" in row
        else ""
    )

    return safe_float(row["odds"]), bookmaker


# ============================================================
# API FOOTBALL-DATA.ORG
# ============================================================

@st.cache_data(ttl=3600)
def load_multimarket_data(competition="PD"):

    try:
        api_key = st.secrets[
            "FOOTBALL_DATA_API_KEY"
        ]

    except Exception:
        return (
            pd.DataFrame(),
            "Falta FOOTBALL_DATA_API_KEY en Streamlit Secrets."
        )

    headers = {
        "X-Auth-Token": api_key
    }

    standings_url = (
        f"https://api.football-data.org/v4/"
        f"competitions/{competition}/standings"
    )

    matches_url = (
        f"https://api.football-data.org/v4/"
        f"competitions/{competition}/matches"
        f"?status=SCHEDULED"
    )

    try:

        resp_matches = requests.get(
            matches_url,
            headers=headers,
            timeout=15
        )

        if resp_matches.status_code != 200:

            return (
                pd.DataFrame(),
                f"Error API partidos: "
                f"{resp_matches.status_code}"
            )

        matches_data = resp_matches.json().get(
            "matches",
            []
        )

        # ----------------------------------------------------
        # TABLA
        # ----------------------------------------------------

        team_stats = {}

        resp_standings = requests.get(
            standings_url,
            headers=headers,
            timeout=15
        )

        if resp_standings.status_code == 200:

            standings_data = resp_standings.json().get(
                "standings",
                []
            )

            for standing in standings_data:

                if standing.get("type") != "TOTAL":
                    continue

                for row in standing.get("table", []):

                    team = row["team"]["name"]

                    played = max(
                        1,
                        row.get(
                            "playedGames",
                            1
                        )
                    )

                    goals_for = (
                        row.get("goalsFor", 0)
                        / played
                    )

                    goals_against = (
                        row.get("goalsAgainst", 0)
                        / played
                    )

                    team_stats[team] = {
                        "gf": goals_for,
                        "ga": goals_against,
                        "played": played
                    }

        parsed_data = []

        # ----------------------------------------------------
        # PARTIDOS
        # ----------------------------------------------------

        for match in matches_data:

            home = match[
                "homeTeam"
            ]["name"]

            away = match[
                "awayTeam"
            ]["name"]

            home_crest = match[
                "homeTeam"
            ].get("crest", "")

            away_crest = match[
                "awayTeam"
            ].get("crest", "")

            (
                match_date_str,
                match_date_obj,
                match_time
            ) = local_match_info(
                match.get("utcDate", "")
            )

            h_stat = team_stats.get(
                home,
                {
                    "gf": DEFAULT_LEAGUE_GOALS / 2,
                    "ga": DEFAULT_LEAGUE_GOALS / 2,
                    "played": 0
                }
            )

            a_stat = team_stats.get(
                away,
                {
                    "gf": DEFAULT_LEAGUE_GOALS / 2,
                    "ga": DEFAULT_LEAGUE_GOALS / 2,
                    "played": 0
                }
            )

            # ------------------------------------------------
            # EXPECTED GOALS
            # ------------------------------------------------

            home_expected_goals = (
                h_stat["gf"]
                + a_stat["ga"]
            ) / 2

            away_expected_goals = (
                a_stat["gf"]
                + h_stat["ga"]
            ) / 2

            total_expected_goals = (
                home_expected_goals
                + away_expected_goals
            )

            total_expected_goals = max(
                0.2,
                min(6.0, total_expected_goals)
            )

            prob_goals = poisson_prob_over(
                total_expected_goals,
                2.5
            )

            fair_g = fair_odds(
                prob_goals
            )

            # ------------------------------------------------
            # CÓRNERS
            # ------------------------------------------------

            # IMPORTANTE:
            # Es una estimación provisional porque
            # football-data.org no proporciona aquí
            # suficientes datos históricos de córners.

            exp_corners = (
                DEFAULT_CORNERS
                + (home_expected_goals - 1.3) * 1.0
                + (away_expected_goals - 1.3) * 0.8
            )

            exp_corners = max(
                5.0,
                min(15.0, exp_corners)
            )

            prob_corners = poisson_prob_over(
                exp_corners,
                9.5
            )

            fair_c = fair_odds(
                prob_corners
            )

            # ------------------------------------------------
            # TARJETAS
            # ------------------------------------------------

            exp_cards = DEFAULT_CARDS

            prob_cards = poisson_prob_over(
                exp_cards,
                4.5
            )

            fair_cards = fair_odds(
                prob_cards
            )

            # ------------------------------------------------
            # TIROS A PUERTA
            # ------------------------------------------------

            exp_sot = (
                DEFAULT_SOT
                + (total_expected_goals - 2.6) * 1.5
            )

            exp_sot = max(
                4.0,
                min(15.0, exp_sot)
            )

            prob_sot = poisson_prob_over(
                exp_sot,
                8.5
            )

            fair_sot = fair_odds(
                prob_sot
            )

            # ------------------------------------------------
            # MERCADOS
            # ------------------------------------------------

            markets = [

                (
                    "goals",
                    "⚽ Goles Totales",
                    "+2.5",
                    prob_goals,
                    fair_g
                ),

                (
                    "corners",
                    "📐 Córners Totales",
                    "+9.5",
                    prob_corners,
                    fair_c
                ),

                (
                    "cards",
                    "🟨 Tarjetas Totales",
                    "+4.5",
                    prob_cards,
                    fair_cards
                ),

                (
                    "sot",
                    "🎯 Disparos a Puerta",
                    "+8.5",
                    prob_sot,
                    fair_sot
                )
            ]

            for (
                market_code,
                market_name,
                line,
                probability,
                fair
            ) in markets:

                if probability < MIN_PROBABILITY:
                    continue

                # --------------------------------------------
                # CUOTA REAL
                # --------------------------------------------

                odds_df = load_real_odds()

                odds, bookmaker = find_real_odds(
                    odds_df,
                    home,
                    away,
                    market_code,
                    line
                )

                if pd.isna(odds):

                    ev = np.nan
                    edge = np.nan
                    rating = "📊 SIN CUOTA"

                else:

                    ev = expected_value(
                        probability,
                        odds
                    )

                    edge = edge_probability(
                        probability,
                        odds
                    )

                    rating = classify_value(
                        ev
                    )

                # --------------------------------------------
                # CONFIANZA
                # --------------------------------------------

                total_played = min(
                    h_stat.get("played", 0),
                    a_stat.get("played", 0)
                )

                if total_played >= 15:
                    quality = 1.0
                elif total_played >= 8:
                    quality = 0.85
                elif total_played >= 4:
                    quality = 0.70
                else:
                    quality = 0.55

                confidence = confidence_score(
                    probability,
                    quality
                )

                parsed_data.append([
                    home,
                    away,
                    home_crest,
                    away_crest,
                    match_date_str,
                    match_date_obj,
                    match_time,

                    market_code,
                    market_name,
                    line,

                    probability,
                    odds,
                    fair,

                    ev,
                    edge,

                    bookmaker,
                    rating,
                    confidence,

                    home_expected_goals,
                    away_expected_goals
                ])

        if not parsed_data:

            return (
                pd.DataFrame(),
                "No hay partidos disponibles."
            )

        columns = [
            "home",
            "away",
            "home_crest",
            "away_crest",
            "date",
            "date_obj",
            "time",

            "market_code",
            "market",
            "line",

            "probability",
            "odds",
            "fair_odds",

            "ev",
            "edge",

            "bookmaker",
            "rating",
            "confidence",

            "home_expected_goals",
            "away_expected_goals"
        ]

        return (
            pd.DataFrame(
                parsed_data,
                columns=columns
            ),
            "OK"
        )

    except Exception as e:

        return (
            pd.DataFrame(),
            f"Error: {e}"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("⚽ ValueBet Pro V6.4")

    st.caption(
        "Modelo de probabilidades + cuotas reales + EV. "
        "Las selecciones sin cuota no se consideran apuestas de value."
    )

    competitions = {

        "PD (La Liga)": {
            "code": "PD",
            "emblem": "🇪🇸"
        },

        "PL (Premier League)": {
            "code": "PL",
            "emblem": "🇬🇧"
        },

        "CL (Champions League)": {
            "code": "CL",
            "emblem": "🇪🇺"
        },

        "SA (Serie A)": {
            "code": "SA",
            "emblem": "🇮🇹"
        },

        "BL1 (Bundesliga)": {
            "code": "BL1",
            "emblem": "🇩🇪"
        },

        "FL1 (Ligue 1)": {
            "code": "FL1",
            "emblem": "🇫🇷"
        }
    }

    # ========================================================
    # SIDEBAR
    # ========================================================

    with st.sidebar:

        st.header("⚙️ Configuración")

        liga_seleccionada = st.selectbox(
            "Competición",
            list(competitions.keys()),
            index=0
        )

        codigo_liga = competitions[
            liga_seleccionada
        ]["code"]

        st.divider()

        min_ev = st.slider(
            "EV mínimo (%)",
            -20,
            30,
            2,
            1
        )

        st.divider()

        st.caption(
            "⚠️ Las cuotas deben proceder de "
            "una fuente real. La aplicación ya "
            "no genera cuotas aleatorias."
        )

    # ========================================================
    # DATOS
    # ========================================================

    df, msg = load_multimarket_data(
        codigo_liga
    )

    if df.empty:

        st.warning(
            f"⚠️ {msg}"
        )

        return

    df["probability_pct"] = (
        df["probability"] * 100
    )

    # ========================================================
    # ESTADO DE CUOTAS
    # ========================================================

    with_odds = df[
        df["odds"].notna()
    ]

    value_count = (
        with_odds["ev"] >= min_ev / 100
    ).sum()

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Partidos",
        df[
            ["home", "away"]
        ].drop_duplicates().shape[0]
    )

    c2.metric(
        "Mercados",
        len(df)
    )

    c3.metric(
        "Con cuota real",
        len(with_odds)
    )

    c4.metric(
        "Value encontrado",
        int(value_count)
    )

    st.divider()

    # ========================================================
    # TABS
    # ========================================================

    (
        tab_top,
        tab_matches,
        tab_sim
    ) = st.tabs([
        "🔥 Top Value por Fecha",
        "📅 Partidos y Mercados",
        "💰 Simulador"
    ])

    # ========================================================
    # TAB TOP
    # ========================================================

    with tab_top:

        st.caption(
            f"{competitions[liga_seleccionada]['emblem']} "
            "Mejores oportunidades según el modelo."
        )

        col_date, col_info = st.columns(
            [2, 3]
        )

        with col_date:

            selected_date = st.date_input(
                "Fecha:",
                value=datetime.now().date()
            )

        selected_date_str = (
            selected_date.strftime("%d/%m")
        )

        day_df = df[
            df["date_obj"] == selected_date
        ]

        top_df = day_df[
            day_df["odds"].notna()
        ].copy()

        top_df = top_df[
            top_df["ev"] >= min_ev / 100
        ]

        top_df = top_df.sort_values(
            "ev",
            ascending=False
        )

        if top_df.empty:

            st.info(
                f"ℹ️ No hay cuotas reales con "
                f"EV ≥ {min_ev}% para "
                f"el {selected_date_str}."
            )

            no_odds = day_df[
                day_df["odds"].isna()
            ]

            if not no_odds.empty:

                st.markdown(
                    f"""
                    <div class="warning-box">
                    📊 El modelo tiene
                    <b>{len(no_odds)}</b>
                    predicciones para este día,
                    pero no hay cuotas reales
                    cargadas para compararlas.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        else:

            st.markdown(
                f"**Top value del {selected_date_str}:**"
            )

            for _, r in top_df.head(10).iterrows():

                ev_p = float(r.ev) * 100

                if ev_p >= 8:
                    badge_class = "badge-value"
                elif ev_p >= 3:
                    badge_class = "badge-value"
                else:
                    badge_class = "badge-neutral"

                home_img = (
                    f'<img src="{r.home_crest}" '
                    f'width="20" '
                    f'style="vertical-align:middle;'
                    f'margin-right:6px;">'
                    if r.home_crest
                    else ''
                )

                away_img = (
                    f'<img src="{r.away_crest}" '
                    f'width="20" '
                    f'style="vertical-align:middle;'
                    f'margin-left:6px;'
                    f'margin-right:6px;">'
                    if r.away_crest
                    else ''
                )

                st.markdown(
                    f"""
                    <div class="match-card">

                    <div style="
                    display:flex;
                    justify-content:space-between;
                    align-items:center;
                    font-size:.8rem;
                    opacity:.8;
                    margin-bottom:6px;
                    ">

                    <span>
                    {home_img}
                    {r.home}
                    vs
                    {away_img}
                    {r.away}
                    </span>

                    <span>
                    📅 {r.date}
                    —
                    ⏰ {r.time}
                    </span>

                    </div>

                    <div style="
                    font-weight:700;
                    font-size:1.05rem;
                    margin:4px 0;
                    ">

                    {r.market}
                    ({r.line})

                    </div>

                    <div>

                    Prob:
                    <b>{r.probability_pct:.1f}%</b>

                    &nbsp;|&nbsp;

                    Cuota:
                    <b>{r.odds:.2f}</b>

                    &nbsp;|&nbsp;

                    Justa:
                    <b>{r.fair_odds:.2f}</b>

                    &nbsp;

                    <span class="{badge_class}">
                    EV {ev_p:+.1f}%
                    </span>

                    </div>

                    <div class="stat-line">
                    Edge:
                    {r.edge * 100:+.1f} pp
                    |
                    Confianza:
                    {r.confidence:.0f}/100
                    |
                    {r.bookmaker}
                    </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # ========================================================
    # TAB PARTIDOS
    # ========================================================

    with tab_matches:

        st.caption(
            "📅 Calendario y mercados disponibles."
        )

        partidos = (
            df[
                [
                    "home",
                    "away",
                    "home_crest",
                    "away_crest",
                    "date",
                    "time"
                ]
            ]
            .drop_duplicates()
            .sort_values(
                ["date", "time"]
            )
        )

        for _, match in partidos.iterrows():

            h = match["home"]
            a = match["away"]

            subset = df[
                (df["home"] == h) &
                (df["away"] == a)
            ]

            if subset.empty:
                continue

            h_crest = match["home_crest"]
            a_crest = match["away_crest"]

            h_img = (
                f'<img src="{h_crest}" '
                f'width="22" '
                f'style="vertical-align:middle;'
                f'margin-right:8px;">'
                if h_crest
                else ''
            )

            a_img = (
                f'<img src="{a_crest}" '
                f'width="22" '
                f'style="vertical-align:middle;'
                f'margin-right:8px;">'
                if a_crest
                else ''
            )

            num_mercados = len(subset)

            with st.expander(
                f"📌 {match['date']} "
                f"({match['time']}) | "
                f"{h} vs {a} "
                f"({num_mercados} mercados)"
            ):

                st.markdown(
                    f"""
                    <div style="
                    display:flex;
                    align-items:center;
                    justify-content:space-between;
                    background:rgba(128,128,128,.06);
                    padding:10px 14px;
                    border-radius:10px;
                    margin-bottom:12px;
                    ">

                    <div>
                    {h_img}
                    <b>{h}</b>
                    </div>

                    <div style="
                    font-size:.85rem;
                    opacity:.6;
                    font-weight:bold;
                    ">
                    VS
                    </div>

                    <div>
                    {a_img}
                    <b>{a}</b>
                    </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

                for _, r in subset.iterrows():

                    if pd.isna(r["odds"]):

                        rating_html = (
                            '<span class="badge-neutral">'
                            '📊 SIN CUOTA'
                            '</span>'
                        )

                        odds_html = (
                            "Cuota: <b>—</b> "
                            "(carga una cuota real)"
                        )

                    else:

                        ev_p = r["ev"] * 100

                        if ev_p >= 3:

                            color_ev = "#2ecc71"

                        elif ev_p >= 0:

                            color_ev = "#f1c40f"

                        else:

                            color_ev = "#e74c3c"

                        rating_html = (
                            f'<span style="'
                            f'color:{color_ev};'
                            f'font-weight:700;">'
                            f'EV {ev_p:+.1f}%'
                            f'</span>'
                        )

                        odds_html = (
                            f"Cuota: <b>{r.odds:.2f}</b> "
                            f"(Justa: {r.fair_odds:.2f})"
                        )

                    st.markdown(
                        f"""
                        <div class="market-box">

                        <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        margin-bottom:4px;
                        ">

                        <span style="
                        font-weight:700;
                        font-size:.95rem;
                        ">

                        {r.market}

                        <span style="
                        opacity:.7;
                        font-weight:normal;
                        ">

                        ({r.line})

                        </span>

                        </span>

                        {rating_html}

                        </div>

                        <div style="
                        display:flex;
                        justify-content:space-between;
                        align-items:center;
                        font-size:.85rem;
                        opacity:.85;
                        margin-top:6px;
                        ">

                        <div>
                        Probabilidad:
                        <b>{r.probability_pct:.1f}%</b>
                        </div>

                        <div>
                        {odds_html}
                        </div>

                        </div>

                        <div style="
                        width:100%;
                        background:rgba(128,128,128,.15);
                        height:4px;
                        border-radius:2px;
                        margin-top:6px;
                        ">

                        <div style="
                        width:{min(100,r.probability_pct)}%;
                        background:#3498db;
                        height:4px;
                        border-radius:2px;
                        "></div>

                        </div>

                        <div class="stat-line">
                        Confianza:
                        {r.confidence:.0f}/100
                        </div>

                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    # ========================================================
    # TAB SIMULADOR
    # ========================================================

    with tab_sim:

        st.caption(
            "💰 Cálculo de stake con Kelly fraccionado."
        )

        bank = st.number_input(
            "Bankroll actual (€)",
            min_value=10.0,
            value=500.0,
            step=50.0
        )

        frac = st.slider(
            "Kelly fraccionado",
            0.05,
            0.50,
            0.25,
            0.05
        )

        max_stake_pct = st.slider(
            "Máximo por apuesta (% bankroll)",
            0.25,
            5.0,
            2.0,
            0.25
        )

        eligible = df[
            df["odds"].notna() &
            df["ev"].notna() &
            (df["ev"] > 0)
        ].sort_values(
            "ev",
            ascending=False
        )

        if eligible.empty:

            st.info(
                "No hay apuestas con cuota real "
                "y EV positivo disponibles."
            )

        else:

            s = eligible.iloc[0]

            p = float(
                s["probability"]
            )

            o = float(
                s["odds"]
            )

            max_stake = (
                max_stake_pct / 100
            )

            stake_fraction = fractional_kelly(
                p,
                o,
                fraction=frac,
                max_stake=max_stake
            )

            stake = (
                stake_fraction * bank
            )

            st.success(
                f"""
                Mejor oportunidad:
                **{s['home']} vs {s['away']} —
                {s['market']} {s['line']}**

                Stake orientativo:
                **€{stake:.2f}**
                ({stake_fraction*100:.2f}% del bankroll)
                """
            )

            st.caption(
                "Kelly es extremadamente sensible a "
                "errores en la probabilidad. Úsalo como "
                "referencia, no como garantía."
            )

    # ========================================================
    # FOOTER
    # ========================================================

    st.divider()

    st.caption(
        "ValueBet Football Pro V6.4 — "
        "Probabilidades sin cuotas ficticias."
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
