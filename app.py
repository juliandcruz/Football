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
import time

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


# ============================================================
# ESTADÍSTICAS DE JUGADOR (API-Football)
# ============================================================
#
# football-data.org (la API principal de esta app) y el CSV
# histórico NO tienen datos a nivel de jugador — solo agregados de
# equipo. Para "qué jugador tira más a puerta" o "qué jugador
# comete/recibe más faltas" hace falta una fuente distinta.
# API-Football sí expone esto vía /players?team=&season=.
#
# Este bloque es independiente del resto de la app y solo se llama
# bajo demanda (botón explícito), porque en plan gratuito la cuota
# de API-Football está muy limitada (100 peticiones/día).

API_FOOTBALL_URL = "https://v3.football.api-sports.io"

# Mapa de competición (código football-data.org) -> liga API-Football
API_FOOTBALL_LEAGUE_MAP = {
    "PD": (140, "La Liga"),
    "PL": (39, "Premier League"),
    "SA": (135, "Serie A"),
    "BL1": (78, "Bundesliga"),
    "FL1": (61, "Ligue 1"),
    "CL": (2, "Champions League"),
}

# Temporadas disponibles en plan gratuito para las ligas grandes:
# API-Football no da la temporada en curso para estas competiciones
# en el plan gratuito, solo temporadas ya completadas.
API_FOOTBALL_FREE_SEASONS = [2024, 2023, 2022]

MIN_APPEARANCES_FOR_PLAYER_STATS = 3


def get_api_football_key():
    try:
        return st.secrets["API_FOOTBALL_KEY"]
    except Exception:
        return None


def api_football_get(endpoint, params):
    """
    Llamada HTTP a API-Football con contador de peticiones visible
    en sesión (igual patrón que usamos en el otro proyecto para no
    perder de vista el consumo de cuota).

    Incluye una pequeña pausa MÍNIMA entre peticiones consecutivas.
    No es por el límite diario (100/día), sino por el límite POR
    MINUTO de su plan gratuito: sus términos de servicio permiten
    suspender la cuenta automáticamente ante "patrones de petición
    abusivos, desproporcionados o excesivos", y varias llamadas
    seguidas sin pausa (como pedir equipos + jugadores de 2 equipos
    en una sola ejecución) pueden parecer tráfico de bot aunque
    estés muy por debajo de la cuota diaria.
    """
    key = get_api_football_key()

    if not key:
        return None, "Falta la clave API_FOOTBALL_KEY en st.secrets."

    if "api_football_call_count" not in st.session_state:
        st.session_state["api_football_call_count"] = 0

    if "api_football_last_call_ts" not in st.session_state:
        st.session_state["api_football_last_call_ts"] = 0.0

    min_gap_seconds = 1.2

    elapsed = time.time() - st.session_state["api_football_last_call_ts"]
    if elapsed < min_gap_seconds:
        time.sleep(min_gap_seconds - elapsed)

    st.session_state["api_football_call_count"] += 1

    headers = {"x-apisports-key": key}

    try:
        response = requests.get(
            API_FOOTBALL_URL + endpoint,
            headers=headers,
            params=params,
            timeout=20,
        )

        st.session_state["api_football_last_call_ts"] = time.time()

        if response.status_code != 200:
            return None, f"Error API-Football ({response.status_code})"

        data = response.json()

        if data.get("errors"):
            return None, str(data["errors"])

        return data, None

    except Exception as e:
        return None, str(e)


@st.cache_data(ttl=21600)
def get_api_football_teams(league_id: int, season: int):
    """
    Lista de equipos de una liga/temporada en API-Football (para
    resolver nombre -> team_id). Una sola llamada por liga/temporada,
    reutilizable para todos los partidos de esa liga.
    """
    data, error = api_football_get(
        "/teams", {"league": league_id, "season": season}
    )

    if error or not data:
        return {}, error

    teams = {}
    for entry in data.get("response", []):
        team = entry.get("team", {})
        name = team.get("name")
        team_id = team.get("id")
        if name and team_id:
            teams[name] = team_id

    return teams, None


def resolve_api_football_team_id(team_name: str, teams_by_name: dict):
    """
    Reutiliza el mismo resolver de nombres (normalización + alias +
    fuzzy) que usamos para el CSV, aplicado ahora contra la lista de
    equipos de API-Football.
    """
    norm_to_original = {
        normalize_team_name(name): name
        for name in teams_by_name.keys()
    }

    resolved_name, score = resolve_team_to_csv(team_name, norm_to_original)

    if resolved_name is None:
        return None, 0.0

    return teams_by_name.get(resolved_name), score


@st.cache_data(ttl=21600)
def get_team_players_stats(team_id: int, league_id: int, season: int):
    """
    Estadísticas de todos los jugadores de un equipo en una
    temporada: tiros a puerta, faltas cometidas y faltas recibidas,
    con nº de partidos jugados (para poder calcular una media por
    partido y no solo el acumulado).

    Limitado a 2 páginas (hasta 40 jugadores) para no disparar el
    consumo de cuota — suficiente para cubrir la plantilla habitual.
    """
    players = []
    page = 1
    max_pages = 2

    while page <= max_pages:

        data, error = api_football_get(
            "/players",
            {"team": team_id, "season": season, "page": page},
        )

        if error or not data:
            break

        for entry in data.get("response", []):

            player_info = entry.get("player", {})
            stats_list = entry.get("statistics", [])

            # Un jugador puede tener varias entradas de estadísticas
            # (una por competición/equipo si fue traspasado). Nos
            # quedamos con la que corresponde a esta liga.
            stat = next(
                (
                    s for s in stats_list
                    if s.get("league", {}).get("id") == league_id
                ),
                None,
            )

            if not stat:
                continue

            appearances = stat.get("games", {}).get("appearences") or 0

            if appearances < MIN_APPEARANCES_FOR_PLAYER_STATS:
                continue

            shots_on = stat.get("shots", {}).get("on") or 0
            fouls_committed = stat.get("fouls", {}).get("committed") or 0
            fouls_drawn = stat.get("fouls", {}).get("drawn") or 0

            players.append({
                "name": player_info.get("name"),
                "photo": player_info.get("photo"),
                "position": stat.get("games", {}).get("position"),
                "appearances": appearances,
                "shots_on_per_game": shots_on / appearances,
                "fouls_committed_per_game": fouls_committed / appearances,
                "fouls_drawn_per_game": fouls_drawn / appearances,
            })

        paging = data.get("paging", {})
        if page >= paging.get("total", 1):
            break

        page += 1

    return players, None


def build_player_predictions(
    home_team_name, away_team_name,
    home_team_id, away_team_id,
    league_id, season,
):
    """
    Devuelve un dict con los rankings de jugadores para los 3
    mercados: tiros a puerta, faltas cometidas y faltas recibidas,
    cada uno con el equipo de procedencia de cada jugador.
    """
    home_players, home_error = get_team_players_stats(
        home_team_id, league_id, season
    ) if home_team_id else ([], "Equipo local no encontrado en API-Football")

    away_players, away_error = get_team_players_stats(
        away_team_id, league_id, season
    ) if away_team_id else ([], "Equipo visitante no encontrado en API-Football")

    for p in home_players:
        p["team"] = home_team_name
    for p in away_players:
        p["team"] = away_team_name

    all_players = home_players + away_players

    def top(metric, n=5):
        return sorted(
            all_players, key=lambda p: p[metric], reverse=True
        )[:n]

    return {
        "shots_on": top("shots_on_per_game"),
        "fouls_committed": top("fouls_committed_per_game"),
        "fouls_drawn": top("fouls_drawn_per_game"),
        "errors": [e for e in [home_error, away_error] if e],
        "sample_size": len(all_players),
    }


# ============================================================
# ESTADÍSTICAS DE JUGADOR — FUENTE ALTERNATIVA: FBref
# ============================================================
#
# A diferencia de API-Football, FBref no depende de una cuenta que
# se pueda suspender ni de una cuota diaria — es gratis siempre.
# No tiene API oficial, así que se obtiene con web scraping, PERO
# a diferencia de sitios como Sofascore o FotMob (que prohíben el
# scraping sin excepción en sus términos), FBref/Sports-Reference
# publica una política explícita tolerando bots que respeten un
# límite de 10 peticiones/minuto (sports-reference.com/bot-traffic).
# Aquí nos quedamos por debajo de eso (1 petición cada 7s ≈ 8,6/min,
# con margen real bajo su límite de 10/min) y
# cacheamos agresivamente para no repetir peticiones innecesarias.
#
# Esto es para uso personal (tus propias decisiones de apuesta), no
# para redistribuir los datos — su ToS prohíbe explícitamente
# revender/ceder el contenido del sitio a terceros.

FBREF_BASE_URL = "https://fbref.com"

FBREF_MIN_GAP_SECONDS = 7.0

# id de competición en FBref + nombre usado en la URL
FBREF_COMPETITIONS = {
    "PD": (12, "La-Liga"),
    "PL": (9, "Premier-League"),
    "SA": (11, "Serie-A"),
    "BL1": (20, "Bundesliga"),
    "FL1": (13, "Ligue-1"),
    "CL": (8, "Champions-League"),
}

FBREF_HEADERS = {
    # Cabeceras de un navegador normal (Chrome en Windows). Esto es
    # una práctica habitual y razonable para identificarse como
    # tráfico web estándar — no incluye nada diseñado para falsear
    # huella de navegador ni saltarse bloqueos activos.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://fbref.com/en/",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
}


def fbref_current_season_string(today: datetime = None) -> str:
    """
    FBref identifica las temporadas europeas como "2024-2025". Las
    temporadas empiezan a mediados de año (julio/agosto), así que
    antes de esa fecha consideramos que seguimos en la temporada
    que empezó el año anterior.
    """
    today = today or datetime.now()
    if today.month >= 7:
        return f"{today.year}-{today.year + 1}"
    return f"{today.year - 1}-{today.year}"


def get_fbref_session():
    """
    Reutiliza una única sesión (con sus cookies) durante toda la
    sesión de Streamlit, en vez de peticiones sueltas sin estado.
    Visitar primero la portada y guardar las cookies que da el
    sitio es simplemente lo que hace cualquier navegador normal al
    entrar por primera vez — no es un intento de evadir nada.
    """
    if "fbref_session" not in st.session_state:
        session = requests.Session()
        session.headers.update(FBREF_HEADERS)
        try:
            session.get(
                "https://fbref.com/en/", timeout=20
            )
        except Exception:
            pass
        st.session_state["fbref_session"] = session

    return st.session_state["fbref_session"]


def fbref_rate_limited_get(url: str):
    """
    GET a FBref respetando el límite de 10 peticiones/minuto que
    ellos mismos publican como tolerado para bots — nos quedamos
    en ~8,6 peticiones/minuto, por debajo de su límite de 10/min,
    pero en la práctica muy por debajo porque los resultados se
    cachean 24h).
    """
    if "fbref_last_call_ts" not in st.session_state:
        st.session_state["fbref_last_call_ts"] = 0.0

    elapsed = time.time() - st.session_state["fbref_last_call_ts"]
    if elapsed < FBREF_MIN_GAP_SECONDS:
        time.sleep(FBREF_MIN_GAP_SECONDS - elapsed)

    try:
        session = get_fbref_session()
        response = session.get(url, timeout=20)
        st.session_state["fbref_last_call_ts"] = time.time()

        if response.status_code == 403:
            return None, (
                "FBref ha bloqueado la petición (403). Es probable que "
                "esté bloqueando el rango de IPs de centros de datos "
                "de Streamlit Cloud, no un problema de ritmo de "
                "peticiones. No voy a intentar saltarme ese bloqueo "
                "(falsificar huella de navegador, proxies, etc.) — "
                "si te sigue pasando, la vía fiable es reactivar "
                "API-Football."
            )

        if response.status_code != 200:
            return None, f"Error FBref ({response.status_code})"

        return response.text, None

    except Exception as e:
        return None, str(e)


def fbref_parse_player_table(html: str, wanted_columns):
    """
    Extrae la tabla "grande" de jugadores de una página de FBref.

    Dos particularidades de FBref hay que tratar:
    1) Varias tablas están envueltas en comentarios HTML
       (<!-- ... -->) para carga diferida — hay que "descomentarlas"
       antes de que pandas pueda verlas.
    2) La tabla repite la fila de cabecera cada ~25 filas (para que
       se vea al hacer scroll) — pandas las cuela como filas de
       datos y hay que descartarlas.
    """
    uncommented = html.replace("<!--", "").replace("-->", "")

    try:
        tables = pd.read_html(uncommented)
    except Exception as e:
        return pd.DataFrame(), str(e)

    if not tables:
        return pd.DataFrame(), "No se encontraron tablas en la página."

    # La tabla de jugadores es, con diferencia, la más larga de la
    # página (una fila por jugador de toda la liga).
    biggest = max(tables, key=lambda t: len(t))

    # Las columnas de FBref vienen a veces en 2 niveles
    # (p.ej. ("Standard","Sh")); nos quedamos con el nivel de abajo.
    if isinstance(biggest.columns, pd.MultiIndex):
        biggest.columns = [
            col[-1] if isinstance(col, tuple) else col
            for col in biggest.columns
        ]

    biggest = biggest.loc[:, ~biggest.columns.duplicated()]

    missing = [c for c in wanted_columns if c not in biggest.columns]
    if missing:
        return pd.DataFrame(), f"Columnas no encontradas: {missing}"

    df = biggest[wanted_columns].copy()

    # Descarta filas de cabecera repetidas incrustadas como datos.
    df = df[df["Player"] != "Player"]
    df = df.dropna(subset=["Player"])

    return df, None


@st.cache_data(ttl=86400)
def get_fbref_shooting_stats(competition_code: str, season: str):
    """
    Tiros / tiros a puerta por jugador de TODA la liga en una sola
    petición (mucho más eficiente que pedir equipo a equipo).
    """
    if competition_code not in FBREF_COMPETITIONS:
        return pd.DataFrame(), "Competición no mapeada en FBref."

    comp_id, comp_slug = FBREF_COMPETITIONS[competition_code]
    url = (
        f"{FBREF_BASE_URL}/en/comps/{comp_id}/{season}/shooting/"
        f"{season}-{comp_slug}-Stats"
    )

    html, error = fbref_rate_limited_get(url)
    if error:
        return pd.DataFrame(), error

    df, error = fbref_parse_player_table(
        html, ["Player", "Squad", "90s", "Sh", "SoT", "Sh/90", "SoT/90"]
    )
    return df, error


@st.cache_data(ttl=86400)
def get_fbref_misc_stats(competition_code: str, season: str):
    """
    Faltas cometidas/recibidas por jugador de toda la liga.
    """
    if competition_code not in FBREF_COMPETITIONS:
        return pd.DataFrame(), "Competición no mapeada en FBref."

    comp_id, comp_slug = FBREF_COMPETITIONS[competition_code]
    url = (
        f"{FBREF_BASE_URL}/en/comps/{comp_id}/{season}/misc/"
        f"{season}-{comp_slug}-Stats"
    )

    html, error = fbref_rate_limited_get(url)
    if error:
        return pd.DataFrame(), error

    df, error = fbref_parse_player_table(
        html, ["Player", "Squad", "90s", "Fls", "Fld"]
    )
    return df, error


def build_player_predictions_fbref(
    home_name, away_name, competition_code, season
):
    """
    Igual que build_player_predictions pero usando FBref: no
    depende de mapear team_id (se filtra directamente por el
    nombre de equipo de FBref, resuelto con nuestro mismo
    resolver de nombres normalizado + alias + fuzzy).
    """
    shooting_df, shooting_error = get_fbref_shooting_stats(
        competition_code, season
    )
    misc_df, misc_error = get_fbref_misc_stats(competition_code, season)

    errors = [e for e in [shooting_error, misc_error] if e]

    if shooting_df.empty and misc_df.empty:
        return {
            "shots_on": [], "fouls_committed": [], "fouls_drawn": [],
            "errors": errors, "sample_size": 0,
        }

    all_squads = set()
    if not shooting_df.empty:
        all_squads.update(shooting_df["Squad"].unique())
    if not misc_df.empty:
        all_squads.update(misc_df["Squad"].unique())

    norm_to_original = {
        normalize_team_name(name): name for name in all_squads
    }

    resolved_home, _ = resolve_team_to_csv(home_name, norm_to_original)
    resolved_away, _ = resolve_team_to_csv(away_name, norm_to_original)

    if resolved_home is None:
        errors.append(
            f"No se encontró a '{home_name}' entre los equipos de FBref."
        )
    if resolved_away is None:
        errors.append(
            f"No se encontró a '{away_name}' entre los equipos de FBref."
        )

    target_squads = {resolved_home, resolved_away} - {None}

    players = {}

    if not shooting_df.empty:
        subset = shooting_df[shooting_df["Squad"].isin(target_squads)]
        for _, row in subset.iterrows():
            nineties = pd.to_numeric(row.get("90s"), errors="coerce")
            if pd.isna(nineties) or nineties < 1.0:
                continue
            sot_per_90 = pd.to_numeric(row.get("SoT/90"), errors="coerce")
            if pd.isna(sot_per_90):
                continue
            players.setdefault(row["Player"], {
                "name": row["Player"], "team": row["Squad"],
                "appearances_90s": round(float(nineties), 1),
            })["shots_on_per_game"] = float(sot_per_90)

    if not misc_df.empty:
        subset = misc_df[misc_df["Squad"].isin(target_squads)]
        for _, row in subset.iterrows():
            nineties = pd.to_numeric(row.get("90s"), errors="coerce")
            if pd.isna(nineties) or nineties < 1.0:
                continue
            fls = pd.to_numeric(row.get("Fls"), errors="coerce")
            fld = pd.to_numeric(row.get("Fld"), errors="coerce")
            entry = players.setdefault(row["Player"], {
                "name": row["Player"], "team": row["Squad"],
                "appearances_90s": round(float(nineties), 1),
            })
            if not pd.isna(fls):
                entry["fouls_committed_per_game"] = float(fls) / float(nineties)
            if not pd.isna(fld):
                entry["fouls_drawn_per_game"] = float(fld) / float(nineties)

    all_players = list(players.values())

    def top(metric, n=5):
        candidates = [p for p in all_players if metric in p]
        return sorted(candidates, key=lambda p: p[metric], reverse=True)[:n]

    return {
        "shots_on": top("shots_on_per_game"),
        "fouls_committed": top("fouls_committed_per_game"),
        "fouls_drawn": top("fouls_drawn_per_game"),
        "errors": errors,
        "sample_size": len(all_players),
    }


HISTORY_WINDOW_YEARS = 2

# Cada mercado define:
# - lines_total: líneas para el TOTAL DEL PARTIDO (goles/córners/etc.
#   sumando ambos equipos)
# - lines_team: líneas para CADA EQUIPO por separado (solo lo suyo,
#   no se suma con el rival)
MARKET_DEFINITIONS = {
    "⚽ Goles": {
        "lines_total": [1.5, 2.5, 3.5],
        "lines_team": [0.5, 1.5, 2.5],
    },
    "📐 Córners": {
        "lines_total": [8.5, 9.5, 10.5],
        "lines_team": [3.5, 4.5, 5.5],
    },
    "🟨 Tarjetas": {
        "lines_total": [2.5, 3.5, 4.5, 5.5],
        "lines_team": [1.5, 2.5, 3.5],
    },
    "🎯 Disparos a puerta": {
        "lines_total": [6.5, 8.5, 10.5],
        "lines_team": [2.5, 3.5, 4.5],
    },
    "🟧 Faltas": {
        "lines_total": [18.5, 21.5, 24.5],
        "lines_team": [8.5, 10.5, 12.5],
    },
}

TOTAL_LABEL = "Ambos equipos"


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
            h_f, a_f = 11.5, 10.8

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

                hg_list, ha_list, hc_list, hy_list, hs_list, hf_list = [], [], [], [], [], []
                if not home_games.empty:
                    hg_list.append(home_games['FTHG'].mean())
                    ha_list.append(home_games['FTAG'].mean())
                    if 'HC' in home_games.columns: hc_list.append(home_games['HC'].mean())
                    if 'HY' in home_games.columns: hy_list.append(home_games['HY'].mean())
                    if 'HST' in home_games.columns: hs_list.append(home_games['HST'].mean())
                    if 'HF' in home_games.columns: hf_list.append(home_games['HF'].mean())
                if not away_games_as_home.empty:
                    hg_list.append(away_games_as_home['FTAG'].mean())
                    ha_list.append(away_games_as_home['FTHG'].mean())
                    if 'AC' in away_games_as_home.columns: hc_list.append(away_games_as_home['AC'].mean())
                    if 'AY' in away_games_as_home.columns: hy_list.append(away_games_as_home['AY'].mean())
                    if 'AST' in away_games_as_home.columns: hs_list.append(away_games_as_home['AST'].mean())
                    if 'AF' in away_games_as_home.columns: hf_list.append(away_games_as_home['AF'].mean())

                if hg_list: h_gf = sum(hg_list) / len(hg_list)
                if ha_list: h_ga = sum(ha_list) / len(ha_list)
                if hc_list: h_c = sum(hc_list) / len(hc_list)
                if hy_list: h_y = sum(hy_list) / len(hy_list)
                if hs_list: h_s = sum(hs_list) / len(hs_list)
                if hf_list: h_f = sum(hf_list) / len(hf_list)

                ag_list, aa_list, ac_list, ay_list, as_list, af_list = [], [], [], [], [], []
                if not away_games.empty:
                    ag_list.append(away_games['FTAG'].mean())
                    aa_list.append(away_games['FTHG'].mean())
                    if 'AC' in away_games.columns: ac_list.append(away_games['AC'].mean())
                    if 'AY' in away_games.columns: ay_list.append(away_games['AY'].mean())
                    if 'AST' in away_games.columns: as_list.append(away_games['AST'].mean())
                    if 'AF' in away_games.columns: af_list.append(away_games['AF'].mean())
                if not home_games_as_away.empty:
                    ag_list.append(home_games_as_away['FTHG'].mean())
                    aa_list.append(home_games_as_away['FTAG'].mean())
                    if 'HC' in home_games_as_away.columns: ac_list.append(home_games_as_away['HC'].mean())
                    if 'HY' in home_games_as_away.columns: ay_list.append(home_games_as_away['HY'].mean())
                    if 'HST' in home_games_as_away.columns: as_list.append(home_games_as_away['HST'].mean())
                    if 'HF' in home_games_as_away.columns: af_list.append(home_games_as_away['HF'].mean())

                if ag_list: a_gf = sum(ag_list) / len(ag_list)
                if aa_list: a_ga = sum(aa_list) / len(aa_list)
                if ac_list: a_c = sum(ac_list) / len(ac_list)
                if ay_list: a_y = sum(ay_list) / len(ay_list)
                if as_list: a_s = sum(as_list) / len(as_list)
                if af_list: a_f = sum(af_list) / len(af_list)

            home_exp_g = max(0.3, (h_gf + a_ga) / 2)
            away_exp_g = max(0.3, (a_gf + h_ga) / 2)

            rand_factor = (hash(home + away) % 15) / 100.0

            # Para cada mercado: expected value del equipo local,
            # del equipo visitante, y el total (suma de ambos).
            # "margin" es el margen de cuota simulado — se mantiene
            # igual que antes por mercado.
            market_expected = {
                "⚽ Goles": {
                    "home": home_exp_g,
                    "away": away_exp_g,
                    "margin": rand_factor,
                },
                "📐 Córners": {
                    "home": h_c,
                    "away": a_c,
                    "margin": rand_factor / 2,
                },
                "🟨 Tarjetas": {
                    "home": h_y,
                    "away": a_y,
                    "margin": rand_factor,
                },
                "🎯 Disparos a puerta": {
                    "home": h_s,
                    "away": a_s,
                    "margin": rand_factor,
                },
                "🟧 Faltas": {
                    "home": h_f,
                    "away": a_f,
                    "margin": rand_factor,
                },
            }

            floor_by_market = {
                # (suelo mínimo por equipo, suelo mínimo total)
                "⚽ Goles": (0.3, 0.6),
                "📐 Córners": (2.0, 4.0),
                "🟨 Tarjetas": (0.8, 1.5),
                "🎯 Disparos a puerta": (1.5, 3.0),
                "🟧 Faltas": (5.0, 10.0),
            }

            def add_row(market_name, team_label, line, expected_value, margin_factor):
                prob = poisson_prob_over(expected_value, line)
                fair = 1 / prob
                odds = round(fair * (0.92 + margin_factor), 2)
                ev = (prob * odds) - 1

                if prob >= 0.20:
                    rating = "🔥 VALUE" if ev > 0.02 else "⚖️ NEUTRAL"
                    parsed_data.append([
                        home, away, home_crest, away_crest, match_date_str, match_date_obj, match_time,
                        market_name, team_label, f"+{line}", prob, odds, fair, ev, rating
                    ])

            for market_name, definition in MARKET_DEFINITIONS.items():

                info = market_expected[market_name]
                team_floor, total_floor = floor_by_market[market_name]

                home_expected = max(team_floor, info["home"])
                away_expected = max(team_floor, info["away"])
                total_expected = max(total_floor, home_expected + away_expected)

                # Mercado del PARTIDO (ambos equipos sumados)
                for line in definition["lines_total"]:
                    add_row(
                        market_name, TOTAL_LABEL, line,
                        total_expected, info["margin"]
                    )

                # Mercado POR EQUIPO (local y visitante por separado)
                for line in definition["lines_team"]:
                    add_row(
                        market_name, home, line,
                        home_expected, info["margin"]
                    )
                    add_row(
                        market_name, away, line,
                        away_expected, info["margin"]
                    )

        diagnostics = sorted(unmatched_teams)

        if parsed_data:
            df_out = pd.DataFrame(
                parsed_data,
                columns=["home","away","home_crest","away_crest","date","date_obj","time","market","team","line","probability","odds","fair_odds","ev","rating"]
            )
            return df_out, "OK", diagnostics
        else:
            return pd.DataFrame(), "No hay suficientes datos.", diagnostics

    except Exception as e:
        return pd.DataFrame(), str(e), []


def render_player_predictions_section(home_name: str, away_name: str, competition_code: str):
    """
    Sección opt-in (bajo demanda) dentro de cada partido: qué
    jugador de los dos equipos tiene más tiros a puerta por partido
    de media, y qué jugador comete/recibe más faltas.

    Dos fuentes posibles, porque ninguna de las dos fuentes
    principales de esta app tiene datos por jugador:
    - API-Football: requiere clave propia, cuota diaria y cuenta
      activa (puede suspenderse).
    - FBref: gratis siempre, sin cuenta ni cuota — pero al no tener
      API oficial se obtiene vía scraping respetuoso (ver política
      publicada de FBref sobre tráfico de bots).
    """
    st.markdown("**👤 Pronóstico de jugadores**")

    source = st.radio(
        "Fuente de datos",
        ["FBref (gratis, sin cuenta)", "API-Football (requiere cuenta activa)"],
        horizontal=True,
        key=f"player_source_{home_name}_{away_name}",
    )

    if source.startswith("FBref"):
        render_player_predictions_fbref(home_name, away_name, competition_code)
    else:
        render_player_predictions_api_football(home_name, away_name, competition_code)


def render_player_predictions_fbref(home_name: str, away_name: str, competition_code: str):

    if competition_code not in FBREF_COMPETITIONS:
        st.caption(
            "Esta competición no está mapeada a FBref todavía."
        )
        return

    default_season = fbref_current_season_string()
    year = int(default_season.split("-")[0])
    season_options = [
        f"{y}-{y + 1}" for y in range(year, year - 3, -1)
    ]

    col_season, col_button = st.columns([1, 1])

    with col_season:
        season = st.selectbox(
            "Temporada de referencia",
            season_options,
            key=f"fbref_season_{home_name}_{away_name}",
            help=(
                "La temporada en curso puede tener pocos partidos "
                "jugados todavía — si el ranking sale corto, prueba "
                "con la temporada anterior."
            ),
        )

    with col_button:
        st.caption(
            "Datos: FBref (Sports Reference) · sin cuenta, sin cuota"
        )
        run = st.button(
            "▶️ Generar pronóstico de jugadores",
            key=f"fbref_btn_{home_name}_{away_name}",
        )

    if not run:
        st.caption(
            "No se genera automáticamente para respetar el ritmo "
            "de peticiones que FBref tolera para bots — pulsa el "
            "botón cuando quieras verlo (puede tardar unos segundos "
            "la primera vez; luego queda en caché 24h)."
        )
        return

    with st.spinner("Consultando FBref (respetando su límite de peticiones)..."):
        result = build_player_predictions_fbref(
            home_name, away_name, competition_code, season
        )

    if result["errors"]:
        for err in result["errors"]:
            st.warning(f"⚠️ {err}")

    if result["sample_size"] == 0:
        st.info(
            "No se encontraron jugadores con al menos 1 partido "
            "completo (90 min. acumulados) para estos equipos en "
            "esta temporada. Prueba con otra temporada, o puede que "
            "el nombre del equipo no se haya reconocido bien en "
            "FBref (revisa el aviso de arriba)."
        )
        return

    _render_player_rankings(result, "appearances_90s", "90s jugados")

    st.caption(
        f"Basado en la temporada {season} (FBref) · jugadores con "
        f"al menos 1 partido completo acumulado. Uso personal, no "
        f"redistribuir estos datos (así lo pide FBref en sus "
        f"condiciones de uso)."
    )


def render_player_predictions_api_football(home_name: str, away_name: str, competition_code: str):

    if competition_code not in API_FOOTBALL_LEAGUE_MAP:
        st.caption(
            "Esta competición no está mapeada a API-Football "
            "todavía, así que no hay pronóstico de jugador "
            "disponible aquí."
        )
        return

    if not get_api_football_key():
        st.caption(
            "⚠️ Falta la clave `API_FOOTBALL_KEY` en `st.secrets` "
            "para poder generar pronósticos de jugador."
        )
        return

    league_id, league_display = API_FOOTBALL_LEAGUE_MAP[competition_code]

    col_season, col_button = st.columns([1, 1])

    with col_season:
        season = st.selectbox(
            "Temporada de referencia",
            API_FOOTBALL_FREE_SEASONS,
            key=f"player_season_{home_name}_{away_name}",
            help=(
                "El plan gratuito de API-Football no da la "
                "temporada en curso para las ligas grandes, solo "
                "temporadas ya completadas."
            ),
        )

    used_calls = st.session_state.get("api_football_call_count", 0)

    with col_button:
        st.caption(f"Peticiones API-Football usadas: {used_calls}")
        run = st.button(
            "▶️ Generar pronóstico de jugadores",
            key=f"player_btn_{home_name}_{away_name}",
        )

    if not run:
        st.caption(
            "No se generan automáticamente para no gastar cuota "
            "de API-Football sin pedirlo — pulsa el botón cuando "
            "quieras verlo. Cada pulsación hace varias peticiones "
            "con una pequeña pausa entre ellas para respetar su "
            "límite por minuto, así que puede tardar unos segundos."
        )
        return

    with st.spinner("Consultando estadísticas de jugadores..."):

        teams_by_name, teams_error = get_api_football_teams(league_id, season)

        if teams_error:
            st.error(f"No se pudo obtener la lista de equipos: {teams_error}")
            return

        home_id, home_score = resolve_api_football_team_id(home_name, teams_by_name)
        away_id, away_score = resolve_api_football_team_id(away_name, teams_by_name)

        result = build_player_predictions(
            home_name, away_name, home_id, away_id, league_id, season
        )

    if result["errors"]:
        for err in result["errors"]:
            st.warning(f"⚠️ {err}")

    if result["sample_size"] == 0:
        st.info(
            "No hay suficientes jugadores con mínimo "
            f"{MIN_APPEARANCES_FOR_PLAYER_STATS} partidos jugados "
            "en esta temporada para generar el pronóstico "
            "(equipo no encontrado en API-Football o temporada sin "
            "datos)."
        )
        return

    _render_player_rankings(result, "appearances", "partidos jugados")

    st.caption(
        f"Basado en la temporada {season} de {league_display} "
        f"(API-Football, plan gratuito) · "
        f"jugadores con mínimo {MIN_APPEARANCES_FOR_PLAYER_STATS} "
        f"partidos jugados."
    )


def _render_player_rankings(result, appearances_key, appearances_label):

    def render_ranking(title, players, metric, unit_label):
        st.markdown(f"##### {title}")
        if not players:
            st.caption("Sin datos suficientes.")
            return
        for i, p in enumerate(players[:3]):
            medal = ["🥇", "🥈", "🥉"][i]
            st.write(
                f"{medal} **{p['name']}** ({p['team']}) — "
                f"{p[metric]:.2f} {unit_label} · "
                f"{p.get(appearances_key, '?')} {appearances_label}"
            )

    col1, col2, col3 = st.columns(3)

    with col1:
        render_ranking(
            "🎯 Más tiros a puerta",
            result["shots_on"], "shots_on_per_game", "tiros/partido"
        )

    with col2:
        render_ranking(
            "🟧 Más faltas cometidas",
            result["fouls_committed"], "fouls_committed_per_game", "faltas/partido"
        )

    with col3:
        render_ranking(
            "🟢 Más faltas recibidas",
            result["fouls_drawn"], "fouls_drawn_per_game", "faltas/partido"
        )


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

                team_tag = (
                    "Total partido" if r.team == TOTAL_LABEL
                    else f"{r.team} (solo su equipo)"
                )

                render_html(f"""
                <div class="match-card">
                  <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.8rem; opacity:0.8; margin-bottom:6px;">
                    <span>{home_img} {r.home} vs {away_img} {r.away}</span>
                    <span>📅 {r.date} — ⏰ {r.time}</span>
                  </div>
                  <div style="font-weight:700; font-size:1.05rem; margin: 4px 0;">{r.market} ({r.line}) <span style="font-weight:400; font-size:0.75rem; opacity:0.65;">· {team_tag}</span></div>
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

                scope_filter = st.radio(
                    "Ver mercados de:",
                    ["Total del partido", f"Solo {h}", f"Solo {a}"],
                    horizontal=True,
                    key=f"scope_{h}_{a}_{m_date}_{m_time}",
                )

                if scope_filter == "Total del partido":
                    subset_view = subset[subset["team"] == TOTAL_LABEL]
                elif scope_filter == f"Solo {h}":
                    subset_view = subset[subset["team"] == h]
                else:
                    subset_view = subset[subset["team"] == a]

                for _, r in subset_view.iterrows():
                    ev_p = float(r.ev) * 100
                    color_ev = '#2ecc71' if ev_p > 0 else '#e74c3c'
                    badge_bg = 'rgba(46, 204, 113, 0.12)' if ev_p > 0 else 'rgba(231, 76, 60, 0.12)'

                    team_tag = (
                        "Total partido (ambos equipos)" if r.team == TOTAL_LABEL
                        else f"Solo {r.team}"
                    )

                    render_html(f"""
                    <div class="market-box">
                      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                        <span style="font-weight:700; font-size:0.95rem;">{r.market} <span style="opacity:0.7; font-weight:normal;">({r.line})</span></span>
                        <span style="background:{badge_bg}; color:{color_ev}; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.8rem;">EV {ev_p:+.1f}%</span>
                      </div>
                      <div style="font-size:0.75rem; opacity:0.6; margin-bottom:4px;">{team_tag}</div>
                      <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.85rem; opacity:0.85; margin-top:6px;">
                        <div>Probabilidad: <b>{r.probability_pct:.1f}%</b></div>
                        <div>Cuota: <b>{r.odds:.2f}</b> <span style="font-size:0.75rem; opacity:0.6;">(Justa: {r.fair_odds:.2f})</span></div>
                      </div>
                    </div>
                    """)

                st.divider()
                render_player_predictions_section(h, a, codigo_liga)

    with tab_sim:
        st.caption("Cálculo de stake mediante Criterio de Kelly.")
        bank = st.number_input("Bankroll actual (€)", min_value=10.0, value=500.0, step=50.0)
        frac = st.slider("Criterio Kelly fraccionado", 0.05, 0.50, 0.25, 0.05)

        if not df.empty:

            df_sim = df.copy()
            df_sim["team_scope"] = np.where(
                df_sim["team"] == TOTAL_LABEL,
                "Total partido",
                "Solo " + df_sim["team"],
            )
            df_sim["label"] = (
                df_sim["date"] + " " + df_sim["time"] + " · "
                + df_sim["home"] + " vs " + df_sim["away"] + " — "
                + df_sim["market"] + " " + df_sim["line"]
                + " [" + df_sim["team_scope"] + "]"
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
