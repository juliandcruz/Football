import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import requests
import math
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="ValueBet Pro",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# ESTILO PROFESIONAL
# ============================================================

st.markdown("""
<style>

.block-container {
    max-width: 1150px;
    padding: 1rem .8rem 4rem .8rem;
}

/* Header */

.app-header {
    padding: 4px 0 18px 0;
}

.app-title {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: -0.5px;
}

.app-subtitle {
    opacity: .60;
    font-size: .85rem;
}

/* Cards */

.value-card {
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 18px;
    padding: 18px;
    margin-bottom: 14px;
    background: rgba(128,128,128,.035);
}

.match-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 14px;
}

.match-teams {
    font-size: 1rem;
    font-weight: 700;
}

.match-date {
    font-size: .75rem;
    opacity: .55;
}

.market-title {
    font-size: 1.05rem;
    font-weight: 750;
    margin-bottom: 12px;
}

.metric-box {
    border-radius: 12px;
    padding: 10px;
    background: rgba(128,128,128,.06);
    text-align: center;
}

.metric-label {
    font-size: .70rem;
    opacity: .55;
}

.metric-value {
    font-size: 1.05rem;
    font-weight: 750;
}

.ev-positive {
    color: #2ecc71;
}

.ev-negative {
    color: #e74c3c;
}

.value-badge {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 8px;
    font-size: .72rem;
    font-weight: 750;
    background: rgba(46,204,113,.14);
    color: #2ecc71;
}

.neutral-badge {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 8px;
    font-size: .72rem;
    background: rgba(128,128,128,.12);
}

.no-odds-badge {
    display: inline-block;
    padding: 4px 9px;
    border-radius: 8px;
    font-size: .72rem;
    background: rgba(241,196,15,.12);
    color: #f1c40f;
}

.section-title {
    font-size: 1.25rem;
    font-weight: 800;
    margin-top: 8px;
    margin-bottom: 12px;
}

.small-note {
    font-size: .75rem;
    opacity: .55;
}

hr {
    opacity: .15;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# CONSTANTES
# ============================================================

MIN_PROBABILITY = 0.45
DEFAULT_LEAGUE_GOALS = 2.60
DEFAULT_CORNERS = 9.5
DEFAULT_CARDS = 4.5
DEFAULT_SOT = 8.5

MAX_KELLY_STAKE = 0.02


# ============================================================
# FUNCIONES MATEMÁTICAS
# ============================================================

def poisson_pmf(k, lam):

    lam = max(0.01, float(lam))

    return (
        math.exp(-lam)
        * lam ** k
        / math.factorial(k)
    )


def poisson_prob_over(expected_value, line):

    expected_value = max(
        0.01,
        float(expected_value)
    )

    threshold = math.floor(
        float(line)
    ) + 1

    probability_under = sum(
        poisson_pmf(
            k,
            expected_value
        )
        for k in range(threshold)
    )

    probability = 1 - probability_under

    return max(
        .001,
        min(.999, probability)
    )


def fair_odds(probability):

    if probability <= 0:
        return np.nan

    return 1 / probability


def implied_probability(odds):

    if pd.isna(odds) or odds <= 1:
        return np.nan

    return 1 / odds


def expected_value(probability, odds):

    if pd.isna(odds) or odds <= 1:
        return np.nan

    return probability * odds - 1


def edge_probability(probability, odds):

    implied = implied_probability(
        odds
    )

    if pd.isna(implied):
        return np.nan

    return probability - implied


def kelly_fraction(
    probability,
    odds,
    fraction=.25,
    maximum=.02
):

    if pd.isna(odds) or odds <= 1:
        return 0

    p = probability
    q = 1 - p
    b = odds - 1

    raw = (
        (b * p) - q
    ) / b

    if raw <= 0:
        return 0

    return min(
        raw * fraction,
        maximum
    )


# ============================================================
# FECHAS
# ============================================================

def parse_date(value):

    try:

        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

        dt = dt.astimezone(
            timezone.utc
        )

        return (
            dt.strftime("%d/%m"),
            dt.date(),
            dt.strftime("%H:%M")
        )

    except Exception:

        now = datetime.now(
            timezone.utc
        )

        return (
            "Próx.",
            now.date(),
            ""
        )


# ============================================================
# CUOTAS REALES
# ============================================================

@st.cache_data(ttl=300)
def load_real_odds():

    path = Path(
        "data/odds.csv"
    )

    if not path.exists():
        return pd.DataFrame()

    try:

        df = pd.read_csv(path)

        required = [
            "home",
            "away",
            "market",
            "line",
            "odds"
        ]

        if not all(
            col in df.columns
            for col in required
        ):
            return pd.DataFrame()

        df["odds"] = pd.to_numeric(
            df["odds"],
            errors="coerce"
        )

        return df[
            df["odds"] > 1
        ].copy()

    except Exception:

        return pd.DataFrame()


def get_real_odds(
    odds_df,
    home,
    away,
    market,
    line
):

    if odds_df.empty:
        return np.nan, ""

    matches = odds_df[
        (
            odds_df["home"]
            .astype(str)
            .str.lower()
            ==
            str(home).lower()
        )
        &
        (
            odds_df["away"]
            .astype(str)
            .str.lower()
            ==
            str(away).lower()
        )
        &
        (
            odds_df["market"]
            .astype(str)
            .str.lower()
            ==
            str(market).lower()
        )
        &
        (
            odds_df["line"]
            .astype(str)
            ==
            str(line)
        )
    ]

    if matches.empty:
        return np.nan, ""

    row = matches.iloc[0]

    bookmaker = ""

    if "bookmaker" in matches.columns:
        bookmaker = str(
            row["bookmaker"]
        )

    return (
        float(row["odds"]),
        bookmaker
    )


# ============================================================
# API FOOTBALL DATA
# ============================================================

@st.cache_data(ttl=3600)
def load_data(competition):

    try:

        api_key = st.secrets[
            "FOOTBALL_DATA_API_KEY"
        ]

    except Exception:

        return (
            pd.DataFrame(),
            "Falta FOOTBALL_DATA_API_KEY."
        )

    headers = {
        "X-Auth-Token": api_key
    }

    matches_url = (
        "https://api.football-data.org/v4/"
        f"competitions/{competition}/matches"
        "?status=SCHEDULED"
    )

    standings_url = (
        "https://api.football-data.org/v4/"
        f"competitions/{competition}/standings"
    )

    try:

        response = requests.get(
            matches_url,
            headers=headers,
            timeout=15
        )

        if response.status_code != 200:

            return (
                pd.DataFrame(),
                f"Error API: {response.status_code}"
            )

        matches = response.json().get(
            "matches",
            []
        )

        team_stats = {}

        standings_response = requests.get(
            standings_url,
            headers=headers,
            timeout=15
        )

        if standings_response.status_code == 200:

            standings = (
                standings_response
                .json()
                .get(
                    "standings",
                    []
                )
            )

            for table in standings:

                if table.get("type") != "TOTAL":
                    continue

                for row in table.get(
                    "table",
                    []
                ):

                    team = row[
                        "team"
                    ]["name"]

                    games = max(
                        1,
                        row.get(
                            "playedGames",
                            1
                        )
                    )

                    team_stats[
                        team
                    ] = {

                        "gf":
                        row.get(
                            "goalsFor",
                            0
                        ) / games,

                        "ga":
                        row.get(
                            "goalsAgainst",
                            0
                        ) / games,

                        "played":
                        games
                    }

        odds_df = load_real_odds()

        rows = []

        for match in matches:

            home = match[
                "homeTeam"
            ]["name"]

            away = match[
                "awayTeam"
            ]["name"]

            home_crest = match[
                "homeTeam"
            ].get(
                "crest",
                ""
            )

            away_crest = match[
                "awayTeam"
            ].get(
                "crest",
                ""
            )

            (
                date_text,
                date_obj,
                time_text
            ) = parse_date(
                match.get(
                    "utcDate",
                    ""
                )
            )

            h = team_stats.get(
                home,
                {
                    "gf": 1.3,
                    "ga": 1.3,
                    "played": 0
                }
            )

            a = team_stats.get(
                away,
                {
                    "gf": 1.3,
                    "ga": 1.3,
                    "played": 0
                }
            )

            # -----------------------------------------------
            # GOLES
            # -----------------------------------------------

            home_xg = (
                h["gf"] + a["ga"]
            ) / 2

            away_xg = (
                a["gf"] + h["ga"]
            ) / 2

            total_xg = (
                home_xg + away_xg
            )

            total_xg = max(
                .2,
                min(6, total_xg)
            )

            p_goals = poisson_prob_over(
                total_xg,
                2.5
            )

            # -----------------------------------------------
            # CÓRNERS
            # -----------------------------------------------

            expected_corners = (
                DEFAULT_CORNERS
                + (
                    home_xg - 1.3
                ) * 1.0
                + (
                    away_xg - 1.3
                ) * .8
            )

            expected_corners = max(
                5,
                min(
                    15,
                    expected_corners
                )
            )

            p_corners = poisson_prob_over(
                expected_corners,
                9.5
            )

            # -----------------------------------------------
            # TARJETAS
            # -----------------------------------------------

            p_cards = poisson_prob_over(
                DEFAULT_CARDS,
                4.5
            )

            # -----------------------------------------------
            # TIROS A PUERTA
            # -----------------------------------------------

            expected_sot = (
                DEFAULT_SOT
                +
                (
                    total_xg - 2.6
                ) * 1.5
            )

            expected_sot = max(
                4,
                min(
                    15,
                    expected_sot
                )
            )

            p_sot = poisson_prob_over(
                expected_sot,
                8.5
            )

            markets = [

                (
                    "goals",
                    "⚽ Goles",
                    "+2.5",
                    p_goals
                ),

                (
                    "corners",
                    "📐 Córners",
                    "+9.5",
                    p_corners
                ),

                (
                    "cards",
                    "🟨 Tarjetas",
                    "+4.5",
                    p_cards
                ),

                (
                    "sot",
                    "🎯 Tiros a puerta",
                    "+8.5",
                    p_sot
                )
            ]

            for (
                code,
                name,
                line,
                probability
            ) in markets:

                if probability < MIN_PROBABILITY:
                    continue

                odds, bookmaker = (
                    get_real_odds(
                        odds_df,
                        home,
                        away,
                        code,
                        line
                    )
                )

                fair = fair_odds(
                    probability
                )

                ev = expected_value(
                    probability,
                    odds
                )

                edge = edge_probability(
                    probability,
                    odds
                )

                rows.append([

                    home,
                    away,

                    home_crest,
                    away_crest,

                    date_text,
                    date_obj,
                    time_text,

                    code,
                    name,
                    line,

                    probability,
                    fair,

                    odds,
                    ev,
                    edge,

                    bookmaker
                ])

        if not rows:

            return (
                pd.DataFrame(),
                "No hay datos."
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
            "fair_odds",

            "odds",
            "ev",
            "edge",

            "bookmaker"
        ]

        return (
            pd.DataFrame(
                rows,
                columns=columns
            ),
            "OK"
        )

    except Exception as e:

        return (
            pd.DataFrame(),
            str(e)
        )


# ============================================================
# CARD DE VALUE
# ============================================================

def render_value_card(row):

    probability = (
        row["probability"] * 100
    )

    fair = row["fair_odds"]

    odds = row["odds"]

    ev = row["ev"]

    if pd.isna(odds):

        odds_text = "—"
        ev_text = "—"
        badge = (
            '<span class="no-odds-badge">'
            'SIN CUOTA'
            '</span>'
        )

    else:

        odds_text = f"{odds:.2f}"

        ev_text = (
            f"{ev * 100:+.1f}%"
        )

        if ev >= .08:

            badge = (
                '<span class="value-badge">'
                '🔥 VALUE ALTO'
                '</span>'
            )

        elif ev >= .03:

            badge = (
                '<span class="value-badge">'
                '🟢 VALUE'
                '</span>'
            )

        else:

            badge = (
                '<span class="neutral-badge">'
                '⚖️ NEUTRAL'
                '</span>'
            )

    home_img = ""

    away_img = ""

    if row["home_crest"]:

        home_img = (
            f'<img src="{row["home_crest"]}" '
            f'width="22" '
            f'style="vertical-align:middle;'
            f'margin-right:7px;">'
        )

    if row["away_crest"]:

        away_img = (
            f'<img src="{row["away_crest"]}" '
            f'width="22" '
            f'style="vertical-align:middle;'
            f'margin-right:7px;">'
        )

    bookmaker = row["bookmaker"]

    if bookmaker:

        bookmaker_html = (
            f'<div class="small-note">'
            f'Cuota: {bookmaker}'
            f'</div>'
        )

    else:

        bookmaker_html = ""

    st.markdown(
        f"""
        <div class="value-card">

            <div class="match-header">

                <div class="match-teams">

                    {home_img}
                    {row["home"]}

                    <span style="
                    opacity:.45;
                    padding:0 6px;
                    ">
                    vs
                    </span>

                    {away_img}
                    {row["away"]}

                </div>

                <div class="match-date">

                    {row["date"]}
                    ·
                    {row["time"]}

                </div>

            </div>

            <div class="market-title">

                {row["market"]}
                <span style="opacity:.55;">
                {row["line"]}
                </span>

                &nbsp;&nbsp;

                {badge}

            </div>

            <div style="
            display:grid;
            grid-template-columns:
            repeat(4,1fr);
            gap:8px;
            ">

                <div class="metric-box">

                    <div class="metric-label">
                    PROBABILIDAD
                    </div>

                    <div class="metric-value">
                    {probability:.1f}%
                    </div>

                </div>

                <div class="metric-box">

                    <div class="metric-label">
                    CUOTA
                    </div>

                    <div class="metric-value">
                    {odds_text}
                    </div>

                </div>

                <div class="metric-box">

                    <div class="metric-label">
                    CUOTA JUSTA
                    </div>

                    <div class="metric-value">
                    {fair:.2f}
                    </div>

                </div>

                <div class="metric-box">

                    <div class="metric-label">
                    EV
                    </div>

                    <div class="metric-value ev-positive">
                    {ev_text}
                    </div>

                </div>

            </div>

            {bookmaker_html}

        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# APP
# ============================================================

def main():

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    st.title("⚽ ValueBet Pro")
st.caption("Análisis de mercados de fútbol")

    # --------------------------------------------------------
    # CONFIG
    # --------------------------------------------------------

    competitions = {

        "🇪🇸 La Liga": "PD",

        "🇬🇧 Premier League": "PL",

        "🇪🇺 Champions League": "CL",

        "🇮🇹 Serie A": "SA",

        "🇩🇪 Bundesliga": "BL1",

        "🇫🇷 Ligue 1": "FL1"
    }

    col1, col2 = st.columns(
        [5, 1]
    )

    with col1:

        league_name = st.selectbox(
            "Competición",
            list(
                competitions.keys()
            ),
            label_visibility="collapsed"
        )

    with col2:

        refresh = st.button(
            "🔄 Actualizar",
            use_container_width=True
        )

    if refresh:

        st.cache_data.clear()

        st.rerun()

    competition = competitions[
        league_name
    ]

    # --------------------------------------------------------
    # DATOS
    # --------------------------------------------------------

    df, message = load_data(
        competition
    )

    if df.empty:

        st.error(
            f"⚠️ {message}"
        )

        return

    df["probability_pct"] = (
        df["probability"] * 100
    )

    # --------------------------------------------------------
    # TABS
    # --------------------------------------------------------

    (
        tab_top,
        tab_matches,
        tab_bank
    ) = st.tabs(
        [
            "🔥 Top Value",
            "📅 Partidos",
            "💰 Stake"
        ]
    )

    # ========================================================
    # TOP VALUE
    # ========================================================

    with tab_top:

        st.markdown(
            '<div class="section-title">'
            '🔥 Mejores oportunidades'
            '</div>',
            unsafe_allow_html=True
        )

        selected_date = st.date_input(
            "Fecha",
            value=datetime.now().date(),
            label_visibility="collapsed"
        )

        day = df[
            df["date_obj"] == selected_date
        ].copy()

        # Solo apuestas con cuota real
        value = day[
            day["odds"].notna()
        ].copy()

        value = value.sort_values(
            "ev",
            ascending=False
        )

        if value.empty:

            st.info(
                "No hay cuotas reales cargadas "
                "para esta fecha."
            )

        else:

            for _, row in value.head(
                15
            ).iterrows():

                render_value_card(
                    row
                )

    # ========================================================
    # PARTIDOS
    # ========================================================

    with tab_matches:

        st.markdown(
            '<div class="section-title">'
            '📅 Partidos'
            '</div>',
            unsafe_allow_html=True
        )

        matches = (
            df[
                [
                    "home",
                    "away",
                    "date",
                    "time"
                ]
            ]
            .drop_duplicates()
            .sort_values(
                [
                    "date",
                    "time"
                ]
            )
        )

        for _, match in matches.iterrows():

            home = match["home"]
            away = match["away"]

            subset = df[
                (df["home"] == home)
                &
                (df["away"] == away)
            ]

            with st.expander(
                f"{match['date']} "
                f"· {match['time']} "
                f"  {home} vs {away}"
            ):

                for _, row in subset.iterrows():

                    render_value_card(
                        row
                    )

    # ========================================================
    # STAKE
    # ========================================================

    with tab_bank:

        st.markdown(
            '<div class="section-title">'
            '💰 Calculadora de stake'
            '</div>',
            unsafe_allow_html=True
        )

        bank = st.number_input(
            "Bankroll (€)",
            min_value=10.0,
            value=500.0,
            step=50.0
        )

        kelly = st.slider(
            "Kelly fraccionado",
            .05,
            .50,
            .25,
            .05
        )

        max_pct = st.slider(
            "Máximo por apuesta (%)",
            .25,
            5.0,
            2.0,
            .25
        )

        eligible = df[
            df["odds"].notna()
            &
            df["ev"].notna()
            &
            (df["ev"] > 0)
        ].sort_values(
            "ev",
            ascending=False
        )

        if eligible.empty:

            st.info(
                "No hay apuestas con EV positivo."
            )

        else:

            best = eligible.iloc[0]

            stake_pct = kelly_fraction(
                best["probability"],
                best["odds"],
                fraction=kelly,
                maximum=max_pct / 100
            )

            stake = (
                bank * stake_pct
            )

            st.success(
                f"""
                **{best["home"]} vs
                {best["away"]}**

                {best["market"]}
                {best["line"]}

                Probabilidad:
                **{best["probability"]*100:.1f}%**

                Cuota:
                **{best["odds"]:.2f}**

                EV:
                **{best["ev"]*100:+.1f}%**

                Stake orientativo:
                **€{stake:.2f}**
                """
            )

            st.caption(
                "El stake es una referencia matemática. "
                "Un modelo puede equivocarse y el EV "
                "estimado no garantiza beneficio."
            )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    st.divider()

    st.caption(
        "ValueBet Football Pro V6.5"
    )


if __name__ == "__main__":
    main()
