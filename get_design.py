import html
import logging
import os
import re
from typing import Any, Sequence
from urllib.parse import unquote

import requests
from dotenv import load_dotenv

BASE_URL = "https://hockeynet.fr"
CSRF_REFEX = r'name="csrf-token" content="([^"]+)"'
EXCLUDED_ROLE_LABELS = {"Secrétaire de match", "Chronométreur"}

DEFAULT_DESIGNATION_FILTER = {
    "etat": None,
    "competitions_ids": [],
    "phases_ids": [],
    "dates": {},
    "role_id": None,
    "etat_rencontre": None,
    "lieu_pratique": None,
    "horaire": None,
    "libelle": None,
    "saison": 2027,
    "perPage": 200,
    "discipline_code": "HG",
    "show_all": False,
}


def extractToken(page: str) -> str:
    token = re.findall(CSRF_REFEX, page)
    if len(token) == 0:
        logging.error("Could not find token")
        raise Exception("Could not find token")
    return token[0]


def _session_headers() -> dict:
    return {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/112.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Host": "hockeynet.fr",
        "Referer": BASE_URL + "/",
    }


def _xsrf_header(s: requests.Session) -> str:
    token = s.cookies.get("XSRF-TOKEN") or ""
    return unquote(token)


def _xhr_headers(s: requests.Session) -> dict:
    return {
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest",
        "X-XSRF-TOKEN": _xsrf_header(s),
    }


def sendRequest(
    s: requests.Session,
    url: str,
    method: str,
    data: dict[str, Any] | None = None,
    *,
    json_data: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> requests.Response:
    headers = _session_headers()
    if extra_headers:
        headers.update(extra_headers)
    page = s.request(
        method,
        url,
        headers=headers,
        data=data,
        json=json_data,
        timeout=20,
    )
    try:
        page.raise_for_status()
    except Exception as e:
        logging.exception(f"An error occured while fetching {url}")
        raise e
    return page


def create_authenticated_session() -> requests.Session:
    load_dotenv()
    debug_enabled = os.environ.get("HOCKEYNET_DEBUG", "0") == "1"
    logging.getLogger().handlers.clear()
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.DEBUG if debug_enabled else logging.INFO)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG if debug_enabled else logging.WARNING)
    requests_log.propagate = debug_enabled

    s = requests.Session()
    login_page = sendRequest(s, BASE_URL + "/auth/login", "GET")
    sendRequest(
        s,
        BASE_URL + "/auth/login",
        "POST",
        data={
            "_token": extractToken(login_page.text),
            "username": os.environ.get("HOCKEYNET_USER", "225544"),
            "password": os.environ.get("HOCKEYNET_PASSWORD", "PASSWORD"),
        },
    )
    sendRequest(s, BASE_URL + "/arbitrage/designation", "GET")
    return s


def request_designation_page(s: requests.Session, page_number: int) -> dict:
    response = s.request(
        "POST",
        BASE_URL + "/arbitrage/designation/query",
        params={"page": page_number},
        json=DEFAULT_DESIGNATION_FILTER,
        headers={**_session_headers(), **_xhr_headers(s)},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def fetch_designation_pages(s: requests.Session, max_pages: int | None = None) -> list[dict]:
    first_page = request_designation_page(s, 1)
    pages = [first_page]
    last_page = int(first_page.get("meta", {}).get("last_page", 1) or 1)
    if max_pages is not None:
        last_page = min(last_page, max_pages)
    for page_number in range(2, last_page + 1):
        pages.append(request_designation_page(s, page_number))
    return pages


def fetch_designations(s: requests.Session, max_pages: int | None = None) -> list[dict]:
    pages = fetch_designation_pages(s, max_pages=max_pages)
    designations = []
    for page in pages:
        designations.extend(page.get("data", []))
    return designations


def fetch_person_distances(s: requests.Session, person_id: int | str) -> tuple[dict, dict]:
    payload = s.request(
        "GET",
        f"{BASE_URL}/arbitrage/{person_id}/distances/init",
        headers={**_session_headers(), **_xhr_headers(s)},
        timeout=20,
    )
    payload.raise_for_status()
    data = payload.json()
    distance_map = {}
    for row in data.get("personneDistances", []):
        lieu_id = row.get("lieu_pratique_id")
        if lieu_id is None:
            continue
        distance_map[lieu_id] = row.get("distance")
    return distance_map, data


def fetch_person_indisponibilites(s: requests.Session, person_id: int | str) -> dict:
    payload = s.request(
        "GET",
        f"{BASE_URL}/arbitrage/{person_id}/indisponibilites/init",
        headers={**_session_headers(), **_xhr_headers(s)},
        timeout=20,
    )
    payload.raise_for_status()
    return payload.json()


def parse_person_name(nom_complet: str) -> tuple[str, str]:
    if not nom_complet:
        return "", ""
    cleaned = nom_complet.strip()
    match = re.match(r"^(?:M(?:me)?\.?\s+)?([A-ZÀ-ÖØ-Ý'\- ]+)\s+(.+)$", cleaned)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    tokens = cleaned.split()
    if len(tokens) >= 3 and tokens[0] in {"M", "Mme", "Mme."}:
        return tokens[1], " ".join(tokens[2:])
    if len(tokens) >= 2:
        return tokens[0], " ".join(tokens[1:])
    return cleaned, ""


def _build_role_label_lookup(designation: dict) -> dict[int, str]:
    role_lookup: dict[int, str] = {}
    competition_officiels = (
        designation.get("phase", {})
        .get("competition_maitre", {})
        .get("competition_officiels", [])
    )
    for officiel in competition_officiels:
        officiel_id = officiel.get("officiel_id")
        libelle = officiel.get("libelle")
        if officiel_id is None or not libelle:
            continue
        try:
            role_lookup[int(officiel_id)] = str(libelle)
        except Exception:
            continue
    return role_lookup


def _resolve_role_label(officiel: dict, role_lookup: dict[int, str]) -> str:
    role_id = officiel.get("officiel_id")
    if role_id is None:
        role_id = officiel.get("role_id")
    if role_id is not None:
        try:
            role_id = int(role_id)
        except Exception:
            return "Officiel"
        if role_id in role_lookup:
            return role_lookup[role_id]
        return f"Officiel {role_id}"
    return "Officiel"


def _split_teams(rencontre_libelle: str) -> tuple[str, str]:
    if not rencontre_libelle:
        return "", ""
    teams = rencontre_libelle.split(" / ", 1)
    if len(teams) != 2:
        return rencontre_libelle, ""
    return teams[0], teams[1]


def build_designation_export_rows(designations: list[dict], distance_lookup: dict[int, dict]) -> list[list[str]]:
    rows: list[list[str]] = []
    for designation in designations:
        competition = designation.get("competition", {}).get("libelle", "")
        phase = designation.get("phase", {}).get("libelle", "")
        date = designation.get("date", "")
        heure = designation.get("heure", "")
        lieu = designation.get("lieu_pratique", {}).get("nom", "")
        lieu_id = designation.get("lieu_pratique", {}).get("id")
        rencontre_home, rencontre_away = _split_teams(designation.get("rencontre_libelle", ""))
        rencontre_officiels = designation.get("rencontre_officiels", [])
        role_lookup = _build_role_label_lookup(designation)

        for team_label, team_name in (("Domicile", rencontre_home), ("Visiteur", rencontre_away)):
            for officiel in rencontre_officiels:
                role_label = _resolve_role_label(officiel, role_lookup)
                if role_label in EXCLUDED_ROLE_LABELS:
                    continue
                person = officiel.get("personne", {})
                person_id = person.get("id")
                last_name, first_name = parse_person_name(person.get("nom_complet") or "")
                distance = ""
                if person_id is not None and lieu_id is not None:
                    distance = distance_lookup.get(int(person_id), {}).get(lieu_id, "")
                rows.append([
                    competition,
                    phase,
                    date,
                    heure,
                    lieu,
                    team_label,
                    team_name,
                    role_label,
                    last_name,
                    first_name,
                    distance,
                ])
    return rows


def render_html_rows(rows: Sequence[Sequence[object]]) -> str:
    return "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
        for row in rows
    )


def main() -> list[dict]:
    session = create_authenticated_session()
    return fetch_designations(session)


if __name__ == "__main__":
    main()