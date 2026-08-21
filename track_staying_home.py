from collections import defaultdict
from datetime import datetime

from get_design import (
    create_authenticated_session,
    fetch_designations,
    fetch_person_indisponibilites,
    parse_person_name,
)


MONTHS = [
    "Janvier",
    "Février",
    "Mars",
    "Avril",
    "Mai",
    "Juin",
    "Juillet",
    "Août",
    "Septembre",
    "Octobre",
    "Novembre",
    "Décembre",
]


def parse_date(date_str):
    return datetime.strptime(date_str, "%d/%m/%Y")


def get_month_name(date_str):
    dt = parse_date(date_str)
    return MONTHS[dt.month - 1]


def _parse_indispo_bounds(indispo):
    dates = indispo.get("dates", {})
    start_date = dates.get("startDate")
    end_date = dates.get("endDate") or start_date
    if not start_date:
        return None, None
    return parse_date(start_date), parse_date(end_date)


def _is_indisponible_on(date_str, indisponibilites):
    target_date = parse_date(date_str)
    for indispo in indisponibilites:
        start_date, end_date = _parse_indispo_bounds(indispo)
        if start_date is None or end_date is None:
            continue
        if start_date <= target_date <= end_date:
            return True
    return False


def _build_person_roster(designations):
    roster = {}
    for designation in designations:
        for officiel in designation.get("rencontre_officiels", []):
            person = officiel.get("personne", {})
            person_id = person.get("id")
            if person_id is None:
                continue
            person_id = int(person_id)
            roster[person_id] = person.get("nom_complet") or person.get("nom") or ""
    return roster


def _fetch_indisponibilites_for_roster(session, person_ids):
    indisponibilites_by_person = {}
    for person_id in sorted(person_ids):
        try:
            payload = fetch_person_indisponibilites(session, person_id)
        except Exception as exc:
            print(f"Warning: could not fetch indisponibilites for person {person_id}: {exc}")
            continue
        indisponibilites_by_person[person_id] = payload.get("indisponibilites", [])
    return indisponibilites_by_person


def main():
    session = create_authenticated_session()
    designations = fetch_designations(session)
    print(f"Fetched {len(designations)} games")

    games = []
    slm_refs = defaultdict(int)

    for designation in designations:
        competition = designation.get("competition", {}).get("libelle", "")
        phase = designation.get("phase", {}).get("libelle", "")
        date = designation.get("date", "")
        time = designation.get("heure", "")
        location = designation.get("lieu_pratique", {}).get("nom", "")
        teams = designation.get("rencontre_libelle", "")

        refs = []
        for officiel in designation.get("rencontre_officiels", []):
            person = officiel.get("personne", {})
            person_id = person.get("id")
            if person_id is None:
                continue
            person_id = int(person_id)
            refs.append((person_id, person.get("nom_complet") or person.get("nom") or ""))

        games.append(
            {
                "competition": competition,
                "phase": phase,
                "date": date,
                "time": time,
                "location": location,
                "teams": teams,
                "refs": refs,
            }
        )

        if competition == "Synerglace Ligue Magnus":
            for ref in refs:
                slm_refs[ref] += 1

    slm_refs_qualified = {ref for ref, count in slm_refs.items() if count >= 3}
    print(f"\nFound {len(slm_refs_qualified)} SLM refs with at least 3 games")

    roster = _build_person_roster(designations)
    indisponibilites_by_person = _fetch_indisponibilites_for_roster(session, roster.keys())

    games_by_date = defaultdict(list)
    for game in games:
        games_by_date[game["date"]].append(game)

    print("\n" + "=" * 80)
    print("ANALYSIS OF DAYS WITH 5+ SLM GAMES")
    print("=" * 80)

    sorted_dates = sorted(games_by_date.keys(), key=parse_date)

    daily_stats = []
    monthly_stats = defaultdict(lambda: {
        "total_slm_refs_not_on_slm": 0,
        "total_staying_home": 0,
        "total_indisponible": 0,
        "total_working_other": 0,
        "total_slm_refs_on_slm": 0,
        "days_count": 0,
        "total_slm_games": 0,
    })

    global_stats = {
        "total_slm_refs_not_on_slm": 0,
        "total_staying_home": 0,
        "total_indisponible": 0,
        "total_working_other": 0,
        "total_slm_refs_on_slm": 0,
        "days_count": 0,
        "total_slm_games": 0,
    }

    for date in sorted_dates:
        date_games = games_by_date[date]
        slm_games = [g for g in date_games if g["competition"] == "Synerglace Ligue Magnus"]

        if len(slm_games) >= 5:
            slm_refs_on_slm_games = set()
            non_slm_refs_on_slm_games = set()

            for game in slm_games:
                for ref in game["refs"]:
                    if ref in slm_refs_qualified:
                        slm_refs_on_slm_games.add(ref)
                    else:
                        non_slm_refs_on_slm_games.add(ref)

            slm_refs_on_other_games = set()
            for game in date_games:
                if game["competition"] != "Synerglace Ligue Magnus":
                    for ref in game["refs"]:
                        if ref in slm_refs_qualified:
                            slm_refs_on_other_games.add(ref)

            all_refs_working = set()
            for game in date_games:
                for ref in game["refs"]:
                    if ref in slm_refs_qualified:
                        all_refs_working.add(ref)

            slm_refs_not_on_slm = slm_refs_qualified - slm_refs_on_slm_games
            slm_refs_staying_home_all = slm_refs_qualified - all_refs_working
            slm_refs_indisponible = {
                ref
                for ref in slm_refs_staying_home_all
                if _is_indisponible_on(date, indisponibilites_by_person.get(ref[0], []))
            }
            slm_refs_staying_home = slm_refs_staying_home_all - slm_refs_indisponible

            total_slm_refs = len(slm_refs_qualified)
            pct_not_on_slm = (len(slm_refs_not_on_slm) / total_slm_refs * 100) if total_slm_refs > 0 else 0
            pct_staying_home = (len(slm_refs_staying_home) / total_slm_refs * 100) if total_slm_refs > 0 else 0

            day_stat = {
                "date": date,
                "total_slm_games": len(slm_games),
                "slm_refs_on_slm": len(slm_refs_on_slm_games),
                "non_slm_refs_on_slm": len(non_slm_refs_on_slm_games),
                "slm_refs_not_on_slm": len(slm_refs_not_on_slm),
                "staying_home": len(slm_refs_staying_home),
                "indisponible": len(slm_refs_indisponible),
                "working_other": len(slm_refs_on_other_games),
                "pct_not_on_slm": pct_not_on_slm,
                "pct_staying_home": pct_staying_home,
                "staying_home_list": sorted(slm_refs_staying_home),
                "indisponible_list": sorted(slm_refs_indisponible),
                "working_other_list": sorted(slm_refs_on_other_games),
                "working_other_details": {},
            }

            for ref in slm_refs_on_other_games:
                competitions = set()
                for game in date_games:
                    if game["competition"] != "Synerglace Ligue Magnus" and ref in game["refs"]:
                        competitions.add(game["competition"])
                day_stat["working_other_details"][ref] = competitions

            daily_stats.append(day_stat)

            month_name = get_month_name(date)
            monthly_stats[month_name]["total_slm_refs_not_on_slm"] += len(slm_refs_not_on_slm)
            monthly_stats[month_name]["total_staying_home"] += len(slm_refs_staying_home)
            monthly_stats[month_name]["total_indisponible"] += len(slm_refs_indisponible)
            monthly_stats[month_name]["total_working_other"] += len(slm_refs_on_other_games)
            monthly_stats[month_name]["total_slm_refs_on_slm"] += len(slm_refs_on_slm_games)
            monthly_stats[month_name]["days_count"] += 1
            monthly_stats[month_name]["total_slm_games"] += len(slm_games)

            global_stats["total_slm_refs_not_on_slm"] += len(slm_refs_not_on_slm)
            global_stats["total_staying_home"] += len(slm_refs_staying_home)
            global_stats["total_indisponible"] += len(slm_refs_indisponible)
            global_stats["total_working_other"] += len(slm_refs_on_other_games)
            global_stats["total_slm_refs_on_slm"] += len(slm_refs_on_slm_games)
            global_stats["days_count"] += 1
            global_stats["total_slm_games"] += len(slm_games)

            print(f"\n📅 Date: {date}")
            print(f"   Total SLM games: {len(slm_games)}")
            print(f"   SLM refs appointed to SLM games: {len(slm_refs_on_slm_games)}")
            print(f"   Non-SLM refs appointed to SLM games: {len(non_slm_refs_on_slm_games)}")
            print(f"   Total SLM refs non désigné en SLM: {len(slm_refs_not_on_slm)} ({pct_not_on_slm:.1f}%)")
            print(f"      - Staying home (no assignment, not indisponible): {len(slm_refs_staying_home)} ({pct_staying_home:.1f}%)")
            print(f"      - Indisponibles: {len(slm_refs_indisponible)}")
            print(f"      - Working other divisions: {len(slm_refs_on_other_games)}")

            if day_stat["staying_home_list"]:
                print(f"\n   📋 SLM refs staying home:")
                for ref in day_stat["staying_home_list"]:
                    print(f"      - {parse_person_name(ref[1])[0]} {parse_person_name(ref[1])[1]}")

            if day_stat["indisponible_list"]:
                print(f"\n   📋 SLM refs indisponibles:")
                for ref in day_stat["indisponible_list"]:
                    print(f"      - {parse_person_name(ref[1])[0]} {parse_person_name(ref[1])[1]}")

            if day_stat["working_other_list"]:
                print(f"\n   📋 SLM refs working other divisions:")
                for ref in day_stat["working_other_list"]:
                    competitions = day_stat["working_other_details"][ref]
                    print(f"      - {parse_person_name(ref[1])[0]} {parse_person_name(ref[1])[1]}: {', '.join(competitions)}")

    print("\n" + "=" * 80)
    print("GLOBAL STATISTICS")
    print("=" * 80)
    print(f"Total days analyzed: {global_stats['days_count']}")
    print(f"Total SLM games: {global_stats['total_slm_games']}")
    print(f"Average SLM games per day: {global_stats['total_slm_games'] / global_stats['days_count']:.1f}")
    if global_stats["days_count"] > 0:
        avg_not_on_slm = global_stats["total_slm_refs_not_on_slm"] / global_stats["days_count"]
        avg_staying_home = global_stats["total_staying_home"] / global_stats["days_count"]
        avg_indisponible = global_stats["total_indisponible"] / global_stats["days_count"]
        avg_working_other = global_stats["total_working_other"] / global_stats["days_count"]
        total_slm_refs = len(slm_refs_qualified)

        print(f"\nAverage per day:")
        print(f"  - SLM refs non désigné en SLM: {avg_not_on_slm:.1f} ({avg_not_on_slm/total_slm_refs*100:.1f}%)")
        print(f"  - SLM refs staying home: {avg_staying_home:.1f} ({avg_staying_home/total_slm_refs*100:.1f}%)")
        print(f"  - SLM refs indisponibles: {avg_indisponible:.1f}")
        print(f"  - SLM refs working other divisions: {avg_working_other:.1f}")

    print("\n" + "=" * 80)
    print("MONTHLY STATISTICS")
    print("=" * 80)

    month_order = MONTHS

    for month in month_order:
        if month in monthly_stats:
            stats = monthly_stats[month]
            print(f"\n{month}:")
            print(f"  Days with 5+ SLM games: {stats['days_count']}")
            print(f"  Total SLM games: {stats['total_slm_games']}")
            if stats["days_count"] > 0:
                avg_not_on_slm = stats["total_slm_refs_not_on_slm"] / stats["days_count"]
                avg_staying_home = stats["total_staying_home"] / stats["days_count"]
                avg_indisponible = stats["total_indisponible"] / stats["days_count"]
                avg_working_other = stats["total_working_other"] / stats["days_count"]
                total_slm_refs = len(slm_refs_qualified)

                print(f"  Average per day:")
                print(f"    - SLM refs non désigné en SLM: {avg_not_on_slm:.1f} ({avg_not_on_slm/total_slm_refs*100:.1f}%)")
                print(f"    - SLM refs staying home: {avg_staying_home:.1f} ({avg_staying_home/total_slm_refs*100:.1f}%)")
                print(f"    - SLM refs indisponibles: {avg_indisponible:.1f}")
                print(f"    - SLM refs working other divisions: {avg_working_other:.1f}")

    generate_html_report(daily_stats, global_stats, monthly_stats, slm_refs_qualified, month_order)
    print("\n✅ HTML report generated: data/staying_home.html")

def generate_html_report(daily_stats, global_stats, monthly_stats, slm_refs_qualified, month_order):
    """Generate HTML report with statistics"""
    total_slm_refs = len(slm_refs_qualified)
    
    content = """<h1>Statistiques Arbitres SLM - Absences sur Journées à 5+ Matchs</h1>
    
    <h2>Statistiques Globales</h2>
    <table>
        <thead>
            <tr>
                <th>Métrique</th>
                <th>Valeur</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Total arbitres SLM qualifiés (3+ matchs)</td>
                <td><span class="stats-highlight">%d</span></td>
            </tr>
            <tr>
                <td>Journées analysées (5+ matchs SLM)</td>
                <td><span class="stats-highlight">%d</span></td>
            </tr>
            <tr>
                <td>Total matchs SLM</td>
                <td><span class="stats-highlight">%d</span></td>
            </tr>
            <tr>
                <td>Moyenne matchs SLM par journée</td>
                <td><span class="stats-highlight">%.1f</span></td>
            </tr>
            <tr>
                <td>Moyenne arbitres SLM non désigné en SLM par journée</td>
                <td><span class="stats-highlight">%.1f</span> <span class="percentage">(%.1f%%)</span></td>
            </tr>
            <tr>
                <td>Moyenne arbitres SLM restant à domicile par journée</td>
                <td><span class="stats-highlight">%.1f</span> <span class="percentage">(%.1f%%)</span></td>
            </tr>
            <tr>
                <td>Moyenne arbitres SLM indisponibles par journée</td>
                <td><span class="stats-highlight">%.1f</span></td>
            </tr>
            <tr>
                <td>Moyenne arbitres SLM travaillant autres divisions par journée</td>
                <td><span class="stats-highlight">%.1f</span></td>
            </tr>
        </tbody>
    </table>
""" % (
        total_slm_refs,
        global_stats['days_count'],
        global_stats['total_slm_games'],
        global_stats['total_slm_games'] / global_stats['days_count'] if global_stats['days_count'] > 0 else 0,
        global_stats['total_slm_refs_not_on_slm'] / global_stats['days_count'] if global_stats['days_count'] > 0 else 0,
        (global_stats['total_slm_refs_not_on_slm'] / global_stats['days_count'] / total_slm_refs * 100) if global_stats['days_count'] > 0 else 0,
        global_stats['total_staying_home'] / global_stats['days_count'] if global_stats['days_count'] > 0 else 0,
        (global_stats['total_staying_home'] / global_stats['days_count'] / total_slm_refs * 100) if global_stats['days_count'] > 0 else 0,
        global_stats['total_indisponible'] / global_stats['days_count'] if global_stats['days_count'] > 0 else 0,
        global_stats['total_working_other'] / global_stats['days_count'] if global_stats['days_count'] > 0 else 0
    )
    
    # Monthly statistics
    content += "\n    <h2>Statistiques Mensuelles</h2>\n"
    content += """    <table>
        <thead>
            <tr>
                <th>Mois</th>
                <th>Journées</th>
                <th>Matchs SLM</th>
                <th>Moy. Non désigné en SLM</th>
                <th>% Non désigné en SLM</th>
                <th>Moy. Restant à domicile</th>
                <th>% Restant à domicile</th>
                <th>Moy. Indisponibles</th>
                <th>Moy. Autres divisions</th>
            </tr>
        </thead>
        <tbody>
"""
    
    for month in month_order:
        if month in monthly_stats:
            stats = monthly_stats[month]
            if stats['days_count'] > 0:
                avg_not_on_slm = stats['total_slm_refs_not_on_slm'] / stats['days_count']
                avg_staying_home = stats['total_staying_home'] / stats['days_count']
                avg_indisponible = stats['total_indisponible'] / stats['days_count']
                avg_working_other = stats['total_working_other'] / stats['days_count']
                
                content += f"""            <tr>
                <td><strong>{month}</strong></td>
                <td>{stats['days_count']}</td>
                <td>{stats['total_slm_games']}</td>
                <td>{avg_not_on_slm:.1f}</td>
                <td><span class="percentage">{avg_not_on_slm/total_slm_refs*100:.1f}%</span></td>
                <td>{avg_staying_home:.1f}</td>
                <td><span class="percentage">{avg_staying_home/total_slm_refs*100:.1f}%</span></td>
                <td>{avg_indisponible:.1f}</td>
                <td>{avg_working_other:.1f}</td>
            </tr>
"""
    
    content += """        </tbody>
    </table>
    
    <h2>Détails par Journée</h2>
"""
    
    # Daily details
    for day in daily_stats:
        content += f"""
    <details class="day-section">
        <summary style="cursor: pointer; font-size: 1.2em; font-weight: bold; padding: 10px; margin: -20px -20px 20px -20px; background-color: #3498db; color: white; border-radius: 5px 5px 0 0;">
            📅 {day['date']} - {day['total_slm_games']} matchs SLM - {day['staying_home']} arbitres à domicile hors indisponibilités ({day['pct_staying_home']:.1f}%)
        </summary>
        <table>
            <thead>
                <tr>
                    <th>Métrique</th>
                    <th>Valeur</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>Matchs SLM</td>
                    <td><span class="stats-highlight">{day['total_slm_games']}</span></td>
                </tr>
                <tr>
                    <td>Arbitres SLM désignés sur SLM</td>
                    <td><span class="stats-highlight">{day['slm_refs_on_slm']}</span></td>
                </tr>
                <tr>
                    <td>Arbitres non-SLM désignés sur SLM</td>
                    <td><span class="stats-highlight">{day['non_slm_refs_on_slm']}</span></td>
                </tr>
                <tr>
                    <td>Arbitres SLM non désigné en SLM</td>
                    <td><span class="stats-highlight">{day['slm_refs_not_on_slm']}</span> <span class="percentage">({day['pct_not_on_slm']:.1f}%)</span></td>
                </tr>
                <tr>
                    <td>Restant à domicile</td>
                    <td><span class="stats-highlight">{day['staying_home']}</span> <span class="percentage">({day['pct_staying_home']:.1f}%)</span></td>
                </tr>
                <tr>
                    <td>Indisponibles</td>
                    <td><span class="stats-highlight">{day['indisponible']}</span></td>
                </tr>
                <tr>
                    <td>Travaillant autres divisions</td>
                    <td><span class="stats-highlight">{day['working_other']}</span></td>
                </tr>
            </tbody>
        </table>
"""
        
        if day['staying_home_list']:
            content += f"""
        <details style="margin-top: 15px;">
            <summary style="cursor: pointer; font-size: 1.05em; font-weight: 600; color: #2c3e50;">
                🏠 Arbitres SLM restant à domicile hors indisponibilités ({len(day['staying_home_list'])})
            </summary>
            <ul>
"""
            for ref in day['staying_home_list']:
                content += f"                <li>{ref[0]} {ref[1]}</li>\n"
            content += "            </ul>\n        </details>\n"
        
        if day['working_other_list']:
            content += f"""
        <details style="margin-top: 15px;">
            <summary style="cursor: pointer; font-size: 1.05em; font-weight: 600; color: #2c3e50;">
                🔄 Arbitres SLM travaillant autres divisions ({len(day['working_other_list'])})
            </summary>
            <ul>
"""
            for ref in day['working_other_list']:
                competitions = ', '.join(day['working_other_details'][ref])
                content += f"                <li>{ref[0]} {ref[1]}: <em>{competitions}</em></li>\n"
            content += "            </ul>\n        </details>\n"
        
        content += "    </details>\n"
    
    # Load template and insert content
    with open("template_staying_home.html", 'r') as f:
        template = f.read()
    
    html = template.replace("%CONTENT%", content)
    
    with open("data/staying_home.html", "w") as f:
        f.write(html)

if __name__ == "__main__":
    main()
