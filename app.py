import streamlit as st
import pandas as pd
import requests
import math
import re
from datetime import datetime
from collections import defaultdict


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="ValueBet Pro V7",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# ESTILO
# ============================================================

st.markdown("""
<style>

.block-container {
    max-width: 1180px;
    padding: 1rem .65rem 4rem .65rem;
}

.app-title {
    font-size: 1.75rem;
    font-weight: 850;
    margin-bottom: 2px;
}

.app-subtitle {
    font-size: .82rem;
    opacity: .55;
    margin-bottom: 18px;
}

.round-header {
    border: 1px solid rgba(128,128,128,.18);
    background: rgba(128,128,128,.045);
    border-radius: 16px;
    padding: 13px 15px;
    margin-top: 16px;
    margin-bottom: 10px;
}

.round-title {
    font-size: 1.08rem;
    font-weight: 800;
}

.round-info {
    font-size: .74rem;
    opacity: .55;
    margin-top: 3px;
}

.match-card {
    border: 1px solid rgba(128,128,128,.15);
    border-radius: 15px;
    padding: 13px;
    margin-bottom: 9px;
    background: rgba(128,128,128,.025);
}

.match-time {
    font-size: .76rem;
    opacity: .55;
    margin-bottom: 9px;
}

.team {
    font-size: .95rem;
    font-weight: 750;
}

.vs {
    opacity: .35;
    font-size: .75rem;
    font-weight: 800;
}

.status {
    font-size: .68rem;
    opacity: .55;
}

.market-card {
    border: 1px solid rgba(128,128,128,.13);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 8px;
}

.value-badge {
    background: rgba(46,204,113,.14);
    color: #2ecc71;
    border-radius: 7px;
    padding: 4px 8px;
    font-size: .7rem;
    font-weight: 800;
}

.no-value-badge {
    background: rgba(128,128,128,.12);
    border-radius: 7px;
    padding: 4px 8px;
    font-size: .7rem;
    font-weight: 700;
}

.no-data {
    padding: 10px;
    border-radius: 10px;
    background: rgba(128,128,128,.06);
    font-size: .8rem;
    opacity: .7;
}

.metric {
    background: rgba(128,128,128,.06);
    border-radius: 10px;
    padding: 8px;
    text-align: center;
}

.metric-label {
    font-size: .62rem;
    opacity: .5;
}

.metric-value {
    font-size: .95rem;
    font-weight: 800;
}

.source {
    font-size: .68rem;
    opacity: .45;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# COMPETICIONES
# ============================================================

COMPETITIONS = {
    "🇪🇸 La Liga": {
        "api_football": 140,
        "football_data": "PD",
    },
    "🇬🇧 Premier League": {
        "api_football": 39,
        "football_data": "PL",
    },
    "🇮🇹 Serie A": {
        "api_football": 135,
        "football_data": "SA",
    },
    "🇩🇪 Bundesliga": {
        "api_football": 78,
        "football_data": "BL1",
    },
    "🇫🇷 Ligue 1": {
        "api_football": 61,
        "football_data": "FL1",
    },
    "🇪🇺 Champions League": {
        "api_football": 2,
        "football_data": "CL",
    },
}


# ============================================================
# SECRETS
# ============================================================

def get_secret(name):

    try:
        value = st.secrets.get(name)

        if value:
            return str(value).strip()

    except Exception:
        pass

    return None


# ============================================================
# API-FOOTBALL
# ============================================================

API_FOOTBALL_BASE = (
    "https://v3.football.api-sports.io"
)


def api_football_get(
    endpoint,
    params=None
):

    key = get_secret(
        "API_FOOTBALL_KEY"
    )

    if not key:

        return None, (
            "No existe API_FOOTBALL_KEY "
            "en Streamlit Secrets."
        )

    headers = {
        "x-apisports-key": key
    }

    try:

        response = requests.get(
            API_FOOTBALL_BASE + endpoint,
            headers=headers,
            params=params or {},
            timeout=20,
        )

        if response.status_code != 200:

            return None, (
                f"API-Football HTTP "
                f"{response.status_code}"
            )

        data = response.json()

        errors = data.get(
            "errors"
        )

        if errors:

            return None, str(errors)

        return data, None

    except Exception as e:

        return None, str(e)


# ============================================================
# FOOTBALL-DATA.ORG
# ============================================================

FOOTBALL_DATA_BASE = (
    "https://api.football-data.org/v4"
)


def football_data_get(
    endpoint,
    params=None
):

    key = get_secret(
        "FOOTBALL_DATA_API_KEY"
    )

    if not key:

        return None, (
            "No existe "
            "FOOTBALL_DATA_API_KEY "
            "en Streamlit Secrets."
        )

    headers = {
        "X-Auth-Token": key
    }

    try:

        response = requests.get(
            FOOTBALL_DATA_BASE + endpoint,
            headers=headers,
            params=params or {},
            timeout=20,
        )

        if response.status_code != 200:

            return None, (
                f"football-data.org HTTP "
                f"{response.status_code}"
            )

        return response.json(), None

    except Exception as e:

        return None, str(e)


# ============================================================
# FECHAS
# ============================================================

def parse_datetime(value):

    if not value:
        return None

    try:

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

    except Exception:

        return None


def format_date(value):

    dt = parse_datetime(value)

    if not dt:
        return "Sin fecha"

    return dt.strftime(
        "%d/%m/%Y"
    )


def format_time(value):

    dt = parse_datetime(value)

    if not dt:
        return "—"

    return dt.strftime(
        "%H:%M"
    )


# ============================================================
# PRÓXIMOS PARTIDOS API-FOOTBALL
#
# IMPORTANTE:
# NO utilizamos /fixtures/rounds
# NO enviamos season=2026
# ============================================================

@st.cache_data(ttl=600)
def get_upcoming_fixtures(
    league_id,
    number=100
):

    data, error = api_football_get(
        "/fixtures",
        {
            "league": league_id,
            "next": number,
        }
    )

    if error:
        return [], error

    fixtures = data.get(
        "response",
        []
    )

    return fixtures, None


# ============================================================
# NORMALIZAR PARTIDOS API-FOOTBALL
# ============================================================

def normalize_api_fixture(
    fixture
):

    fixture_info = fixture.get(
        "fixture",
        {}
    )

    teams = fixture.get(
        "teams",
        {}
    )

    home = teams.get(
        "home",
        {}
    )

    away = teams.get(
        "away",
        {}
    )

    league = fixture.get(
        "league",
        {}
    )

    status = fixture_info.get(
        "status",
        {}
    )

    return {

        "fixture_id":
        fixture_info.get(
            "id"
        ),

        "date_raw":
        fixture_info.get(
            "date"
        ),

        "date":
        format_date(
            fixture_info.get(
                "date"
            )
        ),

        "time":
        format_time(
            fixture_info.get(
                "date"
            )
        ),

        "home":
        home.get(
            "name",
            "Sin datos"
        ),

        "away":
        away.get(
            "name",
            "Sin datos"
        ),

        "home_logo":
        home.get(
            "logo",
            ""
        ),

        "away_logo":
        away.get(
            "logo",
            ""
        ),

        "round":
        league.get(
            "round"
        ),

        "season":
        league.get(
            "season"
        ),

        "status":
        status.get(
            "short",
            ""
        ),

        "venue":
        fixture_info.get(
            "venue",
            {}
        ).get(
            "name"
        ),

        "source":
        "API-Football",

    }


# ============================================================
# AGRUPAR POR JORNADA
# ============================================================

def round_number(
    value
):

    if not value:
        return 9999

    match = re.search(
        r"(\d+)",
        str(value)
    )

    if match:

        return int(
            match.group(1)
        )

    return 9999


def group_by_round(
    fixtures
):

    groups = defaultdict(
        list
    )

    for fixture in fixtures:

        normalized = (
            normalize_api_fixture(
                fixture
            )
        )

        round_name = (
            normalized["round"]
        )

        if not round_name:

            round_name = (
                "Jornada no indicada por la API"
            )

        groups[
            round_name
        ].append(
            normalized
        )

    return dict(
        sorted(
            groups.items(),
            key=lambda item:
            round_number(
                item[0]
            )
        )
    )


# ============================================================
# FOOTBALL-DATA:
# CALENDARIO COMPLEMENTARIO
# ============================================================

@st.cache_data(ttl=900)
def get_football_data_matches(
    competition_code
):

    data, error = football_data_get(
        f"/competitions/"
        f"{competition_code}/matches",
        {
            "status": "SCHEDULED",
        }
    )

    if error:
        return pd.DataFrame(), error

    rows = []

    for match in data.get(
        "matches",
        []
    ):

        rows.append({

            "football_data_id":
            match.get(
                "id"
            ),

            "date_raw":
            match.get(
                "utcDate"
            ),

            "date":
            format_date(
                match.get(
                    "utcDate"
                )
            ),

            "time":
            format_time(
                match.get(
                    "utcDate"
                )
            ),

            "home":
            match.get(
                "homeTeam",
                {}
            ).get(
                "name"
            ),

            "away":
            match.get(
                "awayTeam",
                {}
            ).get(
                "name"
            ),

            "matchday":
            match.get(
                "matchday"
            ),

            "status":
            match.get(
                "status"
            ),

        })

    return pd.DataFrame(
        rows
    ), None


# ============================================================
# CLASIFICACIÓN FOOTBALL-DATA
# ============================================================

@st.cache_data(ttl=1800)
def get_standings(
    competition_code
):

    data, error = football_data_get(
        f"/competitions/"
        f"{competition_code}/standings"
    )

    if error:
        return pd.DataFrame(), error

    rows = []

    for table in data.get(
        "standings",
        []
    ):

        if table.get(
            "type"
        ) != "TOTAL":
            continue

        for row in table.get(
            "table",
            []
        ):

            team = row.get(
                "team",
                {}
            )

            rows.append({

                "Pos":
                row.get(
                    "position"
                ),

                "Equipo":
                team.get(
                    "name"
                ),

                "PJ":
                row.get(
                    "playedGames"
                ),

                "G":
                row.get(
                    "won"
                ),

                "E":
                row.get(
                    "draw"
                ),

                "P":
                row.get(
                    "lost"
                ),

                "GF":
                row.get(
                    "goalsFor"
                ),

                "GC":
                row.get(
                    "goalsAgainst"
                ),

                "Pts":
                row.get(
                    "points"
                ),

            })

    return pd.DataFrame(
        rows
    ), None


# ============================================================
# API-FOOTBALL: PREDICCIONES OFICIALES DEL ENDPOINT
# ============================================================

@st.cache_data(ttl=600)
def get_api_predictions(
    fixture_id
):

    data, error = api_football_get(
        "/predictions",
        {
            "fixture": fixture_id
        }
    )

    if error:
        return None, error

    response = data.get(
        "response",
        []
    )

    if not response:
        return None, None

    return response[0], None


# ============================================================
# API-FOOTBALL: CUOTAS
# ============================================================

@st.cache_data(ttl=300)
def get_fixture_odds(
    fixture_id
):

    data, error = api_football_get(
        "/odds",
        {
            "fixture": fixture_id
        }
    )

    if error:
        return [], error

    return (
        data.get(
            "response",
            []
        ),
        None
    )


# ============================================================
# PROBABILIDAD / EV
# ============================================================

def fair_odds(
    probability
):

    if (
        probability is None
        or probability <= 0
    ):
        return None

    return 1 / probability


def calculate_ev(
    probability,
    odds
):

    if (
        probability is None
        or odds is None
        or odds <= 1
    ):
        return None

    return (
        probability * odds
    ) - 1


# ============================================================
# PARSEAR PREDICCIÓN API-FOOTBALL
# ============================================================

def extract_prediction_data(
    prediction
):

    if not prediction:

        return []

    predictions = (
        prediction.get(
            "predictions",
            {}
        )
    )

    rows = []

    # Resultado 1X2

    winner = predictions.get(
        "winner"
    )

    if winner:

        name = winner.get(
            "name"
        )

        comment = winner.get(
            "comment"
        )

        if name:

            rows.append({

                "market":
                "🏆 Resultado",

                "selection":
                name,

                "value":
                comment,

            })

    # Marcador previsto

    score = predictions.get(
        "score",
        {}
    )

    if score:

        home = score.get(
            "home"
        )

        away = score.get(
            "away"
        )

        if (
            home is not None
            and away is not None
        ):

            rows.append({

                "market":
                "⚽ Marcador previsto",

                "selection":
                f"{home}-{away}",

                "value":
                None,

            })

    # Under / Over

    under_over = predictions.get(
        "under_over"
    )

    if under_over:

        rows.append({

            "market":
            "⚽ Goles",

            "selection":
            str(
                under_over
            ),

            "value":
            None,

        })

    # Goals Home / Away

    goals_home = predictions.get(
        "goals",
        {}
    ).get(
        "home"
    )

    goals_away = predictions.get(
        "goals",
        {}
    ).get(
        "away"
    )

    if goals_home:

        rows.append({

            "market":
            "⚽ Goles local",

            "selection":
            str(
                goals_home
            ),

            "value":
            None,

        })

    if goals_away:

        rows.append({

            "market":
            "⚽ Goles visitante",

            "selection":
            str(
                goals_away
            ),

            "value":
            None,

        })

    # Advice

    advice = predictions.get(
        "advice"
    )

    if advice:

        rows.append({

            "market":
            "🧠 Análisis API",

            "selection":
            str(
                advice
            ),

            "value":
            None,

        })

    return rows


# ============================================================
# RENDER PARTIDO
# ============================================================

def render_match_card(
    match,
    index
):

    home_logo = ""

    away_logo = ""

    if match.get(
        "home_logo"
    ):

        home_logo = (
            f'<img src="{match["home_logo"]}" '
            f'width="22" '
            f'style="vertical-align:middle;'
            f'margin-right:6px;">'
        )

    if match.get(
        "away_logo"
    ):

        away_logo = (
            f'<img src="{match["away_logo"]}" '
            f'width="22" '
            f'style="vertical-align:middle;'
            f'margin-right:6px;">'
        )

    status = match.get(
        "status",
        ""
    )

    st.markdown(
        f"""
        <div class="match-card">

            <div class="match-time">
                📅 {match["date"]}
                &nbsp;&nbsp;
                ⏰ {match["time"]}
                &nbsp;&nbsp;
                <span class="status">
                    {status}
                </span>
            </div>

            <div style="
                display:grid;
                grid-template-columns:
                1fr auto 1fr;
                align-items:center;
                gap:8px;
            ">

                <div class="team">
                    {home_logo}
                    {match["home"]}
                </div>

                <div class="vs">
                    VS
                </div>

                <div class="team"
                     style="text-align:right;">
                    {away_logo}
                    {match["away"]}
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    return st.button(
        "🔮 Ver pronóstico y cuotas",
        key=f"prediction_{index}_{match['fixture_id']}",
        use_container_width=True
    )


# ============================================================
# RENDER PREDICCIONES
# ============================================================

def render_prediction_panel(
    match
):

    fixture_id = match[
        "fixture_id"
    ]

    st.markdown(
        f"""
        ### 🔮 {match["home"]}
        vs {match["away"]}

        **📅 {match["date"]} · ⏰ {match["time"]}**
        """
    )

    # --------------------------------------------------------
    # PREDICCIÓN API
    # --------------------------------------------------------

    prediction, error = (
        get_api_predictions(
            fixture_id
        )
    )

    if error:

        st.warning(
            f"No se pudo obtener la "
            f"predicción: {error}"
        )

    else:

        prediction_rows = (
            extract_prediction_data(
                prediction
            )
        )

        if prediction_rows:

            st.markdown(
                "#### 🧠 Pronóstico API-Football"
            )

            for row in prediction_rows:

                st.markdown(
                    f"""
                    <div class="market-card">

                        <b>{row["market"]}</b><br>

                        {row["selection"]}

                    </div>
                    """,
                    unsafe_allow_html=True
                )

        else:

            st.markdown(
                '<div class="no-data">'
                'API-Football no ha devuelto '
                'un pronóstico para este partido.'
                '</div>',
                unsafe_allow_html=True
            )

    # --------------------------------------------------------
    # CUOTAS
    # --------------------------------------------------------

    st.markdown(
        "#### 💰 Cuotas reales"
    )

    odds, odds_error = (
        get_fixture_odds(
            fixture_id
        )
    )

    if odds_error:

        st.warning(
            f"No se pudieron obtener "
            f"las cuotas: {odds_error}"
        )

    else:

        bookmaker_count = 0

        for bookmaker_block in odds:

            bookmakers = (
                bookmaker_block.get(
                    "bookmakers",
                    []
                )
            )

            for bookmaker in bookmakers:

                bookmaker_count += 1

                bookmaker_name = (
                    bookmaker.get(
                        "name",
                        "Bookmaker"
                    )
                )

                st.markdown(
                    f"**{bookmaker_name}**"
                )

                for bet in bookmaker.get(
                    "bets",
                    []
                ):

                    market_name = (
                        bet.get(
                            "name",
                            ""
                        )
                    )

                    values = (
                        bet.get(
                            "values",
                            []
                        )
                    )

                    # Solo mostramos mercados
                    # relevantes para nuestra app.

                    relevant = any(
                        word in market_name.lower()
                        for word in [
                            "goals",
                            "corner",
                            "cards",
                            "shots",
                            "result"
                        ]
                    )

                    if not relevant:
                        continue

                    for value in values:

                        odd = value.get(
                            "odd"
                        )

                        if odd is None:
                            continue

                        st.write(
                            f"• {market_name}: "
                            f"{value.get('value')} "
                            f"→ **{odd}**"
                        )

        if bookmaker_count == 0:

            st.markdown(
                '<div class="no-data">'
                'No hay cuotas reales '
                'disponibles para este partido.'
                '</div>',
                unsafe_allow_html=True
            )

        st.caption(
            "Las cuotas mostradas son las "
            "devueltas por API-Football. "
            "No se generan cuotas artificiales."
        )


# ============================================================
# MAIN
# ============================================================

def main():

    st.markdown(
        '<div class="app-title">'
        '⚽ ValueBet Pro V7'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="app-subtitle">'
        'Pronósticos · Partidos · Cuotas reales · Datos'
        '</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # SIDEBAR
    # --------------------------------------------------------

    with st.sidebar:

        st.header(
            "⚙️ Configuración"
        )

        competition_name = st.selectbox(
            "Competición",
            list(
                COMPETITIONS.keys()
            )
        )

        number_fixtures = st.slider(
            "Próximos partidos",
            10,
            100,
            50,
            10
        )

        st.divider()

        st.caption(
            "API-Football se utiliza para "
            "partidos, jornadas, pronósticos "
            "y cuotas."
        )

        st.caption(
            "football-data.org se utiliza "
            "como fuente complementaria "
            "de calendario y clasificación."
        )

    competition = COMPETITIONS[
        competition_name
    ]

    api_league = competition[
        "api_football"
    ]

    football_data_code = (
        competition[
            "football_data"
        ]
    )

    # --------------------------------------------------------
    # API-FOOTBALL
    # --------------------------------------------------------

    fixtures, api_error = (
        get_upcoming_fixtures(
            api_league,
            number_fixtures
        )
    )

    if api_error:

        st.error(
            "Error obteniendo próximos "
            "partidos de API-Football:"
        )

        st.code(
            api_error
        )

        st.info(
            "No estamos solicitando "
            "/fixtures/rounds ni "
            "season=2026. La app consulta "
            "directamente los próximos "
            "partidos."
        )

        return

    # --------------------------------------------------------
    # FOOTBALL-DATA
    # --------------------------------------------------------

    fd_matches, fd_error = (
        get_football_data_matches(
            football_data_code
        )
    )

    # --------------------------------------------------------
    # TABS
    # --------------------------------------------------------

    tab_predictions, tab_matches, tab_table = (
        st.tabs(
            [
                "🔮 Pronósticos",
                "📅 Partidos",
                "🏆 Clasificación",
            ]
        )
    )

    # ========================================================
    # PARTIDOS
    # ========================================================

    with tab_matches:

        st.markdown(
            "### 📅 Partidos por jornadas"
        )

        st.caption(
            "La jornada procede del campo "
            "`league.round` de API-Football. "
            "No se calcula ni se inventa."
        )

        if not fixtures:

            st.info(
                "API-Football no ha devuelto "
                "próximos partidos."
            )

        else:

            grouped = group_by_round(
                fixtures
            )

            st.success(
                f"{len(fixtures)} partidos "
                f"recibidos de API-Football"
            )

            for round_name, matches in (
                grouped.items()
            ):

                dates = sorted(
                    set(
                        m["date"]
                        for m in matches
                    )
                )

                date_text = (
                    " · ".join(dates)
                )

                st.markdown(
                    f"""
                    <div class="round-header">

                        <div class="round-title">
                            📋 {round_name}
                        </div>

                        <div class="round-info">
                            {date_text}
                            · {len(matches)}
                            partidos
                        </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

                for i, match in enumerate(
                    matches
                ):

                    render_match_card(
                        match,
                        f"{round_name}_{i}"
                    )

    # ========================================================
    # PRONÓSTICOS
    # ========================================================

    with tab_predictions:

        st.markdown(
            "### 🔮 Pronósticos"
        )

        st.caption(
            "Selecciona un partido para "
            "consultar el pronóstico y las "
            "cuotas disponibles."
        )

        if not fixtures:

            st.info(
                "No hay partidos disponibles."
            )

        else:

            grouped = group_by_round(
                fixtures
            )

            for round_name, matches in (
                grouped.items()
            ):

                st.markdown(
                    f"#### {round_name}"
                )

                for i, match in enumerate(
                    matches
                ):

                    with st.container(
                        border=True
                    ):

                        c1, c2, c3 = st.columns(
                            [1, 5, 2]
                        )

                        with c1:

                            st.markdown(
                                f"**{match['time']}**"
                            )

                            st.caption(
                                match["date"]
                            )

                        with c2:

                            st.markdown(
                                f"**{match['home']}**"
                            )

                            st.markdown(
                                f"vs "
                                f"**{match['away']}**"
                            )

                        with c3:

                            if st.button(
                                "Ver",
                                key=(
                                    "pred_"
                                    f"{round_name}_"
                                    f"{i}_"
                                    f"{match['fixture_id']}"
                                ),
                                use_container_width=True
                            ):

                                st.session_state[
                                    "selected_fixture"
                                ] = match[
                                    "fixture_id"
                                ]

                                st.session_state[
                                    "selected_match"
                                ] = match

                    selected = (
                        st.session_state.get(
                            "selected_fixture"
                        )
                    )

                    if (
                        selected
                        ==
                        match["fixture_id"]
                    ):

                        render_prediction_panel(
                            match
                        )

    # ========================================================
    # CLASIFICACIÓN
    # ========================================================

    with tab_table:

        st.markdown(
            "### 🏆 Clasificación"
        )

        standings, standings_error = (
            get_standings(
                football_data_code
            )
        )

        if standings_error:

            st.error(
                standings_error
            )

        elif standings.empty:

            st.info(
                "No hay clasificación "
                "disponible."
            )

        else:

            st.dataframe(
                standings,
                hide_index=True,
                use_container_width=True
            )

            st.caption(
                "Fuente: football-data.org"
            )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    with st.expander(
        "🔧 Estado de las APIs"
    ):

        st.write(
            "API-Football:"
        )

        if api_error:

            st.error(
                api_error
            )

        else:

            st.success(
                "Conectada"
            )

        st.write(
            "football-data.org:"
        )

        if fd_error:

            st.warning(
                fd_error
            )

        else:

            st.success(
                "Conectada"
            )

        st.write(
            f"Partidos API-Football: "
            f"{len(fixtures)}"
        )

        st.write(
            f"Partidos football-data.org: "
            f"{len(fd_matches)}"
        )

    st.divider()

    st.caption(
        "ValueBet Football Pro V7.1 · "
        "Sin cuotas ni estadísticas inventadas"
    )


# ============================================================
# EJECUCIÓN
# ============================================================

if __name__ == "__main__":
    main()
