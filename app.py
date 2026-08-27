import streamlit as st
import streamlit.components.v1 as components
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
    page_title="ValueBet Pro V8",
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
# CONTADOR DE PETICIONES API (clave en plan gratuito)
# ============================================================
#
# API-Football free tier: 100 peticiones/día.
# Este contador solo cuenta llamadas HTTP reales (no las que
# vienen de la caché de st.cache_data), para que el usuario
# sepa exactamente cuánta cuota ha gastado en la sesión.

def register_api_call(api_name: str):
    if "api_call_count" not in st.session_state:
        st.session_state["api_call_count"] = {}
    counts = st.session_state["api_call_count"]
    counts[api_name] = counts.get(api_name, 0) + 1


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

        register_api_call("API-Football")

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

        register_api_call("football-data.org")

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


@st.cache_data(ttl=300)
def _season_for_date(target_date: date) -> int:
    """
    Devuelve la temporada futbolística correspondiente a una fecha.
    Temporadas europeas: ago-dic = año actual, ene-jul = año anterior.
    """
    if target_date.month >= 8:
        season = target_date.year
    else:
        season = target_date.year - 1
    return season


@st.cache_data(ttl=900)
def get_today_fixtures(
    league_id: int,
    target_date: date,
):
    """
    Obtiene los partidos de una fecha concreta para una liga.

    Estrategia 1: league + from/to (sin season).
    Estrategia 2: league + season=2024 + from/to.
    """
    date_str = target_date.isoformat()

    # Estrategia 1: solo league + from/to (sin season)
    data, error = api_football_get(
        "/fixtures",
        {
            "league": league_id,
            "from": date_str,
            "to": date_str,
        }
    )

    if not error:
        return data.get("response", []), None

    # Estrategia 2: con season=2024 + from/to
    for season in [2024, 2023, 2022]:
        data2, error2 = api_football_get(
            "/fixtures",
            {
                "league": league_id,
                "season": season,
                "from": date_str,
                "to": date_str,
            }
        )
        if not error2:
            return data2.get("response", []), None

    # Si nada funciona, devolver el error original
    return [], error


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
    Obtiene partidos históricos FINISHED del equipo en una
    temporada dada de la liga indicada.

    NO envía from/to para evitar errores de la API cuando
    el rango de fechas no coincide con la temporada.
    El filtro temporal se aplica localmente después.
    """
    data, error = api_football_get(
        "/fixtures",
        {
            "team": team_id,
            "league": league_id,
            "season": season,
        }
    )

    if error:
        return [], error

    fixtures = data.get("response", [])

    # Filtrado local: solo FT y dentro de la ventana de 2 años
    start_date, end_date = historical_date_window(reference_date)
    filtered = []

    for fixture in fixtures:
        status = fixture.get("fixture", {}).get("status", {}).get("short", "")
        if status != "FT":
            continue

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

    Usa la media local/visitante cuando hay al menos
    MIN_MATCHES_FOR_VENUE_SPLIT partidos en ese split; si no, cae a
    la media global del equipo (goals_for_avg / goals_against_avg)
    en vez de descartar el pronóstico por completo, lo cual era
    frecuente con el histórico limitado del plan gratuito.
    """
    if not home_profile or not away_profile:
        return None, None

    def pick(profile, venue_key, overall_key, raw_venue_key):
        raw_values = profile.get(raw_venue_key, [])
        if (
            len(raw_values) >= MIN_MATCHES_FOR_VENUE_SPLIT
            and profile.get(venue_key) is not None
        ):
            return profile.get(venue_key)
        return profile.get(overall_key)

    home_attack = pick(
        home_profile, "home_goals_for_avg",
        "goals_for_avg", "home_goals_for"
    )
    home_defence = pick(
        home_profile, "home_goals_against_avg",
        "goals_against_avg", "home_goals_against"
    )
    away_attack = pick(
        away_profile, "away_goals_for_avg",
        "goals_for_avg", "away_goals_for"
    )
    away_defence = pick(
        away_profile, "away_goals_against_avg",
        "goals_against_avg", "away_goals_against"
    )

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
    Obtiene las estadísticas reales de UN partido histórico.
    Se mantiene por compatibilidad, pero para varios partidos a la
    vez usar get_historical_fixture_statistics_batch, que agrupa
    hasta 20 IDs en una sola petición HTTP (crítico en plan
    gratuito, 100 peticiones/día).
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


@st.cache_data(ttl=21600)
def get_historical_fixture_statistics_batch(
    fixture_ids: Tuple[int, ...]
):
    """
    Obtiene datos básicos de varios partidos históricos en el menor
    número posible de peticiones HTTP, agrupando hasta 20 IDs por
    llamada (límite del endpoint /fixtures?ids=... de API-Football).

    NOTA: este endpoint devuelve equipos, goles y marcador, pero
    NO las estadísticas de mercados (córners, tiros, tarjetas,
    paradas). Para esas se usa get_fixture_statistics_single.
    """

    if not fixture_ids:
        return {}, None

    result_by_id = {}
    error_out = None

    ids_list = list(fixture_ids)

    for i in range(0, len(ids_list), 20):

        chunk = ids_list[i:i + 20]

        ids_string = "-".join(str(x) for x in chunk)

        data, error = api_football_get(
            "/fixtures",
            {
                "ids": ids_string
            }
        )

        if error:
            error_out = error
            continue

        for fixture in data.get("response", []):

            fixture_id = fixture.get(
                "fixture", {}
            ).get("id")

            if fixture_id:
                result_by_id[fixture_id] = fixture

    return result_by_id, error_out


@st.cache_data(ttl=21600)
def get_fixture_statistics_single(
    fixture_id: int
):
    """
    Obtiene las estadísticas reales de UN partido desde el
    endpoint /fixtures/statistics?fixture={id}.

    Este endpoint sí devuelve: Corner Kicks, Total Shots, Shots
    on Goal, Yellow Cards, Red Cards, Goalkeeper Saves, etc.

    Se cachea individualmente (ttl 6h) para que, si se vuelven a
    pedir las mismas jornadas o equipos en la sesión, no se
    repitan las peticiones.
    """
    data, error = api_football_get(
        "/fixtures/statistics",
        {
            "fixture": fixture_id
        }
    )

    if error:
        return None, error

    response = data.get("response", [])

    if not response:
        return None, None

    # Devuelve el array tal cual; add_market_stats_to_team_profile
    # lo procesa con extract_team_statistics.
    return response, None


MARKET_STAT_NAMES = [
    "corners",
    "shots",
    "sot",
    "yellow",
    "red",
    "saves",
]


def add_market_stats_to_team_profile(
    profile,
    fixture,
    team_id,
    stats_response=None
):
    """
    Añade al perfil las estadísticas del partido desde la perspectiva
    del equipo: córners, tiros, tiros a puerta, tarjetas y paradas.

    Además de la lista global (*_for / *_against), guarda también
    la versión separada por local/visitante (home_*_for, away_*_for,
    ...), igual que ya se hacía con los goles. Esto importa porque
    un equipo suele generar más córners/tiros jugando en casa, y
    antes esa señal se perdía al mezclarlo todo en una sola media.

    stats_response: array de bloques por equipo proveniente del
    endpoint /fixtures/statistics. Si se proporciona, se usa en
    lugar de buscar "statistics" dentro del fixture (que nunca
    está presente en el endpoint /fixtures).
    """
    # Determinar local/visitante desde el fixture básico
    # (el endpoint /fixtures/statistics no incluye esa info).
    teams = fixture.get("teams", {})
    home_id = teams.get("home", {}).get("id")
    away_id = teams.get("away", {}).get("id")

    if team_id == home_id:
        prefix = "home"
        opponent_prefix = "away"
        venue = "home"
    elif team_id == away_id:
        prefix = "away"
        opponent_prefix = "home"
        venue = "away"
    else:
        return

    # Obtener estadísticas numéricas del equipo y su oponente.
    if stats_response is not None:
        # Formato del endpoint /fixtures/statistics:
        # [{"team": {"id": X}, "statistics": [{"type": "Corner Kicks", "value": 5}, ...]}, ...]
        team_stats_map = {}
        for team_block in stats_response:
            tid = team_block.get("team", {}).get("id")
            if not tid:
                continue
            block_stats = {}
            for item in team_block.get("statistics", []):
                name = item.get("type")
                value = item.get("value")
                if name:
                    block_stats[name] = clean_stat_value(value)
            team_stats_map[tid] = block_stats

        my_stats = team_stats_map.get(team_id, {})

        opponent_id = None
        for tid in team_stats_map:
            if tid != team_id:
                opponent_id = tid
                break

        opp_stats = team_stats_map.get(opponent_id, {}) if opponent_id else {}

        # Construir el dict stats con claves compatibles
        # con el formato {"home_corners": X, "away_corners": Y, ...}
        def val(block, names):
            for n in names:
                if n in block:
                    return block[n]
            return None

        stats = {}
        stat_defs = [
            ("corners", ["Corner Kicks"]),
            ("shots", ["Total Shots"]),
            ("sot", ["Shots on Goal"]),
            ("yellow", ["Yellow Cards"]),
            ("red", ["Red Cards"]),
            ("saves", ["Goalkeeper Saves"]),
        ]
        for stat_name, api_names in stat_defs:
            stats[f"{prefix}_{stat_name}"] = val(my_stats, api_names)
            stats[f"{opponent_prefix}_{stat_name}"] = val(opp_stats, api_names)
    else:
        # Fallback: intentar extraer del fixture directamente
        # (no debería usarse, pero lo dejamos por compatibilidad).
        stats = fixture_statistics(fixture)

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

        if value is None:
            continue

        profile.setdefault(profile_key, []).append(value)

        # Versión separada por local/visitante:
        # p.ej. "home_corners_for" cuando el equipo jugaba en casa.
        venue_key = f"{venue}_{profile_key}"
        profile.setdefault(venue_key, []).append(value)


def finalize_market_profile(profile):
    """
    Convierte las listas históricas (global y por local/visitante)
    en medias.
    """
    result = dict(profile)

    market_keys = []

    for stat in MARKET_STAT_NAMES:
        for direction in ["for", "against"]:
            base = f"{stat}_{direction}"
            market_keys.append(base)
            market_keys.append(f"home_{base}")
            market_keys.append(f"away_{base}")

    for key in market_keys:
        values = profile.get(key, [])
        result[f"{key}_avg"] = historical_average(values)

    return result


@st.cache_data(ttl=21600)
def build_complete_pre_match_team_profile(
    team_id: int,
    league_id: int,
    seasons: List[int],
    reference_date: date,
    lookback_matches: int = 10,
):
    """
    Perfil completo de un equipo usando exclusivamente partidos de
    los 2 años anteriores al partido objetivo.

    Incluye: goles, córners, tiros, tiros a puerta, tarjetas y
    paradas — cada uno también separado por local/visitante.

    Optimizado para plan gratuito (100 peticiones/día):
    1) Se cachea el perfil completo (ttl 6h) para no recalcularlo
       si se vuelve a pedir el mismo equipo/jornada en la sesión.
    2) Las temporadas se consultan en orden y se PARA en cuanto hay
       partidos suficientes (lookback_matches) — antes se pedían
       siempre las 3 temporadas aunque la más reciente ya tuviera
       de sobra.
    3) Las estadísticas detalladas de los partidos históricos se
       piden en UNA sola llamada por lotes de hasta 20 IDs, en vez
       de una llamada HTTP por cada partido histórico.
    """
    start_date, end_date = historical_date_window(reference_date)

    collected = {}

    for season in seasons:

        fixtures, error = get_team_historical_fixtures(
            team_id,
            league_id,
            season,
            reference_date
        )

        if not error:
            for fixture in fixtures:
                fixture_id = fixture.get("fixture", {}).get("id")
                if fixture_id:
                    collected[fixture_id] = fixture

        # Early-stop: si ya tenemos partidos de sobra dentro de la
        # ventana y anteriores al partido objetivo, no hace falta
        # consultar temporadas más antiguas (ahorra peticiones).
        already_enough = [
            f for f in collected.values()
            if (
                parse_api_date(f.get("fixture", {}).get("date"))
                is not None
                and parse_api_date(
                    f.get("fixture", {}).get("date")
                ).date() < reference_date
            )
        ]

        if len(already_enough) >= lookback_matches:
            break

    fixtures = list(collected.values())

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

    fixtures = fixtures[:lookback_matches]

    profile = {
        "matches": 0,
        "goals_for": [],
        "goals_against": [],
        "home_goals_for": [],
        "home_goals_against": [],
        "away_goals_for": [],
        "away_goals_against": [],
    }

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

    # Estadísticas de mercados (córners, tiros, tarjetas, paradas):
    #
    # El endpoint /fixtures?ids= (batch) NO devuelve estadísticas.
    # Se necesita /fixtures/statistics?fixture={id} para cada partido.
    # Cada llamada se cachea 6h, así que repeticiones del mismo equipo
    # en la sesión no consumen peticiones extra.
    #
    # Se usa el fixture original (del batch) para saber local/visitante,
    # y la respuesta de /fixtures/statistics para los valores reales.
    for fixture in fixtures:

        fixture_id = fixture.get("fixture", {}).get("id")

        if not fixture_id:
            continue

        stats_response, _ = get_fixture_statistics_single(
            fixture_id
        )

        if stats_response:
            add_market_stats_to_team_profile(
                profile,
                fixture,
                team_id,
                stats_response=stats_response,
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


MIN_MATCHES_FOR_VENUE_SPLIT = 3


def venue_or_overall_key(profile, stat_base, venue):
    """
    Devuelve la clave de perfil a usar para un mercado: la versión
    separada por local/visitante (p.ej. "home_corners_for_avg") si
    hay al menos MIN_MATCHES_FOR_VENUE_SPLIT partidos con ese split,
    o si no la media global ("corners_for_avg") como respaldo.

    Con el histórico limitado del plan gratuito, exigir siempre el
    split local/visitante dejaría a muchos equipos sin predicción
    de mercados; este respaldo evita eso sin perder la señal cuando
    sí hay datos suficientes.
    """
    venue_key = f"{venue}_{stat_base}"

    # Reutilizamos la lista cruda (no solo la media) para contar
    # cuántos partidos hay en ese split.
    raw_key = venue_key.replace("_avg", "")
    raw_values = profile.get(raw_key, [])

    if (
        len(raw_values) >= MIN_MATCHES_FOR_VENUE_SPLIT
        and profile.get(venue_key) is not None
    ):
        return venue_key

    return stat_base


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

    Usa la media local del equipo local y la media visitante del
    equipo visitante siempre que haya histórico suficiente
    (>= MIN_MATCHES_FOR_VENUE_SPLIT partidos en ese split); si no,
    cae a la media global del equipo.
    """
    predictions = []

    market_defs = [
        (
            "corners_for_avg", "corners_against_avg",
            "📐 Córners", [7.5, 8.5, 9.5, 10.5, 11.5]
        ),
        (
            "sot_for_avg", "sot_against_avg",
            "🎯 Tiros a puerta", [5.5, 6.5, 7.5, 8.5, 9.5, 10.5]
        ),
        (
            "yellow_for_avg", "yellow_against_avg",
            "🟨 Tarjetas", [2.5, 3.5, 4.5, 5.5, 6.5]
        ),
        (
            "saves_for_avg", "saves_against_avg",
            "🧤 Paradas", [2.5, 3.5, 4.5, 5.5, 6.5]
        ),
    ]

    for for_base, against_base, market_label, lines in market_defs:

        home_for_key = venue_or_overall_key(
            home_profile, for_base, "home"
        )
        home_against_key = venue_or_overall_key(
            home_profile, against_base, "home"
        )
        away_for_key = venue_or_overall_key(
            away_profile, for_base, "away"
        )
        away_against_key = venue_or_overall_key(
            away_profile, against_base, "away"
        )

        expected = expected_from_profiles(
            home_profile,
            away_profile,
            home_for_key,
            home_against_key,
            away_for_key,
            away_against_key,
        )

        if not expected:
            continue

        expected_total = sum(expected)

        for line in lines:

            probability = poisson_over(
                expected_total,
                line
            )

            predictions.append({
                "market": market_label,
                "selection": f"Más de {line}",
                "probability": probability,
                "source": (
                    "Histórico máx. 2 años · split local/visitante "
                    "cuando hay datos suficientes"
                )
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
    historical_seasons: List[int],
    lookback_matches: int = 10,
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
        reference_date,
        lookback_matches,
    )

    away_profile = build_complete_pre_match_team_profile(
        away_id,
        league_id,
        historical_seasons,
        reference_date,
        lookback_matches,
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
                "source": (
                    f"Histórico máx. 2 años · últimos "
                    f"{lookback_matches} partidos"
                )
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


def translate_selection_to_odds_format(selection: str) -> str:
    """
    Las predicciones se generan en español ("Más de 8.5") pero
    API-Football devuelve las cuotas con valores en inglés
    ("Over 8.5"). Sin esta traducción, find_market_odds nunca
    encontraba una cuota real y el cálculo de EV/Value quedaba
    siempre vacío.
    """

    text = normalise_text(selection)

    text = text.replace("más de", "over")
    text = text.replace("mas de", "over")
    text = text.replace("menos de", "under")

    return text.strip()


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

    target_selection = translate_selection_to_odds_format(
        selection
    )

    # Extraemos la línea numérica (p.ej. "8.5") para poder hacer
    # un matching robusto aunque el formato del texto varíe entre
    # casas de apuestas ("Over 8.5", "Más +8.5", etc.).
    line_match = re.search(r"(\d+(?:\.\d+)?)", target_selection)
    target_line = line_match.group(1) if line_match else None
    target_is_over = "over" in target_selection
    target_is_under = "under" in target_selection

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

        market_matches = (
            target_market in current_market
            or
            current_market in target_market
        )

        if not market_matches:
            continue

        # 1) intento directo (por si algún bookmaker ya usa texto
        #    equivalente al traducido)
        if target_selection and target_selection in current_value:
            return (
                row["odd"],
                row["bookmaker"]
            )

        # 2) intento por línea + dirección (over/under), que es el
        #    formato real que devuelve API-Football
        if target_line and (target_is_over or target_is_under):

            direction_ok = (
                (target_is_over and "over" in current_value)
                or (target_is_under and "under" in current_value)
            )

            if direction_ok and target_line in current_value:

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
    historical_seasons,
    lookback_matches=10,
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
            historical_seasons,
            lookback_matches,
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

        # Usamos palabras clave cortas en vez de nombres completos:
        # los bookmakers nombran los mercados de forma distinta
        # ("Corners Over Under", "Total Corners", "Alternative
        # Corners"...) y find_market_odds hace matching de
        # substring en ambas direcciones + línea numérica exacta,
        # así que la palabra clave es suficiente y más robusta.

        if "Goles" in market:

            api_market = "goals"

        elif "Córners" in market:

            api_market = "corners"

        elif "Tarjetas" in market:

            api_market = "cards"

        elif "Tiros a puerta" in market:

            api_market = "shots on goal"

        elif "Paradas" in market:

            api_market = "goalkeeper saves"

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
# CALIBRACIÓN (backtest ligero, opcional, bajo demanda)
# ============================================================
#
# Esto NO es un backtest riguroso: usa los mismos partidos que
# alimentan el histórico (evaluación dentro de muestra), porque en
# plan gratuito no hay presupuesto de peticiones para reservar un
# conjunto de partidos totalmente aparte. Sirve para detectar
# errores burdos de calibración (p.ej. que el modelo prediga
# sistemáticamente demasiado alto o demasiado bajo), no para
# certificar la rentabilidad real del modelo.
#
# Importante: para cada partido de prueba, el perfil pre-partido
# de cada equipo solo usa partidos ESTRICTAMENTE ANTERIORES a esa
# fecha (ver build_complete_pre_match_team_profile), así que el
# propio resultado del partido de prueba nunca se filtra hacia su
# propia predicción.

ACTUAL_MARKET_FIELDS = {
    "📐 Córners": ("home_corners", "away_corners"),
    "🎯 Tiros a puerta": ("home_sot", "away_sot"),
    "🟨 Tarjetas": ("home_yellow", "away_yellow"),
    "🧤 Paradas": ("home_saves", "away_saves"),
}


def run_calibration_check(
    fixtures,
    league_id,
    historical_seasons,
    lookback_matches,
):
    """
    Para cada fixture FT recibido, genera las predicciones que se
    habrían hecho ANTES del partido y las compara con lo que pasó
    realmente. Devuelve una lista de filas para mostrar en tabla.
    """
    rows = []

    for fixture in fixtures:

        fixture_id = fixture.get("fixture", {}).get("id")

        teams = fixture.get("teams", {})
        home_name = teams.get("home", {}).get("name", "?")
        away_name = teams.get("away", {}).get("name", "?")

        goals = fixture.get("goals", {})
        actual_home_goals = goals.get("home")
        actual_away_goals = goals.get("away")

        predictions = build_match_predictions(
            fixture,
            league_id,
            historical_seasons,
            lookback_matches,
        )

        # Obtener estadísticas reales del partido para calibración.
        stats_response, _ = get_fixture_statistics_single(
            fixture_id
        ) if fixture_id else (None, None)

        if stats_response:
            # Construir dict tipo {"home_corners": X, "away_corners": Y}
            home_id = teams.get("home", {}).get("id")
            actual_stats = {}
            for team_block in stats_response:
                tid = team_block.get("team", {}).get("id")
                block_stats = {}
                for item in team_block.get("statistics", []):
                    name = item.get("type")
                    value = item.get("value")
                    if name:
                        block_stats[name] = clean_stat_value(value)
                if tid == home_id:
                    actual_stats["home_corners"] = block_stats.get("Corner Kicks")
                    actual_stats["home_sot"] = block_stats.get("Shots on Goal")
                    actual_stats["home_yellow"] = block_stats.get("Yellow Cards")
                    actual_stats["home_saves"] = block_stats.get("Goalkeeper Saves")
                else:
                    actual_stats["away_corners"] = block_stats.get("Corner Kicks")
                    actual_stats["away_sot"] = block_stats.get("Shots on Goal")
                    actual_stats["away_yellow"] = block_stats.get("Yellow Cards")
                    actual_stats["away_saves"] = block_stats.get("Goalkeeper Saves")
        else:
            actual_stats = {}

        for prediction in predictions:

            market = prediction["market"]
            probability = prediction["probability"]
            selection = prediction["selection"]

            if probability is None:
                continue

            line_match = re.search(
                r"(\d+(?:\.\d+)?)", selection
            )
            if not line_match:
                continue
            line = float(line_match.group(1))

            if market == "⚽ Goles":
                if actual_home_goals is None or actual_away_goals is None:
                    continue
                actual_total = actual_home_goals + actual_away_goals

            elif market in ACTUAL_MARKET_FIELDS:
                home_field, away_field = ACTUAL_MARKET_FIELDS[market]
                h = actual_stats.get(home_field)
                a = actual_stats.get(away_field)
                if h is None or a is None:
                    continue
                actual_total = h + a

            else:
                continue

            hit = 1.0 if actual_total > line else 0.0
            brier = (probability - hit) ** 2

            rows.append({
                "Partido": f"{home_name} vs {away_name}",
                "Mercado": market,
                "Selección": selection,
                "Prob. predicha": f"{probability * 100:.1f}%",
                "Total real": actual_total,
                "Acierto": "✅" if hit == 1.0 else "❌",
                "Brier": round(brier, 3),
            })

    return rows


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
        '⚽ ValueBet Pro V8'
        '</div>',
        unsafe_allow_html=True
    )

    st.markdown(
        '<div class="subtitle">'
        'Pronósticos del día · Datos históricos reales'
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

        target_date = st.date_input(
            "Fecha de los partidos",
            value=date.today(),
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

        only_with_value = st.checkbox(
            "Mostrar solo apuestas con Value real "
            "(cuota disponible + EV ≥ mínimo)",
            value=False,
        )

        st.divider()

        st.subheader("📡 Consumo de API")

        lookback_matches = st.slider(
            "Partidos históricos por equipo",
            5,
            20,
            10,
            1,
            help=(
                "Menos partidos = menos peticiones, "
                "pero perfiles menos precisos."
            ),
        )

        used_calls = st.session_state.get(
            "api_call_count", {}
        ).get("API-Football", 0)

        st.caption(
            f"Peticiones API-Football: "
            f"**{used_calls}** / ~100 diarias"
        )

        st.divider()

        st.caption(
            "Plan gratuito: temporadas 2022-2024. "
            "Partidos del día se obtienen con "
            "from/to sin season."
        )

    competition = COMPETITIONS[competition_name]
    league_id = competition["api_football"]
    football_data_code = competition["football_data"]

    # Temporadas para el histórico (plan gratuito: 2022-2024)
    historical_seasons = [2024, 2023, 2022]

    # --------------------------------------------------------
    # OBTENER PARTIDOS DEL DÍA
    # --------------------------------------------------------

    today_fixtures, today_error = get_today_fixtures(
        league_id,
        target_date
    )

    if today_error:

        st.error(
            f"Error obteniendo partidos: {today_error}"
        )

        return

    # --------------------------------------------------------
    # TABS
    # --------------------------------------------------------

    (
        tab_predictions,
        tab_widget,
        tab_table,
        tab_calibration,
    ) = st.tabs(
        [
            "🔮 Pronósticos del día",
            "📅 Partidos en vivo",
            "🏆 Clasificación",
            "🧪 Calibración",
        ]
    )

    # ========================================================
    # PRONÓSTICOS DEL DÍA
    # ========================================================

    with tab_predictions:

        st.markdown(
            '<div class="section-title">'
            f'🔮 Pronósticos — {target_date.strftime("%d/%m/%Y")}'
            '</div>',
            unsafe_allow_html=True
        )

        if not today_fixtures:

            st.info(
                f"No hay partidos para el "
                f"{target_date.strftime('%d/%m/%Y')} "
                f"en {competition_name}."
            )

        else:

            st.caption(
                f"**{len(today_fixtures)} partidos**. "
                "Selecciona cuáles analizar. "
                "Histórico de 2022-2024."
            )

            match_labels = {
                f"{f['teams']['home']['name']} vs "
                f"{f['teams']['away']['name']} "
                f"({local_time_string(f['fixture']['date'])}) "
                f"[{f['fixture'].get('status', {}).get('short', '?')}]": f
                for f in today_fixtures
            }

            est_calls = 2 * lookback_matches + 3

            all_labels = list(match_labels.keys())

            # Auto-seleccionar hasta 3 partidos para no
            # excedir ~100 peticiones/día del plan gratuito.
            max_auto = 3
            safe_default = all_labels[:max_auto]

            selected_labels = st.multiselect(
                f"Partidos a analizar (~{est_calls} peticiones c/u, "
                f"máx {max_auto} auto-seleccionados)",
                all_labels,
                default=safe_default,
                key="prediction_fixture_select",
            )

            fixtures_to_analyze = [
                match_labels[label]
                for label in selected_labels
            ]

            if not fixtures_to_analyze:

                st.info("Selecciona al menos un partido.")

            else:

                prediction_rows = []
                debug_info = []

                with st.spinner(
                    "Calculando perfiles y predicciones..."
                ):

                    for fixture in fixtures_to_analyze:
                        home_name = fixture["teams"]["home"]["name"]
                        away_name = fixture["teams"]["away"]["name"]

                        fixture_date_raw = fixture.get("fixture", {}).get("date")
                        fixture_dt = parse_api_date(fixture_date_raw)
                        ref_date = fixture_dt.date() if fixture_dt else date.today()

                        # Construir perfiles
                        home_id = fixture["teams"]["home"]["id"]
                        away_id = fixture["teams"]["away"]["id"]

                        home_profile = build_complete_pre_match_team_profile(
                            home_id, league_id,
                            historical_seasons, ref_date,
                            lookback_matches,
                        )
                        away_profile = build_complete_pre_match_team_profile(
                            away_id, league_id,
                            historical_seasons, ref_date,
                            lookback_matches,
                        )

                        hm = home_profile.get("matches", 0)
                        am = away_profile.get("matches", 0)
                        hgf = home_profile.get("goals_for_avg")
                        agf = away_profile.get("goals_for_avg")

                        debug_info.append(
                            f"{home_name}: {hm} partidos, "
                            f"goles avg={hgf}"
                        )
                        debug_info.append(
                            f"{away_name}: {am} partidos, "
                            f"goles avg={agf}"
                        )

                        rows = create_predictions_for_fixture(
                            fixture,
                            league_id,
                            historical_seasons,
                            lookback_matches,
                        )

                        prediction_rows.extend(rows)

                # Debug: mostrar info de perfiles
                used_calls = st.session_state.get(
                    "api_call_count", {}
                ).get("API-Football", 0)
                with st.expander(
                    "\U0001f527 Diagnóstico", expanded=False
                ):
                    st.text(
                        f"Temporadas consultadas: "
                        f"{historical_seasons}"
                    )
                    st.text(
                        f"Peticiones API usadas: {used_calls}"
                    )
                    for line in debug_info:
                        st.text(line)
                    st.text(
                        f"Total predicciones generadas: "
                        f"{len(prediction_rows)}"
                    )

                if not prediction_rows:

                    st.warning(
                        "No se pudieron generar predicciones. "
                        "Revisa el diagnóstico arriba para ver "
                        "si los perfiles tienen datos. "
                        "Posibles causas: sin histórico suficiente, "
                        "sin cuotas disponibles, o límite de API agotado."
                    )

                else:

                    predictions_df = pd.DataFrame(prediction_rows)

                    predictions_df = predictions_df[
                        predictions_df["probability"]
                        >= (min_probability / 100)
                    ].copy()

                    if predictions_df.empty:

                        st.info(
                            "No hay pronósticos que superen "
                            "la probabilidad mínima."
                        )

                    else:

                        ev_num = pd.to_numeric(
                            predictions_df["ev"],
                            errors="coerce"
                        )

                        if only_with_value:
                            predictions_df = predictions_df[
                            ev_num >= (min_ev / 100)
                            ].copy()
                        else:
                            predictions_df = predictions_df[
                            ev_num.isna()
                            | (ev_num >= (min_ev / 100))
                            ].copy()

                    if predictions_df.empty:

                        st.info(
                            "No hay pronósticos que superen "
                            "el EV mínimo seleccionado."
                        )

                    else:

                        predictions_df["ev_sort"] = (
                            predictions_df["ev"].fillna(-999)
                        )

                        predictions_df = (
                            predictions_df.sort_values(
                                ["ev_sort", "probability"],
                                ascending=False
                            )
                        )

                        for _, row in (
                            predictions_df.head(50).iterrows()
                        ):

                            st.markdown(
                                f"### {row['time']} · "
                                f"{row['home']} vs {row['away']}"
                            )

                            render_prediction(row)

    # ========================================================
    # WIDGET EN VIVO
    # ========================================================

    with tab_widget:

        st.markdown(
            '<div class="section-title">'
            '📅 Partidos en vivo'
            '</div>',
            unsafe_allow_html=True
        )

        st.caption(
            "Widget en tiempo real (no consume peticiones API)."
        )

        widget_html = """
        <script src="https://widgets.api-sports.io/1.4.4/widgets.js"></script>
        <api-sports-widget data-type="config"
          data-sport="football"
          data-lang="es"
          data-theme="white"
          data-timezone="Europe/Madrid"
          data-show-errors="true"
          data-show-logos="true"
          data-favorite="true"
        ></api-sports-widget>
        <api-sports-widget data-type="games"
          data-date="__DATE__"
          data-games-style="1"
          data-refresh="60"
          data-league="__LEAGUE_ID__"
          data-tab="all"
        ></api-sports-widget>
        """.replace(
            "__LEAGUE_ID__", str(league_id)
        ).replace(
            "__DATE__", target_date.isoformat()
        )

        components.html(widget_html, height=500)

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

        standings, error = get_standings(football_data_code)

        if error:
            st.error(error)
        elif standings.empty:
            st.info("No hay clasificación disponible.")
        else:
            st.dataframe(
                standings,
                hide_index=True,
                use_container_width=True
            )

    # ========================================================
    # CALIBRACIÓN
    # ========================================================

    with tab_calibration:

        st.markdown(
            '<div class="section-title">'
            '🧪 Calibración (opcional)'
            '</div>',
            unsafe_allow_html=True
        )

        st.caption(
            "Comprueba predicciones vs resultados reales "
            "en partidos ya jugados. Consume peticiones API."
        )

        calib_season = st.selectbox(
            "Temporada",
            [2024, 2023, 2022],
            index=0,
            key="calibration_season"
        )

        calib_rounds, calib_round_error = get_rounds(
            league_id, calib_season
        )

        if calib_round_error:
            st.error(f"Error: {calib_round_error}")
        elif not calib_rounds:
            st.info(
                f"Sin jornadas para {competition_name} "
                f"en {calib_season}."
            )
        else:

            calib_rounds = sorted(
                calib_rounds, key=round_sort_key
            )

            calibration_round = st.selectbox(
                "Jornada a comprobar",
                calib_rounds,
                key="calibration_round"
            )

            max_matches = st.slider(
                "Nº de partidos", 1, 5, 3, 1,
                key="calibration_max_matches"
            )

            run_check = st.button(
                "▶️ Ejecutar comprobación"
            )

            if run_check:

                calib_fixtures, calib_error = (
                    get_fixtures_by_round(
                        league_id,
                        calib_season,
                        calibration_round
                    )
                )

                if calib_error:
                    st.error(calib_error)
                else:

                    finished = [
                        f for f in calib_fixtures
                        if f["fixture"].get(
                            "status", {}
                        ).get("short") == "FT"
                    ][:max_matches]

                    if not finished:

                        st.info(
                            "Sin partidos finalizados (FT)."
                        )

                    else:

                        with st.spinner(
                            "Calculando predicciones..."
                        ):

                            calib_rows = (
                                run_calibration_check(
                                    finished,
                                    league_id,
                                    [calib_season, calib_season - 1],
                                    lookback_matches,
                                )
                            )

                        if not calib_rows:

                            st.info(
                                "Histórico insuficiente "
                                "para estos equipos."
                            )

                        else:

                            calib_df = pd.DataFrame(calib_rows)

                            hit_rate = (
                                (calib_df["Acierto"] == "✅").mean()
                                * 100
                            )
                            avg_brier = calib_df["Brier"].mean()

                            col1, col2 = st.columns(2)

                            with col1:
                                st.metric(
                                    "Acierto",
                                    f"{hit_rate:.1f}%"
                                )

                            with col2:
                                st.metric(
                                    "Brier score",
                                    f"{avg_brier:.3f}",
                                    help=(
                                        "0 = perfecto, "
                                        "0.25 = azar."
                                    )
                                )

                            st.dataframe(
                                calib_df,
                                hide_index=True,
                                use_container_width=True
                            )

    # ========================================================
    # FOOTER
    # ========================================================

    st.divider()

    used_calls_footer = st.session_state.get(
        "api_call_count", {}
    ).get("API-Football", 0)

    st.caption(
        f"ValueBet Pro V8 · "
        f"{used_calls_footer} peticiones API-Football"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()
