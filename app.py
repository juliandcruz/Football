import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date, timedelta
from collections import defaultdict


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="ValueBet Pro V7.3",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# ESTILOS
# ============================================================

st.markdown("""
<style>

.block-container {
    max-width: 1200px;
    padding: 1rem .65rem 4rem .65rem;
}

.app-title {
    font-size: 1.8rem;
    font-weight: 850;
    letter-spacing: -.5px;
}

.app-subtitle {
    font-size: .82rem;
    opacity: .55;
    margin-bottom: 18px;
}

.section-title {
    font-size: 1.25rem;
    font-weight: 800;
    margin-top: 8px;
    margin-bottom: 10px;
}

.round-card {
    border: 1px solid rgba(128,128,128,.18);
    border-radius: 16px;
    padding: 13px 15px;
    margin-top: 18px;
    margin-bottom: 10px;
    background: rgba(128,128,128,.045);
}

.round-title {
    font-size: 1.05rem;
    font-weight: 800;
}

.round-subtitle {
    font-size: .73rem;
    opacity: .55;
    margin-top: 3px;
}

.match-card {
    border: 1px solid rgba(128,128,128,.15);
    border-radius: 14px;
    padding: 13px;
    margin-bottom: 9px;
    background: rgba(128,128,128,.025);
}

.match-date {
    font-size: .74rem;
    opacity: .55;
    margin-bottom: 9px;
}

.team-name {
    font-size: .95rem;
    font-weight: 750;
}

.vs {
    font-size: .7rem;
    opacity: .35;
    font-weight: 800;
    text-align: center;
}

.info-card {
    border: 1px solid rgba(128,128,128,.14);
    border-radius: 14px;
    padding: 14px;
    margin-bottom: 10px;
    background: rgba(128,128,128,.035);
}

.market-card {
    border: 1px solid rgba(128,128,128,.13);
    border-radius: 11px;
    padding: 11px;
    margin-bottom: 7px;
}

.no-data {
    padding: 11px;
    border-radius: 10px;
    background: rgba(128,128,128,.06);
    font-size: .8rem;
    opacity: .7;
}

.metric {
    background: rgba(128,128,128,.055);
    border-radius: 10px;
    padding: 9px;
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

.status-ok {
    color: #2ecc71;
    font-weight: 700;
}

.status-warning {
    color: #f39c12;
    font-weight: 700;
}

.api-box {
    border: 1px solid rgba(128,128,128,.15);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 10px;
    background: rgba(128,128,128,.035);
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# COMPETICIONES
# ============================================================

COMPETITIONS = {

    "🇪🇸 La Liga": {
        "api_id": 140,
        "football_data": "PD",
    },

    "🇬🇧 Premier League": {
        "api_id": 39,
        "football_data": "PL",
    },

    "🇮🇹 Serie A": {
        "api_id": 135,
        "football_data": "SA",
    },

    "🇩🇪 Bundesliga": {
        "api_id": 78,
        "football_data": "BL1",
    },

    "🇫🇷 Ligue 1": {
        "api_id": 61,
        "football_data": "FL1",
    },

    "🇪🇺 Champions League": {
        "api_id": 2,
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

API_FOOTBALL_URL = (
    "https://v3.football.api-sports.io"
)


def api_football(
    endpoint,
    params=None
):

    api_key = get_secret(
        "API_FOOTBALL_KEY"
    )

    if not api_key:

        return None, (
            "Falta API_FOOTBALL_KEY "
            "en Streamlit Secrets."
        ), {}

    headers = {
        "x-apisports-key": api_key,
        "Accept": "application/json",
    }

    try:

        response = requests.get(
            API_FOOTBALL_URL + endpoint,
            headers=headers,
            params=params or {},
            timeout=20,
        )

        try:
            data = response.json()
        except Exception:

            return None, (
                f"Respuesta no válida "
                f"HTTP {response.status_code}"
            ), dict(response.headers)

        errors = data.get("errors")

        if response.status_code != 200:

            return None, str(
                errors or
                f"HTTP {response.status_code}"
            ), dict(response.headers)

        if errors:

            return None, str(
                errors
            ), dict(response.headers)

        return (
            data,
            None,
            dict(response.headers)
        )

    except requests.exceptions.Timeout:

        return (
            None,
            "Timeout de API-Football.",
            {}
        )

    except Exception as e:

        return (
            None,
            str(e),
            {}
        )


# ============================================================
# FOOTBALL-DATA.ORG
# ============================================================

FOOTBALL_DATA_URL = (
    "https://api.football-data.org/v4"
)


def football_data(
    endpoint,
    params=None
):

    api_key = get_secret(
        "FOOTBALL_DATA_API_KEY"
    )

    if not api_key:

        return None, (
            "Falta FOOTBALL_DATA_API_KEY "
            "en Streamlit Secrets."
        )

    headers = {
        "X-Auth-Token": api_key
    }

    try:

        response = requests.get(
            FOOTBALL_DATA_URL + endpoint,
            headers=headers,
            params=params or {},
            timeout=20,
        )

        data = response.json()

        if response.status_code != 200:

            return None, str(
                data.get(
                    "message",
                    f"HTTP {response.status_code}"
                )
            )

        return data, None

    except Exception as e:

        return None, str(e)


# ============================================================
# DETECTAR TEMPORADA AUTOMÁTICAMENTE
# ============================================================

@st.cache_data(ttl=21600)
def detect_current_season(
    league_id
):

    """
    Busca las temporadas disponibles
    para la competición y selecciona
    automáticamente la temporada actual
    o la más cercana a la fecha actual.

    NO fija season=2026 manualmente.
    """

    data, error, headers = api_football(
        "/leagues",
        {
            "id": league_id
        }
    )

    if error:

        return None, error, headers

    responses = data.get(
        "response",
        []
    )

    if not responses:

        return (
            None,
            "API-Football no devolvió "
            "información de la competición.",
            headers
        )

    league_data = responses[0]

    seasons = league_data.get(
        "seasons",
        []
    )

    if not seasons:

        return (
            None,
            "La API no devolvió temporadas "
            "para esta competición.",
            headers
        )

    current_year = date.today().year
    current_month = date.today().month

    candidates = []

    for item in seasons:

        year = item.get(
            "year"
        )

        start = item.get(
            "start"
        )

        end = item.get(
            "end"
        )

        if year is None:
            continue

        try:
            year_int = int(year)
        except Exception:
            continue

        candidates.append({
            "year": year_int,
            "start": start,
            "end": end,
        })

    if not candidates:

        return (
            None,
            "No se encontraron temporadas "
            "válidas.",
            headers
        )

    # --------------------------------------------------------
    # 1. Buscar una temporada cuyo rango
    #    incluya hoy.
    # --------------------------------------------------------

    today = date.today()

    active = []

    for item in candidates:

        try:

            start_date = datetime.fromisoformat(
                item["start"]
            ).date()

            end_date = datetime.fromisoformat(
                item["end"]
            ).date()

            if start_date <= today <= end_date:

                active.append(
                    item
                )

        except Exception:
            continue

    if active:

        selected = max(
            active,
            key=lambda x: x["year"]
        )

        return (
            selected["year"],
            None,
            headers
        )

    # --------------------------------------------------------
    # 2. Si no encuentra una temporada
    #    activa, usar la más cercana.
    # --------------------------------------------------------

    candidates.sort(
        key=lambda x:
            abs(
                x["year"]
                - current_year
            )
    )

    selected = candidates[0]

    return (
        selected["year"],
        None,
        headers
    )


# ============================================================
# FIXTURES
# ============================================================

@st.cache_data(ttl=600)
def get_fixtures_by_dates(
    league_id,
    season,
    start_date,
    end_date
):

    params = {

        "league":
            league_id,

        "season":
            season,

        "from":
            start_date,

        "to":
            end_date,
    }

    data, error, headers = api_football(
        "/fixtures",
        params
    )

    if error:

        return (
            [],
            error,
            headers
        )

    return (
        data.get(
            "response",
            []
        ),
        None,
        headers
    )


# ============================================================
# NORMALIZAR FIXTURE
# ============================================================

def parse_date(value):

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

    dt = parse_date(value)

    if not dt:
        return "—"

    return dt.strftime(
        "%d/%m/%Y"
    )


def format_time(value):

    dt = parse_date(value)

    if not dt:
        return "—"

    return dt.strftime(
        "%H:%M"
    )


def normalize_fixture(
    fixture
):

    info = fixture.get(
        "fixture",
        {}
    )

    league = fixture.get(
        "league",
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

    status = info.get(
        "status",
        {}
    )

    venue = info.get(
        "venue",
        {}
    )

    return {

        "fixture_id":
            info.get("id"),

        "date_raw":
            info.get("date"),

        "date":
            format_date(
                info.get("date")
            ),

        "time":
            format_time(
                info.get("date")
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

        "home_id":
            home.get("id"),

        "away_id":
            away.get("id"),

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

        "league":
            league.get(
                "name"
            ),

        "season":
            league.get(
                "season"
            ),

        "status":
            status.get(
                "short"
            ),

        "venue":
            venue.get(
                "name"
            ),

        "city":
            venue.get(
                "city"
            ),
    }


# ============================================================
# ORDEN DE JORNADAS
# ============================================================

def round_sort_key(
    round_name
):

    if not round_name:

        return (
            9999,
            ""
        )

    text = str(
        round_name
    )

    match = re.search(
        r"(\d+)",
        text
    )

    if match:

        return (
            int(
                match.group(1)
            ),
            text
        )

    return (
        9999,
        text
    )


def group_rounds(
    fixtures
):

    grouped = defaultdict(list)

    for fixture in fixtures:

        match = normalize_fixture(
            fixture
        )

        round_name = match.get(
            "round"
        )

        if not round_name:

            round_name = (
                "Jornada no indicada"
            )

        grouped[
            round_name
        ].append(match)

    return dict(
        sorted(
            grouped.items(),
            key=lambda x:
                round_sort_key(
                    x[0]
                )
        )
    )


# ============================================================
# FOOTBALL-DATA — PARTIDOS
# ============================================================

@st.cache_data(ttl=900)
def get_fd_matches(
    competition
):

    data, error = football_data(
        f"/competitions/"
        f"{competition}/matches",
        {
            "status": "SCHEDULED"
        }
    )

    if error:

        return (
            pd.DataFrame(),
            error
        )

    rows = []

    for match in data.get(
        "matches",
        []
    ):

        rows.append({

            "id":
                match.get(
                    "id"
                ),

            "date":
                match.get(
                    "utcDate"
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

    return (
        pd.DataFrame(rows),
        None
    )


# ============================================================
# FOOTBALL-DATA — CLASIFICACIÓN
# ============================================================

@st.cache_data(ttl=1800)
def get_fd_standings(
    competition
):

    data, error = football_data(
        f"/competitions/"
        f"{competition}/standings"
    )

    if error:

        return (
            pd.DataFrame(),
            error
        )

    rows = []

    for standing in data.get(
        "standings",
        []
    ):

        if standing.get(
            "type"
        ) != "TOTAL":

            continue

        for row in standing.get(
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

    return (
        pd.DataFrame(rows),
        None
    )


# ============================================================
# PREDICCIONES
# ============================================================

@st.cache_data(ttl=900)
def get_prediction(
    fixture_id
):

    data, error, headers = api_football(
        "/predictions",
        {
            "fixture":
                fixture_id
        }
    )

    if error:

        return (
            None,
            error,
            headers
        )

    response = data.get(
        "response",
        []
    )

    if not response:

        return (
            None,
            None,
            headers
        )

    return (
        response[0],
        None,
        headers
    )


# ============================================================
# CUOTAS
# ============================================================

@st.cache_data(ttl=600)
def get_odds(
    fixture_id
):

    data, error, headers = api_football(
        "/odds",
        {
            "fixture":
                fixture_id
        }
    )

    if error:

        return (
            [],
            error,
            headers
        )

    return (
        data.get(
            "response",
            []
        ),
        None,
        headers
    )


# ============================================================
# EXTRAER PREDICCIÓN
# ============================================================

def prediction_rows(
    prediction
):

    if not prediction:

        return []

    p = prediction.get(
        "predictions",
        {}
    )

    rows = []

    winner = p.get(
        "winner"
    )

    if isinstance(
        winner,
        dict
    ):

        name = winner.get(
            "name"
        )

        comment = winner.get(
            "comment"
        )

        if name:

            rows.append(
                (
                    "🏆 Resultado",
                    name,
                    comment
                )
            )

    score = p.get(
        "score",
        {}
    )

    if (
        score.get("home")
        is not None
        and
        score.get("away")
        is not None
    ):

        rows.append(
            (
                "⚽ Marcador previsto",
                f"{score['home']}-"
                f"{score['away']}",
                None
            )
        )

    goals = p.get(
        "goals",
        {}
    )

    if goals.get(
        "home"
    ):

        rows.append(
            (
                "⚽ Goles local",
                str(
                    goals["home"]
                ),
                None
            )
        )

    if goals.get(
        "away"
    ):

        rows.append(
            (
                "⚽ Goles visitante",
                str(
                    goals["away"]
                ),
                None
            )
        )

    under_over = p.get(
        "under_over"
    )

    if under_over:

        rows.append(
            (
                "⚽ Under / Over",
                str(
                    under_over
                ),
                None
            )
        )

    advice = p.get(
        "advice"
    )

    if advice:

        rows.append(
            (
                "🧠 Análisis",
                str(
                    advice
                ),
                None
            )
        )

    return rows


# ============================================================
# EXTRAER CUOTAS REALES
# ============================================================

def extract_odds(
    odds_response
):

    rows = []

    relevant_words = [
        "goal",
        "corner",
        "card",
        "shot",
        "result",
        "match winner",
        "double chance",
        "total",
    ]

    for block in odds_response:

        bookmakers = block.get(
            "bookmakers",
            []
        )

        for bookmaker in bookmakers:

            bookmaker_name = (
                bookmaker.get(
                    "name",
                    "Bookmaker"
                )
            )

            for bet in bookmaker.get(
                "bets",
                []
            ):

                market = bet.get(
                    "name",
                    ""
                )

                if not any(
                    word in
                    market.lower()
                    for word in
                    relevant_words
                ):

                    continue

                for value in bet.get(
                    "values",
                    []
                ):

                    odd = value.get(
                        "odd"
                    )

                    if odd is None:
                        continue

                    try:

                        odd_float = float(
                            odd
                        )

                    except Exception:

                        continue

                    rows.append({

                        "bookmaker":
                            bookmaker_name,

                        "market":
                            market,

                        "selection":
                            value.get(
                                "value"
                            ),

                        "odds":
                            odd_float,
                    })

    return rows


# ============================================================
# MOSTRAR CUOTAS
# ============================================================

def render_odds(
    fixture_id
):

    st.markdown(
        "#### 💰 Cuotas reales"
    )

    odds, error, headers = get_odds(
        fixture_id
    )

    if error:

        st.warning(
            f"No se pudieron consultar "
            f"las cuotas: {error}"
        )

        return

    rows = extract_odds(
        odds
    )

    if not rows:

        st.markdown(
            '<div class="no-data">'
            'No hay cuotas reales '
            'disponibles para este partido.'
            '</div>',
            unsafe_allow_html=True
        )

        return

    df = pd.DataFrame(
        rows
    )

    markets = (
        df["market"]
        .drop_duplicates()
        .tolist()
    )

    for market in markets:

        market_df = df[
            df["market"] == market
        ]

        with st.expander(
            market,
            expanded=False
        ):

            for _, row in (
                market_df.head(20)
                .iterrows()
            ):

                st.write(
                    f"**{row['selection']}** "
                    f"— {row['odds']:.2f} "
                    f"· {row['bookmaker']}"
                )

    st.caption(
        "Solo se muestran cuotas "
        "devueltas por API-Football. "
        "No se generan cuotas artificiales."
    )


# ============================================================
# ANÁLISIS DEL PARTIDO
# ============================================================

def render_match_analysis(
    match
):

    fixture_id = match[
        "fixture_id"
    ]

    st.markdown(
        f"""
        <div class="info-card">

        <div class="small">
        {match["date"]} · {match["time"]}
        </div>

        <h3 style="margin:5px 0;">
        {match["home"]}
        vs
        {match["away"]}
        </h3>

        <div class="small">
        {match.get("venue") or "Estadio no indicado"}
        </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # PREDICCIÓN
    # --------------------------------------------------------

    st.markdown(
        "#### 🔮 Pronóstico"
    )

    prediction, error, headers = (
        get_prediction(
            fixture_id
        )
    )

    if error:

        st.warning(
            error
        )

    else:

        rows = prediction_rows(
            prediction
        )

        if not rows:

            st.markdown(
                '<div class="no-data">'
                'API-Football no ha devuelto '
                'pronóstico para este encuentro.'
                '</div>',
                unsafe_allow_html=True
            )

        else:

            for (
                market,
                selection,
                comment
            ) in rows:

                extra = ""

                if comment:

                    extra = (
                        "<br><span "
                        "class='small'>"
                        f"{comment}"
                        "</span>"
                    )

                st.markdown(
                    f"""
                    <div class="market-card">

                    <b>{market}</b><br>

                    {selection}

                    {extra}

                    </div>
                    """,
                    unsafe_allow_html=True
                )

    # --------------------------------------------------------
    # CUOTAS
    # --------------------------------------------------------

    render_odds(
        fixture_id
    )


# ============================================================
# RESUMEN
# ============================================================

def render_summary(
    fixtures,
    grouped,
    season
):

    col1, col2, col3, col4 = (
        st.columns(4)
    )

    with col1:

        st.markdown(
            f"""
            <div class="metric">
            <div class="metric-label">
            PARTIDOS
            </div>
            <div class="metric-value">
            {len(fixtures)}
            </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:

        st.markdown(
            f"""
            <div class="metric">
            <div class="metric-label">
            JORNADAS
            </div>
            <div class="metric-value">
            {len(grouped)}
            </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col3:

        dates = sorted(
            set(
                f["date"]
                for f in fixtures
            )
        )

        st.markdown(
            f"""
            <div class="metric">
            <div class="metric-label">
            FECHAS
            </div>
            <div class="metric-value">
            {len(dates)}
            </div>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col4:

        st.markdown(
            f"""
            <div class="metric">
            <div class="metric-label">
            TEMPORADA
            </div>
            <div class="metric-value">
            {season}
            </div>
            </div>
            """,
            unsafe_allow_html=True
        )


# ============================================================
# MAIN
# ============================================================

def main():

    st.markdown(
        '<div class="app-title">'
        '⚽ ValueBet Pro V7.3'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="app-subtitle">'
        'Partidos · Jornadas · Pronósticos · '
        'Cuotas reales'
        '</div>',
        unsafe_allow_html=True
    )

    # ========================================================
    # SIDEBAR
    # ========================================================

    with st.sidebar:

        st.header(
            "⚙️ Configuración"
        )

        competition_name = st.selectbox(
            "Competición",
            list(
                COMPETITIONS.keys()
            ),
            index=0
        )

        st.divider()

        days_ahead = st.slider(
            "Días de calendario",
            min_value=3,
            max_value=21,
            value=14,
            step=1
        )

        st.caption(
            "La app no utiliza `next` ni "
            "`/fixtures/rounds`."
        )

        st.caption(
            "La temporada se detecta "
            "automáticamente."
        )

        st.divider()

        if st.button(
            "🔄 Actualizar datos",
            use_container_width=True
        ):

            st.cache_data.clear()
            st.rerun()

    competition = COMPETITIONS[
        competition_name
    ]

    league_id = competition[
        "api_id"
    ]

    fd_code = competition[
        "football_data"
    ]

    # ========================================================
    # DETECCIÓN DE TEMPORADA
    # ========================================================

    with st.spinner(
        "Detectando temporada..."
    ):

        (
            season,
            season_error,
            season_headers
        ) = detect_current_season(
            league_id
        )

    if season_error:

        st.error(
            "No se pudo detectar "
            "automáticamente la temporada."
        )

        st.code(
            season_error
        )

        st.info(
            "La aplicación utiliza "
            "/leagues para conocer las "
            "temporadas disponibles para "
            "tu cuenta y evitar enviar "
            "una temporada que tu plan "
            "Free no tenga disponible."
        )

        return

    # ========================================================
    # FECHAS
    # ========================================================

    today = date.today()

    end_date = (
        today
        + timedelta(
            days=days_ahead
        )
    )

    start_string = (
        today.isoformat()
    )

    end_string = (
        end_date.isoformat()
    )

    # ========================================================
    # FIXTURES
    # ========================================================

    with st.spinner(
        "Cargando próximos partidos..."
    ):

        (
            fixtures_raw,
            api_error,
            fixture_headers
        ) = get_fixtures_by_dates(
            league_id,
            season,
            start_string,
            end_string
        )

    # ========================================================
    # FOOTBALL-DATA
    # ========================================================

    fd_matches, fd_error = (
        get_fd_matches(
            fd_code
        )
    )

    # ========================================================
    # ERROR
    # ========================================================

    if api_error:

        st.error(
            "No se pudieron obtener "
            "los próximos partidos."
        )

        st.code(
            api_error
        )

        st.info(
            f"La aplicación detectó "
            f"automáticamente la temporada "
            f"**{season}** y realizó la consulta "
            f"con `league + season + from + to`."
        )

        return

    # ========================================================
    # NORMALIZAR
    # ========================================================

    fixtures = [
        normalize_fixture(
            f
        )
        for f in fixtures_raw
    ]

    fixtures = sorted(
        fixtures,
        key=lambda x:
            x["date_raw"] or ""
    )

    grouped = group_rounds(
        fixtures_raw
    )

    # ========================================================
    # RESUMEN
    # ========================================================

    render_summary(
        fixtures,
        grouped,
        season
    )

    st.write("")

    # ========================================================
    # TABS
    # ========================================================

    (
        tab_predictions,
        tab_matches,
        tab_table,
        tab_status
    ) = st.tabs(
        [
            "🔮 Pronósticos",
            "📅 Partidos",
            "🏆 Clasificación",
            "🔧 Estado",
        ]
    )

    # ========================================================
    # PRONÓSTICOS
    # ========================================================

    with tab_predictions:

        st.markdown(
            '<div class="section-title">'
            '🔮 Pronósticos'
            '</div>',
            unsafe_allow_html=True
        )

        st.caption(
            "Los pronósticos y las cuotas "
            "se consultan directamente de "
            "API-Football cuando seleccionas "
            "un partido."
        )

        if not fixtures:

            st.info(
                f"No hay partidos entre "
                f"{start_string} y "
                f"{end_string}."
            )

        else:

            for round_name, matches in (
                grouped.items()
            ):

                st.markdown(
                    f"### {round_name}"
                )

                for match in matches:

                    col1, col2, col3 = (
                        st.columns(
                            [1.4, 5, 1.2]
                        )
                    )

                    with col1:

                        st.markdown(
                            f"**{match['time']}**"
                        )

                        st.caption(
                            match["date"]
                        )

                    with col2:

                        st.markdown(
                            f"**{match['home']}**"
                        )

                        st.markdown(
                            f"vs **{match['away']}**"
                        )

                    with col3:

                        show = st.button(
                            "Ver",
                            key=(
                                "view_"
                                f"{match['fixture_id']}"
                            ),
                            use_container_width=True
                        )

                    if show:

                        st.session_state[
                            "selected_fixture"
                        ] = match[
                            "fixture_id"
                        ]

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

                        render_match_analysis(
                            match
                        )

                        st.divider()

    # ========================================================
    # PARTIDOS
    # ========================================================

    with tab_matches:

        st.markdown(
            '<div class="section-title">'
            '📅 Partidos por jornadas'
            '</div>',
            unsafe_allow_html=True
        )

        st.caption(
            f"Temporada detectada: "
            f"**{season}** · "
            f"{start_string} → {end_string}"
        )

        if not fixtures:

            st.info(
                "No hay partidos disponibles "
                "en el periodo seleccionado."
            )

        else:

            for round_name, matches in (
                grouped.items()
            ):

                dates = sorted(
                    set(
                        m["date"]
                        for m in matches
                    )
                )

                st.markdown(
                    f"""
                    <div class="round-card">

                    <div class="round-title">
                    📋 {round_name}
                    </div>

                    <div class="round-subtitle">
                    {" · ".join(dates)}
                    · {len(matches)} partidos
                    </div>

                    </div>
                    """,
                    unsafe_allow_html=True
                )

                for match in matches:

                    home_logo = ""

                    away_logo = ""

                    if match[
                        "home_logo"
                    ]:

                        home_logo = (
                            f'<img src="'
                            f'{match["home_logo"]}" '
                            f'width="24" '
                            f'style="vertical-align:middle;'
                            f'margin-right:6px;">'
                        )

                    if match[
                        "away_logo"
                    ]:

                        away_logo = (
                            f'<img src="'
                            f'{match["away_logo"]}" '
                            f'width="24" '
                            f'style="vertical-align:middle;'
                            f'margin-right:6px;">'
                        )

                    st.markdown(
                        f"""
                        <div class="match-card">

                        <div class="match-date">
                        📅 {match["date"]}
                        &nbsp; · &nbsp;
                        ⏰ {match["time"]}
                        </div>

                        <div style="
                        display:grid;
                        grid-template-columns:
                        1fr auto 1fr;
                        align-items:center;
                        gap:8px;
                        ">

                        <div class="team-name">
                        {home_logo}
                        {match["home"]}
                        </div>

                        <div class="vs">
                        VS
                        </div>

                        <div class="team-name"
                        style="text-align:right;">
                        {away_logo}
                        {match["away"]}
                        </div>

                        </div>

                        </div>
                        """,
                        unsafe_allow_html=True
                    )

    # ========================================================
    # CLASIFICACIÓN
    # ========================================================

    with tab_table:

        st.markdown(
            '<div class="section-title">'
            '🏆 Clasificación'
            '</div>',
            unsafe_allow_html=True
        )

        standings, standings_error = (
            get_fd_standings(
                fd_code
            )
        )

        if standings_error:

            st.warning(
                "No se pudo obtener "
                "la clasificación."
            )

            st.code(
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
    # ESTADO
    # ========================================================

    with tab_status:

        st.markdown(
            '<div class="section-title">'
            '🔧 Estado de las fuentes'
            '</div>',
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # API FOOTBALL
        # ----------------------------------------------------

        st.markdown(
            '<div class="api-box">',
            unsafe_allow_html=True
        )

        st.markdown(
            "### ⚽ API-Football"
        )

        st.write(
            "Estado: "
            "**Conectada**"
        )

        st.write(
            f"Competición: "
            f"**{competition_name}**"
        )

        st.write(
            f"League ID: "
            f"**{league_id}**"
        )

        st.write(
            f"Temporada detectada: "
            f"**{season}**"
        )

        st.write(
            f"Periodo: "
            f"**{start_string} → {end_string}**"
        )

        st.write(
            "Endpoint: "
            "**/fixtures**"
        )

        st.write(
            "Método: "
            "**league + season + from + to**"
        )

        st.write(
            "`next`: ❌ No utilizado"
        )

        st.write(
            "`/fixtures/rounds`: "
            "❌ No utilizado"
        )

        st.write(
            f"Partidos: "
            f"**{len(fixtures)}**"
        )

        # Headers de consumo

        remaining = (
            fixture_headers.get(
                "x-ratelimit-requests-remaining"
            )
            or fixture_headers.get(
                "X-RateLimit-Remaining"
            )
        )

        daily_limit = (
            fixture_headers.get(
                "x-ratelimit-requests-limit"
            )
        )

        if remaining:

            st.write(
                f"Requests restantes: "
                f"**{remaining}**"
            )

        if daily_limit:

            st.write(
                f"Límite diario: "
                f"**{daily_limit}**"
            )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # FOOTBALL DATA
        # ----------------------------------------------------

        st.markdown(
            '<div class="api-box">',
            unsafe_allow_html=True
        )

        st.markdown(
            "### 🏆 football-data.org"
        )

        if fd_error:

            st.markdown(
                '<span class="status-warning">'
                '⚠️ No disponible'
                '</span>',
                unsafe_allow_html=True
            )

            st.code(
                fd_error
            )

        else:

            st.markdown(
                '<span class="status-ok">'
                '✓ Conectada'
                '</span>',
                unsafe_allow_html=True
            )

            st.write(
                f"Partidos complementarios: "
                f"**{len(fd_matches)}**"
            )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # INFORMACIÓN
        # ----------------------------------------------------

        st.info(
            "La V7.3 detecta primero la "
            "temporada disponible para la "
            "competición mediante API-Football. "
            "Después consulta los partidos "
            "usando esa temporada y un rango "
            "de fechas."
        )

    # ========================================================
    # FOOTER
    # ========================================================

    st.divider()

    st.caption(
        "ValueBet Football Pro V7.3 · "
        "API-Football + football-data.org · "
        "Datos reales · Sin cuotas inventadas"
    )


# ============================================================
# EJECUTAR
# ============================================================

if __name__ == "__main__":
    main()
