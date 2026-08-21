import csv
from datetime import datetime

from get_design import (
    create_authenticated_session,
    fetch_designations,
    fetch_person_indisponibilites,
    parse_person_name,
    render_html_rows,
)


MOTIF_LABELS = {
    2: "Travail",
    3: "blessure",
    4: "vacances",
    5: "stage",
    6: "mondial",
    7: "Autre",
}


def _build_roster(designations):
    roster = {}
    for designation in designations:
        for officiel in designation.get("rencontre_officiels", []):
            person = officiel.get("personne", {})
            person_id = person.get("id")
            if person_id is None:
                continue
            person_id = int(person_id)
            roster[person_id] = {
                "nom_complet": person.get("nom_complet") or person.get("nom") or "",
            }
    return roster


def _parse_indispo_date(date_string):
    if not date_string:
        return None
    return datetime.strptime(date_string, "%d/%m/%Y")


def main():
    session = create_authenticated_session()
    designations = fetch_designations(session)
    roster = _build_roster(designations)

    rows = []
    for person_id, person_data in sorted(roster.items(), key=lambda item: item[1]["nom_complet"]):
        try:
            payload = fetch_person_indisponibilites(session, person_id)
        except Exception as exc:
            print(f"Warning: could not fetch indisponibilites for person {person_id}: {exc}")
            continue

        last_name, first_name = parse_person_name(person_data["nom_complet"])
        for indispo in payload.get("indisponibilites", []):
            dates = indispo.get("dates", {})
            start_date = dates.get("startDate", "")
            end_date = dates.get("endDate", "")
            rows.append([
                person_id,
                last_name,
                first_name,
                MOTIF_LABELS.get(indispo.get("motif_id"), indispo.get("motif_id", "")),
                start_date,
                end_date,
            ])

    rows.sort(key=lambda row: (
        row[1],
        row[2],
        _parse_indispo_date(row[4]) or datetime.max,
        _parse_indispo_date(row[5]) or datetime.max,
    ))

    headers = ["Personne ID", "Nom", "Prénom", "Motif", "Début", "Fin"]

    with open("template_indisponibilites.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    with open("data/indisponibilites.html", "w", encoding="utf-8") as f:
        f.write(html_content.replace("%DATA%", render_html_rows(rows)))

    with open("data/indisponibilites.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print("Processed", len(rows), "indisponibilite rows")


if __name__ == "__main__":
    main()