import csv
import re
from get_design import main as get_design
from datetime import datetime
from collections import defaultdict

def parse_referee_names(ref_string):
    """Extract referee names from a string like 'M DUPONT Jean, Mme MARTIN Marie'"""
    if not ref_string:
        return []
    
    refs = []
    refNames = ref_string.split(', ')
    for refName in refNames:
        refMatch = re.match(r"M(?:me)? ([A-Z \-']+) ([A-Z][\w \-']+)", refName)
        if refMatch:
            lastName = refMatch.group(1)
            firstName = refMatch.group(2)
            refs.append((lastName, firstName))
    return refs

def parse_date(date_str):
    """Parse date from DD/MM/YYYY format"""
    return datetime.strptime(date_str, "%d/%m/%Y")

def get_month_name(date_str):
    """Get month name from date string"""
    dt = parse_date(date_str)
    months = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
              'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    return months[dt.month - 1]

def main():
    # Get raw designations from get_design (1 row per game)
    designations = get_design().splitlines()
    print(f"Fetched {len(designations) - 1} games")
    
    reader = csv.reader(designations, delimiter=';', quotechar='"')
    next(reader)  # Skip header
    
    # Data structures
    games = []
    slm_refs = defaultdict(int)  # ref -> game count in SLM
    
    # Parse all games
    for row in reader:
        if len(row) < 7:
            continue
            
        competition = row[0]
        phase = row[1]
        date = row[2]
        time = row[3]
        location = row[4]
        teams = row[5]
        
        # Extract all referees from columns 6 onwards
        refs = []
        for col in range(6, 9):
            refs.extend(parse_referee_names(row[col]))
        
        game_data = {
            'competition': competition,
            'phase': phase,
            'date': date,
            'time': time,
            'location': location,
            'teams': teams,
            'refs': refs
        }
        games.append(game_data)
        
        # Count SLM refs
        if competition == 'Synerglace Ligue Magnus':
            for ref in refs:
                slm_refs[ref] += 1
    
    # Filter SLM refs with at least 3 games
    slm_refs_qualified = {ref for ref, count in slm_refs.items() if count >= 3}
    print(f"\nFound {len(slm_refs_qualified)} SLM refs with at least 3 games")
    
    # Group games by date
    games_by_date = defaultdict(list)
    for game in games:
        games_by_date[game['date']].append(game)
    
    # Analyze days with 3+ SLM games
    print("\n" + "="*80)
    print("ANALYSIS OF DAYS WITH 3+ SLM GAMES")
    print("="*80)
    
    # Sort dates properly
    sorted_dates = sorted(games_by_date.keys(), key=parse_date)
    
    # Store statistics for later aggregation
    daily_stats = []
    monthly_stats = defaultdict(lambda: {
        'total_slm_refs_not_on_slm': 0,
        'total_staying_home': 0,
        'total_working_other': 0,
        'total_slm_refs_on_slm': 0,
        'days_count': 0,
        'total_slm_games': 0
    })
    
    global_stats = {
        'total_slm_refs_not_on_slm': 0,
        'total_staying_home': 0,
        'total_working_other': 0,
        'total_slm_refs_on_slm': 0,
        'days_count': 0,
        'total_slm_games': 0
    }
    
    for date in sorted_dates:
        date_games = games_by_date[date]
        slm_games = [g for g in date_games if g['competition'] == 'Synerglace Ligue Magnus']
        
        if len(slm_games) >= 3:
            # Get all refs appointed on SLM games this day
            slm_refs_on_slm_games = set()
            non_slm_refs_on_slm_games = set()
            
            for game in slm_games:
                for ref in game['refs']:
                    if ref in slm_refs_qualified:
                        slm_refs_on_slm_games.add(ref)
                    else:
                        non_slm_refs_on_slm_games.add(ref)
            
            # Get SLM refs working on other competitions this day
            slm_refs_on_other_games = set()
            for game in date_games:
                if game['competition'] != 'Synerglace Ligue Magnus':
                    for ref in game['refs']:
                        if ref in slm_refs_qualified:
                            slm_refs_on_other_games.add(ref)
            
            # Get all refs with any appointment this day
            all_refs_working = set()
            for game in date_games:
                for ref in game['refs']:
                    if ref in slm_refs_qualified:
                        all_refs_working.add(ref)
            
            # Calculate staying home (not working at all)
            slm_refs_staying_home = slm_refs_qualified - all_refs_working
            
            # Calculate total not assigned on SLM
            slm_refs_not_on_slm = slm_refs_qualified - slm_refs_on_slm_games
            
            # Calculate percentages
            total_slm_refs = len(slm_refs_qualified)
            pct_not_on_slm = (len(slm_refs_not_on_slm) / total_slm_refs * 100) if total_slm_refs > 0 else 0
            pct_staying_home = (len(slm_refs_staying_home) / total_slm_refs * 100) if total_slm_refs > 0 else 0
            
            # Store stats for this day
            day_stat = {
                'date': date,
                'total_slm_games': len(slm_games),
                'slm_refs_on_slm': len(slm_refs_on_slm_games),
                'non_slm_refs_on_slm': len(non_slm_refs_on_slm_games),
                'slm_refs_not_on_slm': len(slm_refs_not_on_slm),
                'staying_home': len(slm_refs_staying_home),
                'working_other': len(slm_refs_on_other_games),
                'pct_not_on_slm': pct_not_on_slm,
                'pct_staying_home': pct_staying_home,
                'staying_home_list': sorted(slm_refs_staying_home),
                'working_other_list': sorted(slm_refs_on_other_games),
                'working_other_details': {}
            }
            
            # Get details of what competitions they're working
            for ref in slm_refs_on_other_games:
                competitions = set()
                for game in date_games:
                    if game['competition'] != 'Synerglace Ligue Magnus' and ref in game['refs']:
                        competitions.add(game['competition'])
                day_stat['working_other_details'][ref] = competitions
            
            daily_stats.append(day_stat)
            
            # Update monthly stats
            month_name = get_month_name(date)
            monthly_stats[month_name]['total_slm_refs_not_on_slm'] += len(slm_refs_not_on_slm)
            monthly_stats[month_name]['total_staying_home'] += len(slm_refs_staying_home)
            monthly_stats[month_name]['total_working_other'] += len(slm_refs_on_other_games)
            monthly_stats[month_name]['total_slm_refs_on_slm'] += len(slm_refs_on_slm_games)
            monthly_stats[month_name]['days_count'] += 1
            monthly_stats[month_name]['total_slm_games'] += len(slm_games)
            
            # Update global stats
            global_stats['total_slm_refs_not_on_slm'] += len(slm_refs_not_on_slm)
            global_stats['total_staying_home'] += len(slm_refs_staying_home)
            global_stats['total_working_other'] += len(slm_refs_on_other_games)
            global_stats['total_slm_refs_on_slm'] += len(slm_refs_on_slm_games)
            global_stats['days_count'] += 1
            global_stats['total_slm_games'] += len(slm_games)
            
            # Console output
            print(f"\n📅 Date: {date}")
            print(f"   Total SLM games: {len(slm_games)}")
            print(f"   SLM refs appointed to SLM games: {len(slm_refs_on_slm_games)}")
            print(f"   Non-SLM refs appointed to SLM games: {len(non_slm_refs_on_slm_games)}")
            print(f"   Total SLM refs NOT on SLM games: {len(slm_refs_not_on_slm)} ({pct_not_on_slm:.1f}%)")
            print(f"      - Staying home (no assignment): {len(slm_refs_staying_home)} ({pct_staying_home:.1f}%)")
            print(f"      - Working other divisions: {len(slm_refs_on_other_games)}")
            
            # Details of refs staying home
            if day_stat['staying_home_list']:
                print(f"\n   📋 SLM refs staying home:")
                for ref in day_stat['staying_home_list']:
                    print(f"      - {ref[0]} {ref[1]}")
            
            # Details of refs working other divisions
            if day_stat['working_other_list']:
                print(f"\n   📋 SLM refs working other divisions:")
                for ref in day_stat['working_other_list']:
                    competitions = day_stat['working_other_details'][ref]
                    print(f"      - {ref[0]} {ref[1]}: {', '.join(competitions)}")
    
    # Print global statistics
    print("\n" + "="*80)
    print("GLOBAL STATISTICS")
    print("="*80)
    print(f"Total days analyzed: {global_stats['days_count']}")
    print(f"Total SLM games: {global_stats['total_slm_games']}")
    print(f"Average SLM games per day: {global_stats['total_slm_games'] / global_stats['days_count']:.1f}")
    if global_stats['days_count'] > 0:
        avg_not_on_slm = global_stats['total_slm_refs_not_on_slm'] / global_stats['days_count']
        avg_staying_home = global_stats['total_staying_home'] / global_stats['days_count']
        avg_working_other = global_stats['total_working_other'] / global_stats['days_count']
        total_slm_refs = len(slm_refs_qualified)
        
        print(f"\nAverage per day:")
        print(f"  - SLM refs NOT on SLM games: {avg_not_on_slm:.1f} ({avg_not_on_slm/total_slm_refs*100:.1f}%)")
        print(f"  - SLM refs staying home: {avg_staying_home:.1f} ({avg_staying_home/total_slm_refs*100:.1f}%)")
        print(f"  - SLM refs working other divisions: {avg_working_other:.1f}")
    
    # Print monthly statistics
    print("\n" + "="*80)
    print("MONTHLY STATISTICS")
    print("="*80)
    
    month_order = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                   'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
    
    for month in month_order:
        if month in monthly_stats:
            stats = monthly_stats[month]
            print(f"\n{month}:")
            print(f"  Days with 3+ SLM games: {stats['days_count']}")
            print(f"  Total SLM games: {stats['total_slm_games']}")
            if stats['days_count'] > 0:
                avg_not_on_slm = stats['total_slm_refs_not_on_slm'] / stats['days_count']
                avg_staying_home = stats['total_staying_home'] / stats['days_count']
                avg_working_other = stats['total_working_other'] / stats['days_count']
                total_slm_refs = len(slm_refs_qualified)
                
                print(f"  Average per day:")
                print(f"    - SLM refs NOT on SLM games: {avg_not_on_slm:.1f} ({avg_not_on_slm/total_slm_refs*100:.1f}%)")
                print(f"    - SLM refs staying home: {avg_staying_home:.1f} ({avg_staying_home/total_slm_refs*100:.1f}%)")
                print(f"    - SLM refs working other divisions: {avg_working_other:.1f}")
    
    # Generate HTML report
    generate_html_report(daily_stats, global_stats, monthly_stats, slm_refs_qualified, month_order)
    print("\n✅ HTML report generated: data/staying_home.html")

def generate_html_report(daily_stats, global_stats, monthly_stats, slm_refs_qualified, month_order):
    """Generate HTML report with statistics"""
    total_slm_refs = len(slm_refs_qualified)
    
    html = """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Statistiques Arbitres SLM - Absences</title>
</head>
<body>
    <h1>Statistiques Arbitres SLM - Absences sur Journées à 3+ Matchs</h1>
    
    <h2>Statistiques Globales</h2>
    <table border="1">
        <tr>
            <th>Métrique</th>
            <th>Valeur</th>
        </tr>
        <tr>
            <td>Total arbitres SLM qualifiés (3+ matchs)</td>
            <td>%d</td>
        </tr>
        <tr>
            <td>Journées analysées (3+ matchs SLM)</td>
            <td>%d</td>
        </tr>
        <tr>
            <td>Total matchs SLM</td>
            <td>%d</td>
        </tr>
        <tr>
            <td>Moyenne matchs SLM par journée</td>
            <td>%.1f</td>
        </tr>
        <tr>
            <td>Moyenne arbitres SLM Non désignés sur SLM par journée</td>
            <td>%.1f (%.1f%%)</td>
        </tr>
        <tr>
            <td>Moyenne arbitres SLM restant à domicile par journée</td>
            <td>%.1f (%.1f%%)</td>
        </tr>
        <tr>
            <td>Moyenne arbitres SLM travaillant autres divisions par journée</td>
            <td>%.1f</td>
        </tr>
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
        global_stats['total_working_other'] / global_stats['days_count'] if global_stats['days_count'] > 0 else 0
    )
    
    # Monthly statistics
    html += "\n    <h2>Statistiques Mensuelles</h2>\n"
    html += """    <table border="1">
        <thead>
            <tr>
                <th>Mois</th>
                <th>Journées</th>
                <th>Matchs SLM</th>
                <th>Moy. Non désigné sur SLM</th>
                <th>% Non désigné sur SLM</th>
                <th>Moy. Restant à domicile</th>
                <th>% Restant à domicile</th>
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
                avg_working_other = stats['total_working_other'] / stats['days_count']
                
                html += f"""            <tr>
                <td>{month}</td>
                <td>{stats['days_count']}</td>
                <td>{stats['total_slm_games']}</td>
                <td>{avg_not_on_slm:.1f}</td>
                <td>{avg_not_on_slm/total_slm_refs*100:.1f}%</td>
                <td>{avg_staying_home:.1f}</td>
                <td>{avg_staying_home/total_slm_refs*100:.1f}%</td>
                <td>{avg_working_other:.1f}</td>
            </tr>
"""
    
    html += """        </tbody>
    </table>
    
    <h2>Détails par Journée</h2>
"""
    
    # Daily details
    for day in daily_stats:
        html += f"""
    <h3>{day['date']}</h3>
    <table border="1">
        <tr>
            <th>Métrique</th>
            <th>Valeur</th>
        </tr>
        <tr>
            <td>Matchs SLM</td>
            <td>{day['total_slm_games']}</td>
        </tr>
        <tr>
            <td>Arbitres SLM désignés sur SLM</td>
            <td>{day['slm_refs_on_slm']}</td>
        </tr>
        <tr>
            <td>Arbitres non-SLM désignés sur SLM</td>
            <td>{day['non_slm_refs_on_slm']}</td>
        </tr>
        <tr>
            <td>Arbitres SLM Non désigné sur SLM</td>
            <td>{day['slm_refs_not_on_slm']} ({day['pct_not_on_slm']:.1f}%)</td>
        </tr>
        <tr>
            <td>Restant à domicile</td>
            <td>{day['staying_home']} ({day['pct_staying_home']:.1f}%)</td>
        </tr>
        <tr>
            <td>Travaillant autres divisions</td>
            <td>{day['working_other']}</td>
        </tr>
    </table>
"""
        
        if day['staying_home_list']:
            html += "\n    <h4>Arbitres SLM restant à domicile</h4>\n    <ul>\n"
            for ref in day['staying_home_list']:
                html += f"        <li>{ref[0]} {ref[1]}</li>\n"
            html += "    </ul>\n"
        
        if day['working_other_list']:
            html += "\n    <h4>Arbitres SLM travaillant autres divisions</h4>\n    <ul>\n"
            for ref in day['working_other_list']:
                competitions = ', '.join(day['working_other_details'][ref])
                html += f"        <li>{ref[0]} {ref[1]}: {competitions}</li>\n"
            html += "    </ul>\n"
    
    html += """
</body>
</html>"""
    
    with open("data/staying_home.html", "w") as f:
        f.write(html)

if __name__ == "__main__":
    main()
