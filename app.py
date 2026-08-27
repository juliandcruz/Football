import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
import re
from datetime import datetime, timezone, date
from typing import Optional, Dict, List, Tuple


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

st.markdown(
    """
<style>

.block-container {
    max-width: 1180px;
    padding: 1rem .7rem 4rem .7rem;
}

.main-title {
    font-size: 1.8rem;
    font-weight: 850;
    margin-bottom: 0;
}

.subtitle {
    opacity: .55;
    font-size: .82rem;
    margin-bottom: 18px;
}

.section-title {
    font-size: 1.25rem;
    font-weight: 800;
    margin: 10px 0 12px 0;
}

.round-card {
    border: 1px solid rgba(128,128,128,.16);
    border-radius: 16px;
    padding: 13px 15px;
    margin-bottom: 10px;
    background: rgba(128,128,128,.035);
}

.match-card {
    border: 1px solid rgba(128,128,128,.15);
    border-radius: 15px;
    padding: 14px;
    margin-bottom: 10px;
    background: rgba(128,128,128,.025);
}

.team-line {
    font-size: .96rem;
    font-weight: 750;
}

.match-date {
    font-size: .75rem;
    opacity: .55;
}

.market-card {
    border: 1px solid rgba(128,128,128,.13);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 8px;
    background: rgba(128,128,128,.025);
}

.market-title {
    font-weight: 750;
    font-size: .95rem;
}

.metric {
    background: rgba(128,128,128,.06);
    border-radius: 10px;
    padding: 8px;
    text-align: center;
}

.metric-label {
    font-size: .66rem;
    opacity: .55;
}

.metric-value {
    font-size: .98rem;
    font-weight: 750;
}

.value-badge {
    display: inline-block;
    background: rgba(46,204,113,.14);
    color: #2ecc71;
    padding: 4px 8px;
    border-radius: 7px;
    font-size: .7rem;
    font-weight: 800;
}

.no-value-badge {
    display: inline-block;
    background: rgba(128,128,128,.12);
    padding: 4px 8px;
    border-radius: 7px;
    font-size: .7rem;
}

.no-odds-badge {
    display: inline-block;
    background: rgba(241,196,15,.12);
    color: #f1c40f;
    padding: 4px 8px;
    border-radius: 7px;
    font-size: .7rem;
}

.positive {
    color: #2ecc71;
}

.negative {
    color: #e74c3c;
}

.info-line {
    font-size: .75rem;
    opacity: .58;
}

@media (max-width: 700px) {

    .main-title {
        font-size: 1.5rem;
    }

    .block-container {
        padding-left: .55rem;
        padding-right: .55rem;
    }

    .team-line {
        font-size: .9rem;
    }

}

</style>
""",
    unsafe_allow_html=True,
)


# ============================================================
# COMPETICIONES
# ============================================================

COMPETITIONS = {

    "🇪🇸 La Liga": {
        "football_data": "PD",
        "api_football": 140,
    },

    "🇬🇧 Premier League": {
        "football_data": "PL",
        "api_football": 39,
    },

    "🇪🇺 Champions League": {
        "football_data": "CL",
        "api_football": 2,
    },

    "🇮🇹 Serie A": {
        "football_data": "SA",
        "api_football": 135,
    },

    "🇩🇪 Bundesliga": {
        "football_data": "BL1",
        "api_football": 78,
    },

    "🇫🇷 Ligue 1": {
        "football_data": "FL1",
        "api_football": 61,
    },
}


# ============================================================
# SECRETS
# ============================================================

def get_secret(name: str) -> Optional[str]:

    try:
        value = st.secrets.get(name)

        if value:
            return str(value).strip()

    except Exception:
        pass

    return None


# ============================================================
# HTTP API-FOOTBALL
# ============================================================

API_FOOTBALL_URL = (
    "https://v3.football.api-sports.io"
)


def api_football_get(
    endpoint: str,
    params: Dict
):

    key = get_secret(
        "API_FOOTBALL_KEY"
    )

    if not key:

        return None, (
            "Falta API_FOOTBALL_KEY "
            "en Streamlit Secrets."
        )

    headers = {
        "x-apisports-key": key
    }

    try:

        response = requests.get(
            API_FOOTBALL_URL + endpoint,
            headers=headers,
            params=params,
            timeout=20,
        )

        if response.status_code != 200:

            return None, (
                f"API-Football HTTP "
                f"{response.status_code}"
            )

        data = response.json()

        errors = data.get(
            "errors",
            {}
        )

        if errors:

            return None, str(errors)

        return data, None

    except requests.RequestException as e:

        return None, str(e)


# ============================================================
# HTTP FOOTBALL-DATA
# ============================================================

FOOTBALL_DATA_URL = (
    "https://api.football-data.org/v4"
)


def football_data_get(
    endpoint: str,
    params: Optional[Dict] = None
):

    key = get_secret(
        "FOOTBALL_DATA_API_KEY"
    )

    if not key:

        return None, (
            "Falta FOOTBALL_DATA_API_KEY "
            "en Streamlit Secrets."
        )

    headers = {
        "X-Auth-Token": key
    }

    try:

        response = requests.get(
            FOOTBALL_DATA_URL + endpoint,
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

    except requests.RequestException as e:

        return None, str(e)


# ============================================================
# FECHAS
# ============================================================

def parse_api_date(value):

    if not value:
        return None

    try:

        dt = datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00"
            )
        )

        return dt

    except Exception:

        return None


def local_date_string(value):

    dt = parse_api_date(value)

    if not dt:
        return "Sin fecha"

    return dt.strftime(
        "%d/%m/%Y"
    )


def local_time_string(value):

    dt = parse_api_date(value)

    if not dt:
        return "—"

    return dt.strftime(
        "%H:%M"
    )


# ============================================================
# ROUNDS
# ============================================================

@st.cache_data(ttl=21600)
def get_rounds(
    league_id: int,
    season: int
):

    data, error = api_football_get(
        "/fixtures/rounds",
        {
            "league": league_id,
            "season": season,
        }
    )

    if error:
        return [], error

    rounds = data.get(
        "response",
        []
    )

    return rounds, None


# ============================================================
# FIXTURES POR JORNADA
# ============================================================

@st.cache_data(ttl=900)
def get_fixtures_by_round(
    league_id: int,
    season: int,
    round_name: str
):

    data, error = api_football_get(
        "/fixtures",
        {
            "league": league_id,
            "season": season,
            "round": round_name,
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
# FIXTURE IDs EN BLOQUE
# ============================================================

@st.cache_data(ttl=900)
def get_fixture_details(
    fixture_ids: Tuple[int, ...]
):

    if not fixture_ids:
        return []

    ids_string = "-".join(
        str(x)
        for x in fixture_ids
    )

    data, error = api_football_get(
        "/fixtures",
        {
            "ids": ids_string
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
# CUOTAS REALES
# ============================================================

@st.cache_data(ttl=300)
def get_fixture_odds(
    fixture_id: int
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
# ESTADÍSTICAS DE FIXTURE
# ============================================================

def extract_team_statistics(
    fixture: Dict
):

    result = {}

    statistics = fixture.get(
        "statistics",
        []
    )

    for team_block in statistics:

        team = team_block.get(
            "team",
            {}
        )

        team_id = team.get(
            "id"
        )

        if not team_id:
            continue

        stats = {}

        for item in team_block.get(
            "statistics",
            []
        ):

            name = item.get(
                "type"
            )

            value = item.get(
                "value"
            )

            stats[name] = value

        result[team_id] = stats

    return result


def clean_stat_value(value):

    if value is None:
        return None

    if isinstance(
        value,
        (int, float)
    ):
        return float(value)

    text = str(
        value
    ).strip()

    if text in [
        "",
        "-",
        "null",
        "None"
    ]:
        return None

    text = (
        text
        .replace("%", "")
        .replace(",", ".")
    )

    try:

        return float(text)

    except Exception:

        return None


# ============================================================
# EXTRAER ESTADÍSTICAS DEL PARTIDO
# ============================================================

def fixture_statistics(
    fixture: Dict
):

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

    home_id = home.get(
        "id"
    )

    away_id = away.get(
        "id"
    )

    stats = extract_team_statistics(
        fixture
    )

    home_stats = stats.get(
        home_id,
        {}
    )

    away_stats = stats.get(
        away_id,
        {}
    )

    def value(
        block,
        possible_names
    ):

        for name in possible_names:

            if name in block:

                return clean_stat_value(
                    block[name]
                )

        return None

    return {

        "home_corners":
        value(
            home_stats,
            [
                "Corner Kicks"
            ]
        ),

        "away_corners":
        value(
            away_stats,
            [
                "Corner Kicks"
            ]
        ),

        "home_shots":
        value(
            home_stats,
            [
                "Total Shots"
            ]
        ),

        "away_shots":
        value(
            away_stats,
            [
                "Total Shots"
            ]
        ),

        "home_sot":
        value(
            home_stats,
            [
                "Shots on Goal"
            ]
        ),

        "away_sot":
        value(
            away_stats,
            [
                "Shots on Goal"
            ]
        ),

        "home_yellow":
        value(
            home_stats,
            [
                "Yellow Cards"
            ]
        ),

        "away_yellow":
        value(
            away_stats,
            [
                "Yellow Cards"
            ]
        ),

        "home_red":
        value(
            home_stats,
            [
                "Red Cards"
            ]
        ),

        "away_red":
        value(
            away_stats,
            [
                "Red Cards"
            ]
        ),

        "home_saves":
        value(
            home_stats,
            [
                "Goalkeeper Saves"
            ]
        ),

        "away_saves":
        value(
            away_stats,
            [
                "Goalkeeper Saves"
            ]
        ),
    }


# ============================================================
# MODELOS
# ============================================================

def poisson_over(
    expected,
    line
):

    if expected is None:
        return None

    try:

        expected = float(
            expected
        )

        if expected <= 0:
            return None

        threshold = (
            math.floor(
                float(line)
            ) + 1
        )

        under = 0.0

        for k in range(
            threshold
        ):

            under += (
                math.exp(-expected)
                *
                expected ** k
                /
                math.factorial(k)
            )

        return max(
            0.001,
            min(
                .999,
                1 - under
            )
        )

    except Exception:

        return None


def fair_odds(probability):

    if (
        probability is None
        or probability <= 0
    ):
        return None

    return 1 / probability


def implied_probability(
    odds
):

    if (
        odds is None
        or pd.isna(odds)
        or odds <= 1
    ):
        return None

    return 1 / float(
        odds
    )


def calculate_ev(
    probability,
    odds
):

    if (
        probability is None
        or odds is None
        or pd.isna(odds)
        or odds <= 1
    ):
        return None

    return (
        probability * odds
    ) - 1


# ============================================================
# CONSTRUIR PRONÓSTICOS A PARTIR DE ESTADÍSTICAS REALES
# ============================================================

def build_match_predictions(
    fixture: Dict
):

    stats = fixture_statistics(
        fixture
    )

    home = fixture[
        "teams"
    ][
        "home"
    ]

    away = fixture[
        "teams"
    ][
        "away"
    ]

    home_name = home.get(
        "name",
        "Local"
    )

    away_name = away.get(
        "name",
        "Visitante"
    )

    predictions = []

    # --------------------------------------------------------
    # CÓRNERS
    # --------------------------------------------------------

    hc = stats[
        "home_corners"
    ]

    ac = stats[
        "away_corners"
    ]

    if (
        hc is not None
        and ac is not None
    ):

        total = hc + ac

        for line in [
            7.5,
            8.5,
            9.5,
            10.5,
            11.5
        ]:

            # Para un partido ya jugado no queremos usar
            # la estadística final como predictor del propio
            # partido. Por eso estas predicciones se utilizan
            # solamente para análisis de partidos finalizados.
            #
            # La V7 marcará estos datos como HISTÓRICOS.

            probability = poisson_over(
                total,
                line
            )

            predictions.append({

                "market":
                "📐 Córners",

                "selection":
                f"Más de {line}",

                "probability":
                probability,

                "source":
                "Estadística real del partido",

            })

    # --------------------------------------------------------
    # TIROS A PUERTA
    # --------------------------------------------------------

    hs = stats[
        "home_sot"
    ]

    ass = stats[
        "away_sot"
    ]

    if (
        hs is not None
        and ass is not None
    ):

        total_sot = hs + ass

        for line in [
            6.5,
            7.5,
            8.5,
            9.5,
            10.5
        ]:

            probability = poisson_over(
                total_sot,
                line
            )

            predictions.append({

                "market":
                "🎯 Tiros a puerta",

                "selection":
                f"Más de {line}",

                "probability":
                probability,

                "source":
                "Estadística real del partido",

            })

    # --------------------------------------------------------
    # TARJETAS
    # --------------------------------------------------------

    hy = stats[
        "home_yellow"
    ]

    ay = stats[
        "away_yellow"
    ]

    if (
        hy is not None
        and ay is not None
    ):

        total_cards = hy + ay

        for line in [
            2.5,
            3.5,
            4.5,
            5.5,
            6.5
        ]:

            probability = poisson_over(
                total_cards,
                line
            )

            predictions.append({

                "market":
                "🟨 Tarjetas",

                "selection":
                f"Más de {line}",

                "probability":
                probability,

                "source":
                "Estadística real del partido",

            })

    # --------------------------------------------------------
    # PARADAS
    # --------------------------------------------------------

    hsaves = stats[
        "home_saves"
    ]

    asaves = stats[
        "away_saves"
    ]

    if (
        hsaves is not None
        and asaves is not None
    ):

        total_saves = (
            hsaves + asaves
        )

        for line in [
            2.5,
            3.5,
            4.5,
            5.5,
            6.5
        ]:

            probability = poisson_over(
                total_saves,
                line
            )

            predictions.append({

                "market":
                "🧤 Paradas",

                "selection":
                f"Más de {line}",

                "probability":
                probability,

                "source":
                "Estadística real del partido",

            })

    return predictions


# ============================================================
# FOOTBALL-DATA: CLASIFICACIÓN
# ============================================================

@st.cache_data(ttl=1800)
def get_standings(
    competition_code: str
):

    data, error = football_data_get(
        f"/competitions/"
        f"{competition_code}/standings"
    )

    if error:
        return pd.DataFrame(), error

    rows = []

    standings = data.get(
        "standings",
        []
    )

    for table in standings:

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
# MAPEAR CUOTAS
# ============================================================

def normalise_text(
    text
):

    if text is None:
        return ""

    return (
        str(text)
        .lower()
        .strip()
    )


def extract_odds(
    fixture_odds
):

    rows = []

    for block in fixture_odds:

        bookmakers = block.get(
            "bookmakers",
            []
        )

        for bookmaker in bookmakers:

            bookmaker_name = (
                bookmaker.get(
                    "name",
                    ""
                )
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

                values = bet.get(
                    "values",
                    []
                )

                for value in values:

                    odd = value.get(
                        "odd"
                    )

                    if odd is None:
                        continue

                    try:
                        odd = float(
                            str(odd)
                            .replace(
                                ",",
                                "."
                            )
                        )
                    except Exception:
                        continue

                    if odd <= 1:
                        continue

                    rows.append({

                        "bookmaker":
                        bookmaker_name,

                        "market":
                        market_name,

                        "value":
                        value.get(
                            "value",
                            ""
                        ),

                        "odd":
                        odd,
                    })

    return rows


def find_market_odds(
    odds_rows,
    market,
    selection
):

    if not odds_rows:
        return None, None

    target_market = normalise_text(
        market
    )

    target_selection = normalise_text(
        selection
    )

    for row in odds_rows:

        current_market = (
            normalise_text(
                row["market"]
            )
        )

        current_value = (
            normalise_text(
                row["value"]
            )
        )

        if (
            target_market in current_market
            or
            current_market in target_market
        ):

            if (
                target_selection in
                current_value
            ):

                return (
                    row["odd"],
                    row["bookmaker"]
                )

    return None, None


# ============================================================
# CONSTRUIR FILAS DE PRONÓSTICOS
# ============================================================

def create_predictions_for_fixture(
    fixture
):

    fixture_id = fixture[
        "fixture"
    ].get(
        "id"
    )

    teams = fixture[
        "teams"
    ]

    home = teams[
        "home"
    ]

    away = teams[
        "away"
    ]

    predictions = (
        build_match_predictions(
            fixture
        )
    )

    if not predictions:
        return []

    odds_response, _ = (
        get_fixture_odds(
            fixture_id
        )
    )

    odds_rows = extract_odds(
        odds_response
    )

    output = []

    for prediction in predictions:

        probability = (
            prediction[
                "probability"
            ]
        )

        selection = (
            prediction[
                "selection"
            ]
        )

        market = (
            prediction[
                "market"
            ]
        )

        # Convertimos nombres de UI a nombres
        # que normalmente aparecen en las casas/API.

        if "Córners" in market:

            api_market = "Corners"

        elif "Tarjetas" in market:

            api_market = "Total Cards"

        elif "Tiros a puerta" in market:

            api_market = (
                "Shots on Goal"
            )

        elif "Paradas" in market:

            api_market = "Goalkeeper Saves"

        else:

            api_market = market

        odd, bookmaker = (
            find_market_odds(
                odds_rows,
                api_market,
                selection
            )
        )

        fair = fair_odds(
            probability
        )

        ev = calculate_ev(
            probability,
            odd
        )

        fixture_date = fixture[
            "fixture"
        ].get(
            "date"
        )

        round_name = fixture[
            "league"
        ].get(
            "round",
            "Jornada no indicada"
        )

        output.append({

            "fixture_id":
            fixture_id,

            "round":
            round_name,

            "date_raw":
            fixture_date,

            "date":
            local_date_string(
                fixture_date
            ),

            "time":
            local_time_string(
                fixture_date
            ),

            "home":
            home.get(
                "name"
            ),

            "away":
            away.get(
                "name"
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

            "market":
            market,

            "selection":
            selection,

            "probability":
            probability,

            "fair_odds":
            fair,

            "odds":
            odd,

            "ev":
            ev,

            "bookmaker":
            bookmaker,

            "source":
            prediction[
                "source"
            ],

        })

    return output


# ============================================================
# FUNCIÓN PARA NORMALIZAR JORNADAS
# ============================================================

def round_sort_key(
    round_name
):

    if not round_name:
        return 9999

    match = re.search(
        r"(\d+)",
        str(round_name)
    )

    if match:

        return int(
            match.group(1)
        )

    return 9999


# ============================================================
# CARGAR JORNADA ACTUAL
# ============================================================

@st.cache_data(ttl=900)
def load_round_fixtures(
    league_id,
    season,
    round_name
):

    fixtures, error = (
        get_fixtures_by_round(
            league_id,
            season,
            round_name
        )
    )

    if error:
        return pd.DataFrame(), error

    rows = []

    for fixture in fixtures:

        fixture_info = fixture.get(
            "fixture",
            {}
        )

        teams = fixture.get(
            "teams",
            {}
        )

        league = fixture.get(
            "league",
            {}
        )

        rows.append({

            "fixture_id":
            fixture_info.get(
                "id"
            ),

            "date_raw":
            fixture_info.get(
                "date"
            ),

            "date":
            local_date_string(
                fixture_info.get(
                    "date"
                )
            ),

            "time":
            local_time_string(
                fixture_info.get(
                    "date"
                )
            ),

            "home":
            teams.get(
                "home",
                {}
            ).get(
                "name"
            ),

            "away":
            teams.get(
                "away",
                {}
            ).get(
                "name"
            ),

            "home_logo":
            teams.get(
                "home",
                {}
            ).get(
                "logo",
                ""
            ),

            "away_logo":
            teams.get(
                "away",
                {}
            ).get(
                "logo",
                ""
            ),

            "status":
            fixture_info.get(
                "status",
                {}
            ).get(
                "short"
            ),

            "round":
            league.get(
                "round",
                round_name
            ),
        })

    return (
        pd.DataFrame(
            rows
        ).sort_values(
            [
                "date_raw",
                "time"
            ]
        ),
        None
    )


# ============================================================
# RENDER PARTIDO
# ============================================================

def render_match(
    row,
    fixture_details=None
):

    home_logo = ""

    away_logo = ""

    if row.get(
        "home_logo"
    ):

        home_logo = (
            f'<img src="{row["home_logo"]}" '
            f'width="22" '
            f'style="vertical-align:middle;'
            f'margin-right:6px;">'
        )

    if row.get(
        "away_logo"
    ):

        away_logo = (
            f'<img src="{row["away_logo"]}" '
            f'width="22" '
            f'style="vertical-align:middle;'
            f'margin-right:6px;">'
        )

    st.markdown(
        f"""
        <div class="match-card">

            <div class="match-date">
                📅 {row["date"]}
                &nbsp;&nbsp;
                ⏰ {row["time"]}
            </div>

            <div style="
                margin-top:8px;
                display:flex;
                justify-content:space-between;
                align-items:center;
            ">

                <div class="team-line">
                    {home_logo}
                    {row["home"]}
                </div>

                <div style="
                    opacity:.4;
                    font-weight:800;
                ">
                    VS
                </div>

                <div class="team-line">
                    {away_logo}
                    {row["away"]}
                </div>

            </div>

        </div>
        """,
        unsafe_allow_html=True
    )


# ============================================================
# RENDER PRONÓSTICO
# ============================================================

def render_prediction(
    row
):

    probability = (
        row["probability"]
        * 100
    )

    fair = row[
        "fair_odds"
    ]

    odds = row[
        "odds"
    ]

    ev = row[
        "ev"
    ]

    if odds is None:

        odds_text = "—"

        badge = (
            '<span class="no-odds-badge">'
            'SIN CUOTA REAL'
            '</span>'
        )

        ev_text = "—"

    else:

        odds_text = (
            f"{odds:.2f}"
        )

        if ev is not None:

            ev_text = (
                f"{ev * 100:+.1f}%"
            )

            if ev > 0:

                badge = (
                    '<span class="value-badge">'
                    '🔥 VALUE'
                    '</span>'
                )

            else:

                badge = (
                    '<span class="no-value-badge">'
                    'SIN VALUE'
                    '</span>'
                )

        else:

            ev_text = "—"

            badge = (
                '<span class="no-value-badge">'
                'PRONÓSTICO'
                '</span>'
            )

    fair_text = (
        f"{fair:.2f}"
        if fair is not None
        else "—"
    )

    bookmaker = (
        row.get(
            "bookmaker"
        )
        or ""
    )

    bookmaker_text = ""

    if bookmaker:

        bookmaker_text = (
            f'<div class="info-line">'
            f'Cuota de: {bookmaker}'
            f'</div>'
        )

    st.markdown(
        f"""
        <div class="market-card">

            <div style="
                display:flex;
                justify-content:space-between;
                align-items:center;
                margin-bottom:8px;
            ">

                <div class="market-title">
                    {row["market"]}
                    · {row["selection"]}
                </div>

                <div>
                    {badge}
                </div>

            </div>

            <div style="
                display:grid;
                grid-template-columns:
                repeat(4,1fr);
                gap:6px;
            ">

                <div class="metric">

                    <div class="metric-label">
                        PROBABILIDAD
                    </div>

                    <div class="metric-value">
                        {probability:.1f}%
                    </div>

                </div>

                <div class="metric">

                    <div class="metric-label">
                        CUOTA REAL
                    </div>

                    <div class="metric-value">
                        {odds_text}
                    </div>

                </div>

                <div class="metric">

                    <div class="metric-label">
                        CUOTA JUSTA
                    </div>

                    <div class="metric-value">
                        {fair_text}
                    </div>

                </div>

                <div class="metric">

                    <div class="metric-label">
                        EV
                    </div>

                    <div class="metric-value">
                        {ev_text}
                    </div>

                </div>

            </div>

            <div style="margin-top:6px;">
                {bookmaker_text}
            </div>

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

    st.markdown(
        '<div class="main-title">'
        '⚽ ValueBet Pro V7'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Datos reales · Pronósticos · Value'
        '</div>',
        unsafe_allow_html=True
    )

    # --------------------------------------------------------
    # CONFIGURACIÓN
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

        season = st.selectbox(
            "Temporada disponible",
            [2024, 2023, 2022],
            index=0
        )

        st.divider()

        min_probability = st.slider(
            "Probabilidad mínima (%)",
            40,
            90,
            50,
            1
        )

        min_ev = st.slider(
            "EV mínimo (%)",
            -20,
            50,
            0,
            1
        )

        st.divider()

        st.caption(
            "Las cuotas solo se consideran "
            "Value cuando existe una cuota "
            "real devuelta por la API."
        )

    competition = COMPETITIONS[
        competition_name
    ]

    league_id = competition[
        "api_football"
    ]

    football_data_code = (
        competition[
            "football_data"
        ]
    )

    # --------------------------------------------------------
    # CARGA JORNADAS
    # --------------------------------------------------------

    rounds, round_error = get_rounds(
        league_id,
        season
    )

    if round_error:

        st.error(
            f"Error obteniendo jornadas: "
            f"{round_error}"
        )

        return

    if not rounds:

        st.warning(
            "API-Football no ha devuelto "
            "jornadas para esta competición "
            "y temporada."
        )

        return

    rounds = sorted(
        rounds,
        key=round_sort_key
    )

    # --------------------------------------------------------
    # TABS
    # --------------------------------------------------------

    (
        tab_predictions,
        tab_matches,
        tab_table
    ) = st.tabs(
        [
            "🔮 Pronósticos",
            "📅 Partidos",
            "🏆 Clasificación"
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
            "Aquí aparecen estimaciones basadas "
            "únicamente en datos disponibles. "
            "Sin cuota real no se calcula Value."
        )

        selected_round = st.selectbox(
            "Jornada",
            rounds,
            key="prediction_round"
        )

        fixtures, error = (
            get_fixtures_by_round(
                league_id,
                season,
                selected_round
            )
        )

        if error:

            st.error(
                error
            )

        elif not fixtures:

            st.info(
                "No hay partidos devueltos "
                "por API-Football para esta jornada."
            )

        else:

            # Solo procesamos los partidos
            # de la jornada seleccionada.
            #
            # Se consulta fixture por fixture
            # para mantener controlado el consumo.

            prediction_rows = []

            for fixture in fixtures:

                status = fixture[
                    "fixture"
                ].get(
                    "status",
                    {}
                ).get(
                    "short"
                )

                # Los partidos futuros no tienen
                # estadísticas del propio partido.
                #
                # Por tanto, no fabricamos pronósticos
                # con datos inexistentes.
                #
                # En V7.1 añadiremos el histórico
                # de partidos anteriores por equipo.

                if status not in [
                    "NS",
                    "TBD",
                    "PST"
                ]:

                    rows = (
                        create_predictions_for_fixture(
                            fixture
                        )
                    )

                    prediction_rows.extend(
                        rows
                    )

            if not prediction_rows:

                st.info(
                    "Todavía no hay suficientes "
                    "estadísticas reales disponibles "
                    "para generar pronósticos de "
                    "esta jornada."
                )

            else:

                predictions_df = pd.DataFrame(
                    prediction_rows
                )

                predictions_df = (
                    predictions_df[
                        predictions_df[
                            "probability"
                        ]
                        >=
                        (
                            min_probability
                            / 100
                        )
                    ]
                    .copy()
                )

                if predictions_df.empty:

                    st.info(
                        "No hay pronósticos que "
                        "superen la probabilidad "
                        "mínima seleccionada."
                    )

                else:

                    # Primero Value real

                    predictions_df[
                        "ev_sort"
                    ] = predictions_df[
                        "ev"
                    ].fillna(
                        -999
                    )

                    predictions_df = (
                        predictions_df
                        .sort_values(
                            [
                                "ev_sort",
                                "probability"
                            ],
                            ascending=False
                        )
                    )

                    for _, row in (
                        predictions_df
                        .head(50)
                        .iterrows()
                    ):

                        st.markdown(
                            f"### "
                            f"{row['date']} · "
                            f"{row['time']} · "
                            f"{row['home']} vs "
                            f"{row['away']}"
                        )

                        render_prediction(
                            row
                        )

    # ========================================================
    # PARTIDOS
    # ========================================================

    with tab_matches:

        st.markdown(
            '<div class="section-title">'
            '📅 Partidos por jornada'
            '</div>',
            unsafe_allow_html=True
        )

        st.caption(
            "Fecha, hora y equipos procedentes "
            "directamente de API-Football."
        )

        # Elegimos si mostrar todas las jornadas
        # o una concreta para no sobrecargar móvil.

        round_to_show = st.selectbox(
            "Seleccionar jornada",
            rounds,
            key="matches_round"
        )

        fixtures_df, error = (
            load_round_fixtures(
                league_id,
                season,
                round_to_show
            )
        )

        if error:

            st.error(
                error
            )

        elif fixtures_df.empty:

            st.info(
                "No hay partidos para esta jornada."
            )

        else:

            st.markdown(
                f"""
                <div class="round-card">
                    <b>{round_to_show}</b>
                    <div class="info-line">
                        {len(fixtures_df)}
                        partidos encontrados
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            for _, row in (
                fixtures_df.iterrows()
            ):

                render_match(
                    row
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

        standings, error = (
            get_standings(
                football_data_code
            )
        )

        if error:

            st.error(
                error
            )

        elif standings.empty:

            st.info(
                "No hay clasificación "
                "disponible en football-data.org."
            )

        else:

            st.dataframe(
                standings,
                hide_index=True,
                use_container_width=True
            )

    # ========================================================
    # FOOTER
    # ========================================================

    st.divider()

    st.caption(
        "ValueBet Football Pro V7 · "
        "Datos de API-Football + football-data.org"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
