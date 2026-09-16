import requests
import re
from datetime import datetime, timezone

API_URL = "https://www.arbeitnow.com/api/job-board-api"
MAX_PAGES = 3  # newest-first + hourly updates means a few pages is enough per run,
               # and it respects the API's "please don't abuse this" terms

GERMAN_CITIES = {
    "berlin", "hamburg", "munich", "münchen", "cologne", "köln", "frankfurt",
    "stuttgart", "düsseldorf", "dusseldorf", "dortmund", "essen", "leipzig",
    "bremen", "dresden", "hannover", "nuremberg", "nürnberg", "duisburg",
    "bochum", "wuppertal", "bielefeld", "bonn", "münster", "muenster",
    "karlsruhe", "mannheim", "augsburg", "wiesbaden", "mönchengladbach",
    "braunschweig", "chemnitz", "kiel", "aachen", "halle", "magdeburg",
    "freiburg", "krefeld", "lübeck", "mainz", "rostock", "kassel",
    "saarbrücken", "potsdam", "oldenburg", "osnabrück", "heidelberg",
    "darmstadt", "paderborn", "regensburg", "ingolstadt", "würzburg",
    "wolfsburg", "ulm", "pforzheim", "göttingen", "trier", "reutlingen",
    "koblenz", "jena", "erlangen", "siegen", "starnberg", "gescher", "garching",
}

ROLE_KEYWORDS = {
    "data analyst": "analyst",
    "data engineer": "engineer",
    "data scientist": "scientist",
    "analytics engineer": "engineer",
    "cloud": "cloud",
    "devops": "cloud",
    "machine learning": "ai",
    "ai engineer": "ai",
    "business intelligence": "analyst",
    "data platform": "engineer",
    "data architecture": "engineer",
    "data science": "scientist",
    "ai analyst": "analyst",
    "ai architect": "ai",
    "ai developer": "ai",
    "agentic ai": "ai",
}


def is_german(location):
    if not location:
        return False
    loc = location.lower()
    if "germany" in loc:
        return True
    return any(city in loc for city in GERMAN_CITIES)


def match_role_type(title):
    t = re.sub(r"\([^)]*\)", " ", title.lower())
    t = re.sub(r"\s+", " ", t).strip()
    for keyword, role_type in ROLE_KEYWORDS.items():
        if keyword in t:
            return role_type
    return None


def fetch_all_pages():
    all_postings = []
    url = API_URL
    pages_fetched = 0

    while url and pages_fetched < MAX_PAGES:
        response = requests.get(url)
        response.raise_for_status()
        payload = response.json()
        all_postings.extend(payload["data"])
        url = payload["links"]["next"]
        pages_fetched += 1

    return all_postings


def extract():
    raw_postings = fetch_all_pages()
    results = []
    dropped_non_german = 0
    dropped_unclassified = 0

    for job in raw_postings:
        if not is_german(job["location"]):
            dropped_non_german += 1
            continue
        role_type = match_role_type(job["title"])
        if role_type is None:
            dropped_unclassified += 1
            continue

        results.append({
            "job_id": job["slug"],
            "title": job["title"],
            "company": job["company_name"],
            "city": job["location"],
            "remote": job["remote"],
            "role_type": role_type,
            "posted_at": datetime.fromtimestamp(job["created_at"], tz=timezone.utc).date(),
            "description_html": job["description"],
        })

    stats = {
        "raw": len(raw_postings),
        "dropped_non_german": dropped_non_german,
        "dropped_unclassified": dropped_unclassified,
        "survivors": len(results),
    }

    return results, stats


if __name__ == "__main__":
    jobs, stats = extract()
    print(
        f"Raw: {stats['raw']}  ->  German: {stats['raw'] - stats['dropped_non_german']}  "
        f"->  Role-relevant: {stats['survivors']}"
    )
    print(
        f"Dropped non-German: {stats['dropped_non_german']}, "
        f"dropped unclassified role: {stats['dropped_unclassified']}"
    )
    for j in jobs[:5]:
        print(j)