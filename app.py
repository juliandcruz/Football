import streamlit as st
import pandas as pd
import requests
import re
import unicodedata
from datetime import datetime, date, timedelta, timezone
from collections import defaultdict
from difflib import SequenceMatcher


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="ValueBet Pro V7.4",
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

.status-error {
    color: #e74c3c;
    font-weight: 700;
}

.api-box {
    border: 1px solid rgba(128,128,128,.15);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 10px;
    background: rgba(128,128,128,.035);
}

.source-badge {
    display: inline-block;
    padding: 3px 8px;
    border-radius: 7px;
    background: rgba(52,152,219,.12);
    font-size: .68rem;
    font-weight: 700;
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


def api_football(endpoint, params=None):

    api_key = get_secret(
        "API_FOOTBALL_KEY"
    )

    if not api_key:

        return (
            None,
            "Falta API_FOOTBALL_KEY "
            "en Streamlit Secrets.",
            {}
        )

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

            return (
                None,
                f"Respuesta no válida "
                f"HTTP {response.status_code}",
                dict(response.headers)
            )

        errors = data.get("errors")

        if response.status_code != 200:

            return (
                None,
                str(
                    errors or
                    f"HTTP {response.status_code}"
                ),
                dict(response.headers)
            )

        if errors:

            return (
                None,
                str(errors),
                dict(response.headers)
            )

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


def football_data(endpoint, params=None):

    api_key = get_secret(
        "FOOTBALL_DATA_API_KEY"
    )

    if not api_key:

        return (
            None,
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

        try:
            data = response.json()

        except Exception:

            return (
                None,
                f"Respuesta no válida "
                f"HTTP {response.status_code}"
            )

        if response.status_code != 200:

            return (
                None,
                str(
                    data.get(
                        "message",
                        f"HTTP {response.status_code}"
                    )
                )
            )

        return data, None

    except requests.exceptions.Timeout:

        return (
            None,
            "Timeout de football-data.org."
        )

    except Exception as e:

        return (
            None,
            str(e)
        )


# ============================================================
# UTILIDADES
# ============================================================

def parse_datetime(value):

    if not value:
        return None

    try:

        text = str(value)

        if text.endswith("Z"):
            text = text[:-1] + "+00:00"

        return datetime.fromisoformat(text)

    except Exception:

        return None


def display_date(value):

    dt = parse_datetime(value)

    if not dt:
        return "—"

    return dt.strftime(
        "%d/%m/%Y"
    )


def display_time(value):

    dt = parse_datetime(value)

    if not dt:
        return "—"

    return dt.strftime(
        "%H:%M"
    )


def normalize_name(name):

    if not name:
        return ""

    text = str(name).lower().strip()

    text = unicodedata.normalize(
        "NFKD",
        text
    )

    text = "".join(
        c for c in text
        if not unicodedata.combining(c)
    )

    replacements = {
        "fc": "",
        "cf": "",
        "afc": "",
        "ac": "",
        "ud": "",
        "cd": "",
        "real ": "",
        "club ": "",
    }

    for old, new in replacements.items():

        text = text.replace(
            old,
            new
        )

    text = re.sub(
        r"[^a-z0-9]+",
        " ",
        text
    )

    return " ".join(
        text.split()
    )


def team_similarity(a, b):

    a_norm = normalize_name(a)
    b_norm = normalize_name(b)

    if not a_norm or not b_norm:
        return 0.0

    if a_norm == b_norm:
        return 1.0

    if (
        a_norm in b_norm
        or
        b_norm in a_norm
    ):
        return 0.92

    return SequenceMatcher(
        None,
        a_norm,
        b_norm
    ).ratio()


def match_similarity(
    home_a,
    away_a,
    home_b,
    away_b
):

    home_score = team_similarity(
        home_a,
        home_b
    )

    away_score = team_similarity(
        away_a,
        away_b
    )

    return (
        home_score + away_score
    ) / 2


# ============================================================
# FOOTBALL-DATA
# PRÓXIMOS PARTIDOS
# ============================================================

@st.cache_data(ttl=600)
def get_fd_upcoming_matches(
    competition,
    days_ahead
):

    today = date.today()

    end_date = (
        today
        + timedelta(
            days=days_ahead
        )
    )

    params = {
        "status": "SCHEDULED",
        "dateFrom":
            today.isoformat(),
        "dateTo":
            end_date.isoformat(),
    }

    data, error = football_data(
        f"/competitions/"
        f"{competition}/matches",
        params
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

        utc_date = match.get(
            "utcDate"
        )

        home = match.get(
            "homeTeam",
            {}
        )

        away = match.get(
            "awayTeam",
            {}
        )

        rows.append({

            "fd_id":
                match.get("id"),

            "date_raw":
                utc_date,

            "date":
                display_date(
                    utc_date
                ),

            "time":
                display_time(
                    utc_date
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

            "home_crest":
                home.get(
                    "crest",
                    ""
                ),

            "away_crest":
                away.get(
                    "crest",
                    ""
                ),

            "matchday":
                match.get(
                    "matchday"
                ),

            "stage":
                match.get(
                    "stage"
                ),

            "status":
                match.get(
                    "status"
                ),

            "venue":
                None,

            "source":
                "football-data.org",
        })

    df = pd.DataFrame(
        rows
    )

    if not df.empty:

        df = df.sort_values(
            "date_raw"
        )

    return (
        df,
        None
    )


# ============================================================
# AGRUPAR POR JORNADA
# ============================================================

def get_round_label(
    matchday
):

    if matchday is None:
        return "Jornada no indicada"

    try:

        return f"Jornada {int(matchday)}"

    except Exception:

        return str(
            matchday
        )


def group_fd_matches(
    df
):

    grouped = defaultdict(list)

    if df.empty:
        return {}

    for _, row in df.iterrows():

        round_name = get_round_label(
            row.get("matchday")
        )

        grouped[
            round_name
        ].append(
            row.to_dict()
        )

    def sort_key(item):

        name = item[0]

        m = re.search(
            r"(\d+)",
            name
        )

        if m:
            return int(
                m.group(1)
            )

        return 9999

    return dict(
        sorted(
            grouped.items(),
            key=sort_key
        )
    )


# ============================================================
# API-FOOTBALL
# FIXTURES ACCESIBLES
#
# IMPORTANTE:
# No se consulta la temporada actual.
# Se utiliza exclusivamente una temporada
# que el plan de la cuenta permita consultar.
# ============================================================

@st.cache_data(ttl=21600)
def get_accessible_api_football_seasons(
    league_id
):

    data, error, headers = api_football(
        "/leagues",
        {
            "id": league_id
        }
    )

    if error:

        return (
            [],
            error,
            headers
        )

    responses = data.get(
        "response",
        []
    )

    if not responses:

        return (
            [],
            "API-Football no devolvió "
            "la competición.",
            headers
        )

    seasons = responses[0].get(
        "seasons",
        []
    )

    years = []

    for item in seasons:

        year = item.get(
            "year"
        )

        if year is None:
            continue

        try:
            years.append(
                int(year)
            )

        except Exception:
            continue

    return (
        sorted(
            set(years),
            reverse=True
        ),
        None,
        headers
    )


# ============================================================
# BUSCAR FIXTURES API-FOOTBALL EN TEMPORADAS
# ACCESIBLES
# ============================================================

@st.cache_data(ttl=21600)
def find_api_football_matches(
    league_id,
    start_date,
    end_date
):

    seasons, season_error, headers = (
        get_accessible_api_football_seasons(
            league_id
        )
    )

    if season_error:

        return (
            [],
            season_error,
            headers,
            []
        )

    # --------------------------------------------------------
    # IMPORTANTE
    #
    # No intentamos utilizar automáticamente
    # la temporada 2026.
    #
    # El plan Free del usuario permite
    # determinadas temporadas antiguas.
    #
    # Probamos únicamente temporadas
    # que API-Football pueda aceptar.
    # --------------------------------------------------------

    preferred = [
        2024,
        2023,
        2022,
    ]

    accessible = [
        y for y in preferred
        if y in seasons
    ]

    if not accessible:

        accessible = [
            y for y in seasons
            if y <= 2024
        ][:3]

    if not accessible:

        return (
            [],
            "No se encontraron temporadas "
            "históricas accesibles para "
            "API-Football.",
            headers,
            seasons
        )

    all_fixtures = []

    for season in accessible:

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

        data, error, local_headers = (
            api_football(
                "/fixtures",
                params
            )
        )

        if error:
            continue

        response = data.get(
            "response",
            []
        )

        all_fixtures.extend(
            response
        )

    return (
        all_fixtures,
        None,
        headers,
        accessible
    )


# ============================================================
# NORMALIZAR FIXTURE API-FOOTBALL
# ============================================================

def normalize_api_fixture(
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

    return {

        "api_fixture_id":
            info.get("id"),

        "date_raw":
            info.get("date"),

        "date":
            display_date(
                info.get("date")
            ),

        "time":
            display_time(
                info.get("date")
            ),

        "home":
            home.get(
                "name",
                ""
            ),

        "away":
            away.get(
                "name",
                ""
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

        "season":
            league.get(
                "season"
            ),
    }


# ============================================================
# INTENTAR ENLAZAR PARTIDO ENTRE LAS DOS APIs
# ============================================================

def find_best_api_fixture(
    fd_match,
    api_matches
):

    if not api_matches:
        return None, 0.0

    best = None
    best_score = 0.0

    fd_home = fd_match.get(
        "home",
        ""
    )

    fd_away = fd_match.get(
        "away",
        ""
    )

    fd_date = parse_datetime(
        fd_match.get(
            "date_raw"
        )
    )

    for raw_fixture in api_matches:

        api_match = (
            normalize_api_fixture(
                raw_fixture
            )
        )

        score = match_similarity(
            fd_home,
            fd_away,
            api_match["home"],
            api_match["away"]
        )

        # ----------------------------------------------------
        # La fecha ayuda mucho a evitar coincidencias falsas.
        # ----------------------------------------------------

        api_date = parse_datetime(
            api_match.get(
                "date_raw"
            )
        )

        if fd_date and api_date:

            date_difference = abs(
                (
                    fd_date.date()
                    -
                    api_date.date()
                ).days
            )

            if date_difference == 0:
                score += 0.08

            elif date_difference == 1:
                score += 0.02

            else:
                score -= 0.15

        if score > best_score:

            best_score = score
            best = api_match

    if best_score >= 0.82:

        return (
            best,
            best_score
        )

    return (
        None,
        best_score
    )


# ============================================================
# PREDICCIONES API-FOOTBALL
# ============================================================

@st.cache_data(ttl=900)
def get_prediction(
    fixture_id
):

    data, error, headers = (
        api_football(
            "/predictions",
            {
                "fixture":
                    fixture_id
            }
        )
    )

    if error:

        return (
            None,
            error
        )

    response = data.get(
        "response",
        []
    )

    if not response:

        return (
            None,
            None
        )

    return (
        response[0],
        None
    )


# ============================================================
# CUOTAS API-FOOTBALL
# ============================================================

@st.cache_data(ttl=900)
def get_odds(
    fixture_id
):

    data, error, headers = (
        api_football(
            "/odds",
            {
                "fixture":
                    fixture_id
            }
        )
    )

    if error:

        return (
            [],
            error
        )

    return (
        data.get(
            "response",
            []
        ),
        None
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
        score.get("home") is not None
        and
        score.get("away") is not None
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

    if goals.get("home"):

        rows.append(
            (
                "⚽ Goles local",
                str(
                    goals["home"]
                ),
                None
            )
        )

    if goals.get("away"):

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

    odds, error = get_odds(
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
            'disponibles para este fixture.'
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
                market_df
                .head(30)
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
        "No se generan cuotas."
    )


# ============================================================
# ANÁLISIS DEL PARTIDO
# ============================================================

def render_match_analysis(
    fd_match,
    api_match=None,
    match_score=0
):

    st.markdown(
        f"""
        <div class="info-card">

        <div class="match-date">
        📅 {fd_match["date"]}
        &nbsp; · &nbsp;
        ⏰ {fd_match["time"]} UTC
        </div>

        <h3 style="margin:5px 0;">
        {fd_match["home"]}
        vs
        {fd_match["away"]}
        </h3>

        <div class="small">
        Jornada:
        {get_round_label(fd_match.get("matchday"))}
        </div>

        </div>
        """,
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # NO HAY ENLACE CON API-FOOTBALL
    # --------------------------------------------------------

    if api_match is None:

        st.markdown(
            '<div class="no-data">'
            'ℹ️ Este partido procede de '
            'football-data.org, pero no se ha '
            'podido enlazar de forma segura con '
            'un fixture de API-Football accesible '
            'en tu plan actual.'
            '<br><br>'
            'Por seguridad, no se muestran '
            'pronósticos ni cuotas inventadas.'
            '</div>',
            unsafe_allow_html=True
        )

        return

    # --------------------------------------------------------
    # ENLACE
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="source-badge">
        ✓ Fixture enlazado con API-Football
        · Coincidencia {match_score * 100:.0f}%
        </div>
        """,
        unsafe_allow_html=True
    )

    fixture_id = api_match.get(
        "api_fixture_id"
    )

    if not fixture_id:

        st.warning(
            "No se encontró ID de fixture "
            "válido en API-Football."
        )

        return

    # --------------------------------------------------------
    # PREDICCIÓN
    # --------------------------------------------------------

    st.markdown(
        "#### 🔮 Pronóstico"
    )

    prediction, error = (
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
                'pronóstico para este fixture.'
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
                        "style='opacity:.6;"
                        "font-size:.75rem;'>"
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
# CLASIFICACIÓN
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
# RESUMEN
# ============================================================

def render_summary(
    matches_df,
    linked_count
):

    total = len(
        matches_df
    )

    rounds = (
        matches_df[
            "matchday"
        ]
        .dropna()
        .nunique()
        if not matches_df.empty
        else 0
    )

    dates = (
        matches_df[
            "date"
        ]
        .nunique()
        if not matches_df.empty
        else 0
    )

    cols = st.columns(
        4
    )

    metrics = [
        ("PARTIDOS", total),
        ("JORNADAS", rounds),
        ("FECHAS", dates),
        ("ENLAZADOS", linked_count),
    ]

    for col, (
        label,
        value
    ) in zip(
        cols,
        metrics
    ):

        with col:

            st.markdown(
                f"""
                <div class="metric">
                <div class="metric-label">
                {label}
                </div>
                <div class="metric-value">
                {value}
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
        '⚽ ValueBet Pro V7.4'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="app-subtitle">'
        'Calendario real · Jornadas · '
        'Pronósticos · Cuotas reales'
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

        days_ahead = st.slider(
            "Días de calendario",
            min_value=3,
            max_value=30,
            value=14,
            step=1
        )

        st.divider()

        st.caption(
            "La V7.4 utiliza "
            "football-data.org como fuente "
            "principal del calendario."
        )

        st.caption(
            "API-Football se utiliza para "
            "datos de análisis cuando existe "
            "un fixture accesible y enlazable."
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
    # CARGAR FOOTBALL-DATA
    # ========================================================

    with st.spinner(
        "Cargando próximos partidos..."
    ):

        (
            matches_df,
            fd_error
        ) = get_fd_upcoming_matches(
            fd_code,
            days_ahead
        )

    if fd_error:

        st.error(
            "No se pudieron obtener "
            "los próximos partidos."
        )

        st.code(
            fd_error
        )

        return

    # ========================================================
    # CARGAR FIXTURES API-FOOTBALL
    #
    # Esto es opcional. Si falla, el calendario
    # de football-data sigue funcionando.
    # ========================================================

    api_fixtures = []
    api_error = None
    accessible_seasons = []

    with st.spinner(
        "Comprobando datos complementarios..."
    ):

        (
            api_fixtures,
            api_error,
            api_headers,
            accessible_seasons
        ) = find_api_football_matches(
            league_id,
            start_string,
            end_string
        )

    # ========================================================
    # ENLAZAR PARTIDOS
    # ========================================================

    linked_matches = {}

    if not matches_df.empty:

        for index, row in (
            matches_df.iterrows()
        ):

            fd_match = row.to_dict()

            best, score = (
                find_best_api_fixture(
                    fd_match,
                    api_fixtures
                )
            )

            if best:

                linked_matches[
                    row["fd_id"]
                ] = {
                    "fixture":
                        best,
                    "score":
                        score
                }

    linked_count = len(
        linked_matches
    )

    # ========================================================
    # RESUMEN
    # ========================================================

    render_summary(
        matches_df,
        linked_count
    )

    st.write("")

    # ========================================================
    # AGRUPACIÓN
    # ========================================================

    grouped = group_fd_matches(
        matches_df
    )

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
            "Los partidos proceden de "
            "football-data.org. Los datos "
            "de API-Football solo aparecen "
            "cuando existe un enlace fiable."
        )

        if matches_df.empty:

            st.info(
                "No hay partidos programados "
                f"entre {start_string} "
                f"y {end_string}."
            )

        else:

            for (
                round_name,
                matches
            ) in grouped.items():

                st.markdown(
                    f"### {round_name}"
                )

                for match in matches:

                    fd_id = match[
                        "fd_id"
                    ]

                    linked = (
                        linked_matches.get(
                            fd_id
                        )
                    )

                    col1, col2, col3 = (
                        st.columns(
                            [1.35, 5, 1.2]
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

                        if linked:

                            button_text = (
                                "Analizar"
                            )

                        else:

                            button_text = (
                                "Ver"
                            )

                        show = st.button(
                            button_text,
                            key=(
                                "analysis_"
                                f"{fd_id}"
                            ),
                            use_container_width=True
                        )

                    if show:

                        st.session_state[
                            "selected_fd_match"
                        ] = fd_id

                    selected = (
                        st.session_state.get(
                            "selected_fd_match"
                        )
                    )

                    if (
                        selected == fd_id
                    ):

                        api_match = None
                        score = 0.0

                        if linked:

                            api_match = (
                                linked[
                                    "fixture"
                                ]
                            )

                            score = (
                                linked[
                                    "score"
                                ]
                            )

                        render_match_analysis(
                            match,
                            api_match,
                            score
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
            f"{start_string} → "
            f"{end_string} · "
            f"Horario mostrado en UTC"
        )

        if matches_df.empty:

            st.info(
                "No hay partidos disponibles "
                "en el periodo seleccionado."
            )

        else:

            for (
                round_name,
                matches
            ) in grouped.items():

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

                    if match.get(
                        "home_crest"
                    ):

                        home_logo = (
                            f'<img src="'
                            f'{match["home_crest"]}" '
                            f'width="24" '
                            f'style="vertical-align:middle;'
                            f'margin-right:6px;">'
                        )

                    if match.get(
                        "away_crest"
                    ):

                        away_logo = (
                            f'<img src="'
                            f'{match["away_crest"]}" '
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
                        ⏰ {match["time"]} UTC
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
            '🔧 Estado de las APIs'
            '</div>',
            unsafe_allow_html=True
        )

        # ----------------------------------------------------
        # FOOTBALL-DATA
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
                '<span class="status-error">'
                '✕ Error'
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
                f"Competición: "
                f"**{competition_name}**"
            )

            st.write(
                f"Partidos próximos: "
                f"**{len(matches_df)}**"
            )

            st.write(
                f"Jornadas: "
                f"**{len(grouped)}**"
            )

            st.write(
                "Fuente principal del calendario: "
                "**Sí**"
            )

        st.markdown(
            '</div>',
            unsafe_allow_html=True
        )

        # ------------------------------------------------
