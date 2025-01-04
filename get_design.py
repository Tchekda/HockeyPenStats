import requests
import re
import logging
import os

HTTP_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/112.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Host': 'hockeynet.fr',
    'Referer': 'https://hockeynet.fr/',
    }
CSRF_REFEX = r"name=\"csrf-token\" content=\"([^\"]+)\""

def extractToken(page: str) -> str:
    token = re.findall(CSRF_REFEX, page)
    if len(token) == 0:
        logging.error("Could not find token")
        raise Exception("Could not find token")
    return token[0]

def sendRequest(s: requests.Session, url: str, method: str, data: dict = None) -> requests.Response:
    page = s.request(method, url, headers=HTTP_HEADERS, json=data, timeout=10)
    try:
        page.raise_for_status()
    except Exception as e:
        logging.exception(f"An error occured while fetching {url}")
        raise e
    return page

def getAllDesignations(s: requests.Session) -> str:
    data = {
        "etat": None,
        "competitions_ids": [],
        "phases_ids": [],
        "dates": {},
        "role_id": None,
        "etat_rencontre": None,
        "lieu_pratique": None,
        "horaire": None,
        "libelle": None,
        "saison": 2025,
        "discipline_code": "HG",
        "show_all": False
    }
    page = sendRequest(s, "https://hockeynet.fr/arbitrage/designation/export", "POST", data)
    return page.text
    

def main() -> str:
    if 'X-CSRF-TOKEN' in HTTP_HEADERS:
        del HTTP_HEADERS['X-CSRF-TOKEN']
    s = requests.Session()
    loginPage = sendRequest(s, "https://hockeynet.fr/auth/login", "GET")
    sendRequest(s, "https://hockeynet.fr/auth/login", "POST", {
        '_token': extractToken(loginPage.text),
        'username': os.environ.get('HOCKEYNET_USER', "225544"),
        'password': os.environ.get('HOCKEYNET_PASSWORD', "PASSWORD")
    })
    pageDesignation = sendRequest(s, "https://hockeynet.fr/arbitrage/designation", "GET")
    HTTP_HEADERS['X-CSRF-TOKEN'] = extractToken(pageDesignation.text)
    return getAllDesignations(s)

if __name__ == "__main__":
    logging.getLogger().addHandler(logging.StreamHandler())
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True
    main()