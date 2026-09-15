import csv
import os

from get_design import (
    create_authenticated_session,
    get_roles_data,
    parse_person_name,
    render_html_rows,
)


def _format_role_label(season_role: dict) -> str:
    role = season_role.get("role") or ""
    competition = season_role.get("competition") or ""
    if role and competition:
        return f"{role} {competition}"
    return role or competition


def _rows_from_roles_lookup(roster, roles_lookup):
    rows = []
    for person_id, nom_complet in sorted(roster.items(), key=lambda item: item[1]):
        last_name, first_name = parse_person_name(nom_complet)
        for season_role in roles_lookup.get(person_id, []):
            rows.append([
                person_id,
                last_name,
                first_name,
                season_role.get("role") or "",
                season_role.get("competition") or "",
                season_role.get("phase") or "",
                season_role.get("saison") or "",
            ])
    return rows


def main() -> None:
    current_saison = int(os.environ.get("DESIGNATION_SAISON", 2027))
    force_refresh = os.environ.get("DESIGNATION_FORCE_REFRESH", "0") == "1"
    session = create_authenticated_session() if force_refresh else None

    roster, roles_lookup = get_roles_data(
        session=session,
        current_saison=current_saison,
    )
    if force_refresh:
        print("Fetched", len(roles_lookup), "officials with roles (forced refresh)")
    else:
        print("Loaded roles for", len(roles_lookup), "officials")

    headers = ["Personne ID", "Nom", "Prénom", "Rôle", "Compétition", "Phase", "Saison"]
    rows = _rows_from_roles_lookup(roster, roles_lookup)
    print("Processed", len(rows), "role rows")

    with open("template_roles.html", "r", encoding="utf-8") as f:
        html_content = f.read()
    with open("data/roles.html", "w", encoding="utf-8") as f:
        f.write(html_content.replace("%DATA%", render_html_rows(rows)))

    with open("data/roles.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)


if __name__ == "__main__":
    main()
