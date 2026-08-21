import csv
import json
import os
from pathlib import Path

from get_design import (
    build_designation_export_rows,
    create_authenticated_session,
    fetch_designations,
    fetch_person_distances,
    render_html_rows,
)


DISTANCE_CACHE_PATH = Path("data/distances_cache.json")


def _build_distance_lookup(session, designations):
    person_ids = set()
    for designation in designations:
        for officiel in designation.get("rencontre_officiels", []):
            person = officiel.get("personne", {})
            person_id = person.get("id")
            if person_id is not None:
                person_ids.add(int(person_id))

    distance_lookup = {}
    cached_distances = _load_distance_cache()
    for person_id in sorted(person_ids):
        cached_distance_map = cached_distances.get(str(person_id))
        if cached_distance_map is not None:
            distance_lookup[person_id] = {int(lieu_id): distance for lieu_id, distance in cached_distance_map.items()}
            continue
        try:
            person_distance_map, _ = fetch_person_distances(session, person_id)
        except Exception as exc:
            print(f"Warning: could not fetch distances for person {person_id}: {exc}")
            continue
        distance_lookup[person_id] = person_distance_map
        cached_distances[str(person_id)] = {str(lieu_id): distance for lieu_id, distance in person_distance_map.items()}

    _save_distance_cache(cached_distances)
    return distance_lookup


def _load_distance_cache():
    if not DISTANCE_CACHE_PATH.exists():
        return {}
    try:
        with open(DISTANCE_CACHE_PATH, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            distances = payload.get("distances", payload)
            if isinstance(distances, dict):
                return distances
    except Exception as exc:
        print(f"Warning: could not read distance cache: {exc}")
    return {}


def _save_distance_cache(cached_distances):
    DISTANCE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "distances": cached_distances,
    }
    with open(DISTANCE_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)


def main() -> None:
    session = create_authenticated_session()
    max_pages_env = os.environ.get("DESIGNATION_MAX_PAGES")
    max_pages = int(max_pages_env) if max_pages_env else None
    designations = fetch_designations(session, max_pages=max_pages)
    print("Fetched", len(designations), "designations")

    distance_lookup = _build_distance_lookup(session, designations)
    lines = build_designation_export_rows(designations, distance_lookup)
    print("Processed", len(lines), "designation rows")

    headers = ["Compétition", "Phase", "Date", "Heure", "Lieu", "Type d'Équipe", "Équipe", "Rôle", "Nom", "Prénom", "Distance (km)"]

    with open("template_design.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    with open("data/designations.html", "w", encoding="utf-8") as f:
        f.write(html_content.replace("%DATA%", render_html_rows(lines)))

    with open("data/designations.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(lines)


if __name__ == "__main__":
    main()