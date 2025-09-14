import bs4
import json
import requests
import os

def get_all_magnus_games():
    url = "https://liguemagnus.com/wp-admin/admin-ajax.php"
    data = {
        "action": "get_rencontres",
        "page": "",
        "equipe_id": "",
        "competition_id": 197,
        "phase_id": 560,
        "date_min": "",
        "date_max": "",
        "par_page": 300,
        "journee": "",
        "limite": 0
    }
    response = requests.post(url, data=data)
    return response.json()

def get_all_d1_games():
    url = "https://www.hockeyfrance.com/competitions/wp-admin/admin-ajax.php"
    data= {
        "action": "get_rencontres",
        "page": "",
        "equipe_id": "",
        "competition_id": 196,
        "phase_id": 559,
        "date_min": "",
        "date_max": "",
        "par_page": 300,
        "journee": "",
        "limite": 0
    }
    response = requests.post(url, data=data)
    return response.json()

def get_game_penalties(base_url, game_id: int) -> str:
    url = f"{base_url}/rencontre/{game_id}/"
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
        if penalty['sanction'] is None:
            print("Penalty without sanction in game", url)
            continue
        formatted_penalty = [
            "/".join(game_data['date_rencontre_non_formate'].split(' ')[0].replace('-', '/').split('/')[::-1]),
            game_data['receveur']['abreviation'],
            game_data['visiteur']['abreviation'],
            f"{int(penalty['temps']/3600):02}:{(int(penalty['temps']/60)%60):02}:{(penalty['temps']%60):02}",
            penalty['equipe']['abreviation'],
            penalty['joueur']['nom_complet'] if penalty['joueur'] else "",
            penalty['substitution']['nom_complet'] if penalty['substitution'] else "",
            f"{penalty['temps_penalite'] if penalty['temps_penalite'] else 2}:00",
            penalty['sanction']['code'],
        ]
        formatted_penalties.append(formatted_penalty)

    formatted_dump = "\n".join("\t".join(str(cell) for cell in row) for row in formatted_penalties)

    # with open(f"game_{game_id}_penalties.txt", 'w') as f:
    #     f.write(formatted_dump)
    return formatted_dump

def main():
    magnus_games = get_all_magnus_games()
    finished_magnus_games = [game for game in magnus_games['data']['data'] if game['etat'] == 'T']
    print(len(finished_magnus_games), "out of", len(magnus_games['data']['data']), "Magnus games are finished")
    # Check if file exists
    if os.path.exists("data/finished_games.json"):
        with open("data/finished_games.json", 'r') as f:
            data = json.load(f)
    else:
        data = {}
    for game in finished_magnus_games:
        if str(game['id']) in data:
            continue
        try:
            data[game['id']] = get_game_penalties("https://liguemagnus.com", game['id'])
        except Exception as e:
            print("Error processing game", game['id'], ":", e)

    d1_games = get_all_d1_games()
    finished_d1_games = [game for game in d1_games['data']['data'] if game['etat'] == 'T']
    print(len(finished_d1_games), "out of", len(d1_games['data']['data']), "D1 games are finished")

    for game in finished_d1_games:
        if str(game['id']) in data:
            continue
        try:
            data[game['id']] = get_game_penalties("https://www.hockeyfrance.com/competitions", game['id'])
        except Exception as e:
            print("Error processing game", game['id'], ":", e)

    with open("data/finished_games.json", 'w') as f:
        json.dump(data, f, indent=4)

    magnus_lines = []
    for game in finished_magnus_games:
        if str(game['id']) not in data:
            continue
        penalties = data[str(game['id'])].split("\n")
        for penalty in penalties:
            penalty_data = penalty.split("\t")
            line = "".join([f"<td>{data}</td>" for data in penalty_data])
            magnus_lines.append(f"<tr>{line}</tr>")
    d1_lines = []
    for game in finished_d1_games:
        if str(game['id']) not in data:
            continue
        penalties = data[str(game['id'])].split("\n")
        for penalty in penalties:
            penalty_data = penalty.split("\t")
            line = "".join([f"<td>{data}</td>" for data in penalty_data])
            d1_lines.append(f"<tr>{line}</tr>")
    with open("template_table.html", 'r') as f:
        html_content = f.read()
    with open("data/magnus.html", 'w') as f:
        f.write(html_content.replace("%DATA%", "\n".join(magnus_lines)))
    with open("data/d1.html", 'w') as f:
        f.write(html_content.replace("%DATA%", "\n".join(d1_lines)))

    magnus_lines = [data[str(game['id'])] for game in finished_magnus_games if str(game['id']) in data]
    d1_lines = [data[str(game['id'])] for game in finished_d1_games if str(game['id']) in data]
    with open("template_index.html", 'r') as f:
        html_content = f.read()
    with open("data/index.html", 'w') as f:
        f.write(html_content.replace("%MAGNUS_DATA%", "\n".join(magnus_lines)).replace("%D1_DATA%", "\n".join(d1_lines)))


if __name__ == "__main__":
    main()