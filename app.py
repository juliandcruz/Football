import streamlit as st
import pandas as pd
import numpy as np
import requests
import math
import re
from datetime import datetime, timezone, date, timedelta
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
# HISTÓRICO MÁXIMO DE 2 AÑOS
# ============================================================

HISTORICAL_YEARS = 2


def historical_date_window(reference_date=None):
    """
    Devuelve la ventana histórica permitida:
    desde un máximo de 2 años antes hasta la fecha de referencia.
    """
    if reference_date is None:
        reference_date = date.today()

    end_date = reference_date
    start_date = end_date - timedelta(days=365 * HISTORICAL_YEARS)
    return start_date, end_date


@st.cache_data(ttl=21600)
def get_team_historical_fixtures(
    team_id: int,
    league_id: int,
    season: int,
    reference_date: date
):
    """
    Obtiene partidos históricos del equipo y limita los datos a
    los 2 años anteriores a reference_date.

    El filtro de fechas se hace también localmente para garantizar
    que nunca entren partidos anteriores a la ventana permitida.
    """
    start_date, end_date = historical_date_window(reference_date)

    data, error = api_football_get(
        "/fixtures",
        {
            "team": team_id,
            "league": league_id,
            "season": season,
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "status": "FT"
        }
    )

    if error:
        return [], error

    fixtures = data.get("response", [])

    filtered = []

    for fixture in fixtures:
        fixture_date_raw = fixture.get("fixture", {}).get("date")
        fixture_date = parse_api_date(fixture_date_raw)

        if not fixture_date:
            continue

        fixture_day = fixture_date.date()

        if start_date <= fixture_day <= end_date:
            filtered.append(fixture)

    return filtered, None


def fixture_result_for_team(fixture, team_id):
    """
    Extrae estadísticas/resultados de un partido desde la perspectiva
    del equipo indicado.
    """
    teams = fixture.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})
    goals = fixture.get("goals", {})

    is_home = home.get("id") == team_id
    is_away = away.get("id") == team_id

    if not (is_home or is_away):
        return None

    if is_home:
        team_goals = goals.get("home")
        opponent_goals = goals.get("away")
        team_stats = "home"
        opponent_stats = "away"
    else:
        team_goals = goals.get("away")
        opponent_goals = goals.get("home")
        team_stats = "away"
        opponent_stats = "home"

    if team_goals is None or opponent_goals is None:
        return None

    return {
        "team_goals": team_goals,
        "opponent_goals": opponent_goals,
        "is_home": is_home,
        "team_stats": team_stats,
        "opponent_stats": opponent_stats,
        "date": fixture.get("fixture", {}).get("date")
    }


def historical_average(values):
    """Media segura de una lista de valores numéricos."""
    clean = [float(v) for v in values if v is not None]

    if not clean:
        return None

    return sum(clean) / len(clean)


def build_pre_match_team_profile(
    team_id: int,
    league_id: int,
    seasons: List[int],
    reference_date: date
):
    """
    Construye un perfil prepartido usando exclusivamente partidos
    comprendidos dentro de los 2 años anteriores a reference_date.

    Importante:
    este perfil NO utiliza las estadísticas del partido que se quiere
    pronosticar.
    """
    all_fixtures = []

    for season in seasons:
        fixtures, error = get_team_historical_fixtures(
            team_id,
            league_id,
            season,
            reference_date
        )

        if error:
            continue

        all_fixtures.extend(fixtures)

    # Deducción de duplicados por ID de fixture
    unique = {}
    for fixture in all_fixtures:
        fixture_id = fixture.get("fixture", {}).get("id")
        if fixture_id:
            unique[fixture_id] = fixture

    fixtures = list(unique.values())

    # Orden más reciente primero
    fixtures.sort(
        key=lambda f: f.get("fixture", {}).get("date") or "",
        reverse=True
    )

    profile = {
        "matches": len(fixtures),
        "goals_for": [],
        "goals_against": [],
        "home_goals_for": [],
        "home_goals_against": [],
        "away_goals_for": [],
        "away_goals_against": []
    }

    for fixture in fixtures:
        result = fixture_result_for_team(fixture, team_id)

        if not result:
            continue

        gf = result["team_goals"]
        ga = result["opponent_goals"]

        profile["goals_for"].append(gf)
        profile["goals_against"].append(ga)

        if result["is_home"]:
            profile["home_goals_for"].append(gf)
            profile["home_goals_against"].append(ga)
        else:
            profile["away_goals_for"].append(gf)
            profile["away_goals_against"].append(ga)

    return {
        "matches": len(profile["goals_for"]),
        "goals_for_avg": historical_average(profile["goals_for"]),
        "goals_against_avg": historical_average(profile["goals_against"]),
        "home_goals_for_avg": historical_average(profile["home_goals_for"]),
        "home_goals_against_avg": historical_average(profile["home_goals_against"]),
        "away_goals_for_avg": historical_average(profile["away_goals_for"]),
        "away_goals_against_avg": historical_average(profile["away_goals_against"]),
        "window_start": historical_date_window(reference_date)[0],
        "window_end": historical_date_window(reference_date)[1]
    }


def build_pre_match_goal_expectancy(
    home_profile,
    away_profile
):
    """
    Estima goles esperados combinando ataque y defensa históricos
    de ambos equipos.
    """
    if not home_profile or not away_profile:
        return None, None

    home_attack = home_profile.get("home_goals_for_avg")
    home_defence = home_profile.get("home_goals_against_avg")
    away_attack = away_profile.get("away_goals_for_avg")
    away_defence = away_profile.get("away_goals_against_avg")

    if any(
        x is None
        for x in [
            home_attack,
            home_defence,
            away_attack,
            away_defence
        ]
    ):
        return None, None

    expected_home = (
        home_attack + away_defence
    ) / 2

    expected_away = (
        away_attack + home_defence
    ) / 2

    return expected_home, expected_away




# ============================================================
# ESTADÍSTICAS HISTÓRICAS PARA MERCADOS
# ============================================================

@st.cache_data(ttl=21600)
def get_historical_fixture_statistics(
    fixture_id: int
):
    """
    Obtiene las estadísticas reales de un partido histórico.
    Se utiliza únicamente para construir el perfil previo de los
    equipos, nunca para predecir el propio partido.
    """
    data, error = api_football_get(
        "/fixtures",
        {
            "id": fixture_id
        }
    )

    if error:
        return None, error

    fixtures = data.get("response", [])

    if not fixtures:
        return None, None

    return fixtures[0], None


def add_market_stats_to_team_profile(
    profile,
    fixture,
    team_id
):
    """
    Añade al perfil las estadísticas del partido desde la perspectiva
    del equipo: córners, tiros a puerta, tarjetas y paradas.
    """
    stats = fixture_statistics(fixture)

    teams = fixture.get("teams", {})
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")

    if team_id == home_id:
        prefix = "home"
        opponent_prefix = "away"
    elif team_id == away_id:
        prefix = "away"
        opponent_prefix = "home"
    else:
        return

    mappings = {
        "corners_for": f"{prefix}_corners",
        "corners_against": f"{opponent_prefix}_corners",
        "shots_for": f"{prefix}_shots",
        "shots_against": f"{opponent_prefix}_shots",
        "sot_for": f"{prefix}_sot",
        "sot_against": f"{opponent_prefix}_sot",
        "yellow_for": f"{prefix}_yellow",
        "yellow_against": f"{opponent_prefix}_yellow",
        "red_for": f"{prefix}_red",
        "red_against": f"{opponent_prefix}_red",
        "saves_for": f"{prefix}_saves",
        "saves_against": f"{opponent_prefix}_saves",
    }

    for profile_key, stat_key in mappings.items():
        value = stats.get(stat_key)
        if value is not None:
            profile.setdefault(profile_key, []).append(value)


def finalize_market_profile(profile):
    """
    Convierte las listas históricas en medias.
    """
    result = dict(profile)

    market_keys = [
        "corners_for",
        "corners_against",
        "shots_for",
        "shots_against",
        "sot_for",
        "sot_against",
        "yellow_for",
        "yellow_against",
        "red_for",
        "red_against",
        "saves_for",
        "saves_against",
    ]

    for key in market_keys:
        values = profile.get(key, [])
        result[f"{key}_avg"] = historical_average(values)

    return result


def build_complete_pre_match_team_profile(
    team_id: int,
    league_id: int,
    seasons: List[int],
    reference_date: date
):
    """
    Perfil completo de un equipo usando exclusivamente partidos de
    los 2 años anteriores al partido objetivo.

    Incluye:
    - goles
    - córners
    - tiros
    - tiros a puerta
    - tarjetas
    - paradas
    """
    all_fixtures = []

    start_date, end_date = historical_date_window(reference_date)

    for season in seasons:
        fixtures, error = get_team_historical_fixtures(
            team_id,
            league_id,
            season,
            reference_date
        )

        if not error:
            all_fixtures.extend(fixtures)

    unique = {}
    for fixture in all_fixtures:
        fixture_id = fixture.get("fixture", {}).get("id")
        if fixture_id:
            unique[fixture_id] = fixture

    fixtures = list(unique.values())

    # Solo partidos estrictamente anteriores al partido objetivo.
    fixtures = [
        f for f in fixtures
        if (
            parse_api_date(
                f.get("fixture", {}).get("date")
            ) is not None
            and
            parse_api_date(
                f.get("fixture", {}).get("date")
            ).date() < reference_date
        )
    ]

    fixtures.sort(
        key=lambda f: f.get("fixture", {}).get("date") or "",
        reverse=True
    )

    profile = {
        "matches": 0,
        "goals_for": [],
        "goals_against": [],
        "home_goals_for": [],
        "home_goals_against": [],
        "away_goals_for": [],
        "away_goals_against": [],

        "corners_for": [],
        "corners_against": [],
        "shots_for": [],
        "shots_against": [],
        "sot_for": [],
        "sot_against": [],
        "yellow_for": [],
        "yellow_against": [],
        "red_for": [],
        "red_against": [],
        "saves_for": [],
        "saves_against": [],
    }

    # Limitamos el histórico utilizado a los últimos 20 partidos
    # disponibles dentro de la ventana de 2 años.
    fixtures = fixtures[:20]

    for fixture in fixtures:
        result = fixture_result_for_team(
            fixture,
            team_id
        )

        if not result:
            continue

        gf = result["team_goals"]
        ga = result["opponent_goals"]

        profile["goals_for"].append(gf)
        profile["goals_against"].append(ga)

        if result["is_home"]:
            profile["home_goals_for"].append(gf)
            profile["home_goals_against"].append(ga)
        else:
            profile["away_goals_for"].append(gf)
            profile["away_goals_against"].append(ga)

        fixture_id = fixture.get("fixture", {}).get("id")

        if fixture_id:
            detail, error = get_historical_fixture_statistics(
                fixture_id
            )

            if detail and not error:
                add_market_stats_to_team_profile(
                    profile,
                    detail,
                    team_id
                )

    result = {
        "matches": len(profile["goals_for"]),
        "goals_for_avg": historical_average(profile["goals_for"]),
        "goals_against_avg": historical_average(profile["goals_against"]),
        "home_goals_for_avg": historical_average(profile["home_goals_for"]),
        "home_goals_against_avg": historical_average(profile["home_goals_against"]),
        "away_goals_for_avg": historical_average(profile["away_goals_for"]),
        "away_goals_against_avg": historical_average(profile["away_goals_against"]),
        "window_start": start_date,
        "window_end": end_date,
    }

    result.update(finalize_market_profile(profile))

    return result


def expected_from_profiles(
    home_profile,
    away_profile,
    home_for_key,
    home_against_key,
    away_for_key,
    away_against_key
):
    """
    Combina ataque/ofensiva y concesión defensiva de ambos equipos.
    """
    values = [
        home_profile.get(home_for_key),
        home_profile.get(home_against_key),
        away_profile.get(away_for_key),
        away_profile.get(away_against_key),
    ]

    if any(v is None for v in values):
        return None

    home_expected = (
        home_profile[home_for_key] +
        away_profile[away_against_key]
    ) / 2

    away_expected = (
        away_profile[away_for_key] +
        home_profile[home_against_key]
    ) / 2

    return home_expected, away_expected


def build_market_predictions(
    home_profile,
    away_profile
):
    """
    Genera probabilidades prepartido para:
    - córners
    - tiros a puerta
    - tarjetas
    - paradas
    """
    predictions = []

    # --------------------------------------------------------
    # CÓRNERS
    # --------------------------------------------------------
    corners = expected_from_profiles(
        home_profile,
        away_profile,
        "corners_for_avg",
        "corners_against_avg",
        "corners_for_avg",
        "corners_against_avg"
    )

    if corners:
        expected_total = sum(corners)

        for line in [7.5, 8.5, 9.5, 10.5, 11.5]:
            probability = poisson_over(
                expected_total,
                line
            )

            predictions.append({
                "market": "📐 Córners",
                "selection": f"Más de {line}",
                "probability": probability,
                "source": "Histórico máximo 2 años · últimos 20 partidos"
            })

    # --------------------------------------------------------
    # TIROS A PUERTA
    # --------------------------------------------------------
    sot = expected_from_profiles(
        home_profile,
        away_profile,
        "sot_for_avg",
        "sot_against_avg",
        "sot_for_avg",
        "sot_against_avg"
    )

    if sot:
        expected_total = sum(sot)

        for line in [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]:
            probability = poisson_over(
                expected_total,
                line
            )

            predictions.append({
                "market": "🎯 Tiros a puerta",
                "selection": f"Más de {line}",
                "probability": probability,
                "source": "Histórico máximo 2 años · últimos 20 partidos"
            })

    # --------------------------------------------------------
    # TARJETAS
    # --------------------------------------------------------
    cards = expected_from_profiles(
        home_profile,
        away_profile,
        "yellow_for_avg",
        "yellow_against_avg",
        "yellow_for_avg",
        "yellow_against_avg"
    )

    if cards:
        expected_total = sum(cards)

        for line in [2.5, 3.5, 4.5, 5.5, 6.5]:
            probability = poisson_over(
                expected_total,
                line
            )

            predictions.append({
                "market": "🟨 Tarjetas",
                "selection": f"Más de {line}",
                "probability": probability,
                "source": "Histórico máximo 2 años · últimos 20 partidos"
            })

    # --------------------------------------------------------
    # PARADAS
    # --------------------------------------------------------
    saves = expected_from_profiles(
        home_profile,
        away_profile,
        "saves_for_avg",
        "saves_against_avg",
        "saves_for_avg",
        "saves_against_avg"
    )

    if saves:
        expected_total = sum(saves)

        for line in [2.5, 3.5, 4.5, 5.5, 6.5]:
            probability = poisson_over(
                expected_total,
                line
            )

            predictions.append({
                "market": "🧤 Paradas",
                "selection": f"Más de {line}",
                "probability": probability,
                "source": "Histórico máximo 2 años · últimos 20 partidos"
            })

    return predictions



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
    fixture: Dict,
    league_id: int,
    historical_seasons: List[int]
):
    """
    Genera predicciones PRE-PARTIDO usando exclusivamente el histórico
    permitido de los 2 años anteriores al encuentro.
    """
    teams = fixture.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})

    home_id = home.get("id")
    away_id = away.get("id")

    fixture_date_raw = fixture.get("fixture", {}).get("date")
    fixture_dt = parse_api_date(fixture_date_raw)

    if not home_id or not away_id or not fixture_dt:
        return []

    reference_date = fixture_dt.date()

    home_profile = build_complete_pre_match_team_profile(
        home_id,
        league_id,
        historical_seasons,
        reference_date
    )

    away_profile = build_complete_pre_match_team_profile(
        away_id,
        league_id,
        historical_seasons,
        reference_date
    )

    predictions = []

    # Goles
    expected_home, expected_away = build_pre_match_goal_expectancy(
        home_profile,
        away_profile
    )

    if expected_home is not None and expected_away is not None:
        expected_goals = expected_home + expected_away

        for line in [0.5, 1.5, 2.5, 3.5, 4.5]:
            predictions.append({
                "market": "⚽ Goles",
                "selection": f"Más de {line}",
                "probability": poisson_over(
                    expected_goals,
                    line
                ),
                "source": "Histórico máximo 2 años · últimos 20 partidos"
            })

    # Mercados solicitados
    predictions.extend(
        build_market_predictions(
            home_profile,
            away_profile
        )
    )

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
    fixture,
    league_id,
    historical_seasons
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
            fixture,
            league_id,
            historical_seasons
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

        current_year = date.today().year
        season_options = list(range(current_year, current_year - 5, -1))

        season = st.selectbox(
            "Temporada disponible",
            season_options,
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

    # Solo se permiten datos de los 2 años anteriores.
    # Se solicitan las temporadas necesarias para cubrir esa ventana.
    current_season = season
    historical_seasons = [
        current_season,
        current_season - 1,
        current_season - 2
    ]

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
                            fixture,
                            league_id,
                            historical_seasons
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
