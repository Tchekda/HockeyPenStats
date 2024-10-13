import bs4
import json
import requests
import os

def get_all_games():
    url = "https://liguemagnus.com/wp-admin/admin-ajax.php"
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:131.0) Gecko/20100101 Firefox/131.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache"
    }
    data = {
        "action": "get_rencontres",
        "page": "",
        "equipe_id": "",
        "competition_id": 157,
        "phase_id": 432,
        "date_min": "",
        "date_max": "2025-02-22T00:00:00.000+01:00",
        "par_page": 300,
        "journee": "",
        "limite": 0
    }
    response = requests.post(url, headers=headers, data=data)
    return response.json()

def get_game_penalties(game_id: int) -> str:
    url = f"https://liguemagnus.com/rencontre/{game_id}/"
    response = requests.get(url)
    """
    Extract attributes from the <live-rencontre-container> element
    """
    soup = bs4.BeautifulSoup(response.text, 'html.parser')
    live_rencontre_container = soup.find('live-rencontre-container')
    game_data = json.loads(live_rencontre_container.attrs[':data'])
    # with open(f"game_{game_id}.json", 'w') as f:
    #     json.dump(game_data, f, indent=4)

    game_events = game_data['evenements']
    game_penalties = [event for event in game_events if event['type'] == 'SANCTION']

    print(len(game_penalties), "penalties in game", game_id)

    formatted_penalties = []
    for penalty in game_penalties:
        formatted_penalty = [
            "/".join(game_data['date_rencontre_non_formate'].split(' ')[0].replace('-', '/').split('/')[::-1]),
            game_data['receveur']['abreviation'],
            game_data['visiteur']['abreviation'],
            f"{int(penalty['temps']/60)}:{penalty['temps']%60}:00",
            penalty['equipe']['abreviation'],
            penalty['joueur']['nom_complet'] if penalty['joueur'] else "",
            penalty['substitution']['nom_complet'] if penalty['substitution'] else "",
            f"{penalty['temps_penalite']}:00:00",
            penalty['sanction']['code'],
        ]
        formatted_penalties.append(formatted_penalty)

    formatted_dump = "\n".join("\t".join(str(cell) for cell in row) for row in formatted_penalties)

    # with open(f"game_{game_id}_penalties.txt", 'w') as f:
    #     f.write(formatted_dump)
    return formatted_dump

def main():
    games = get_all_games()
    finished_games = [game for game in games['data']['data'] if game['etat'] == 'T']
    print(len(finished_games), "out of", len(games['data']['data']), "games are finished")
    # Check if file exists
    if os.path.exists("data/finished_games.json"):
        with open("data/finished_games.json", 'r') as f:
            data = json.load(f)
    else:
        data = {}
    for game in finished_games:
        if str(game['id']) in data:
            continue
        try:
            data[game['id']] = get_game_penalties(game['id'])
        except Exception as e:
            print("Error processing game", game['id'], ":", e)

    with open("data/finished_games.json", 'w') as f:
        json.dump(data, f, indent=4)

    lines = [penalties for penalties in data.values()]
    with open("template.html", 'r') as f:
        html_content = f.read()
    with open("data/index.html", 'w') as f:
        f.write(html_content.replace("%DATA%", "\n".join(lines)))

if __name__ == "__main__":
    main()