"""Extract data/AI job postings from the Bundesagentur fuer Arbeit (BA) Jobsuche API.

Searches all of Germany for a fixed list of terms (English and German), keeps only
postings with a location in Germany, skips postings already stored unchanged, and
fetches the full detail only for new or changed postings.
Returns the same shape as extract.py, plus BA-only fields.

Usage:  python3 -m pipeline.extract_ba --days 7 --max-details 20
"""
import argparse
import base64
import re
import statistics
import time
from collections import Counter
from datetime import date, datetime

import requests

from pipeline.extract import match_role_type

SEARCH_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
DETAIL_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{}"
BA_PAGE_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{}"
HEADERS = {"X-API-Key": "jobboerse-jobsuche"}   # public client ID used by the BA website, not a secret

SEARCH_TERMS = [
    "Data Engineer",
    "Data Analyst",
    "Data Scientist",
    "Analytics Engineer",
    "Business Intelligence",
    "Machine Learning",
    "Datenanalyst",
    "Datenanalyse",
    "Datenwissenschaftler",
    "Datenbankentwickler",
    "Künstliche Intelligenz",
]
PAGE_SIZE = 100
MAX_PAGES_PER_TERM = 10        # at most 1,000 hits per term per run
DELAY_SECONDS = 0.5            # pause after every request, to be polite to a public service
SUMMARY_MAX_CHARS = 600        # external postings below this length only carry a short summary
GERMANY = {"deutschland", "germany", "de"}

# Title patterns the English keyword list in extract.py does not catch, matched on word stems
# so "Datenanalyst", "Datenanalystin", "Datenanalyst:in" and "Datenanalyse" all hit.
# \b = whole word (so "ki" never matches "Kita").
EXTRA_ROLE_PATTERNS = [
    (r"datenanaly", "analyst"),
    (r"\bbi (entwickl|analyst|developer|berater|consultant|spezialist)", "analyst"),
    (r"statistiker", "analyst"),
    (r"datenwissenschaft", "scientist"),
    (r"dateningenieur", "engineer"),
    (r"datenbankentwickl", "engineer"),
    (r"data warehous", "engineer"),
    (r"data architect", "engineer"),
    (r"databricks", "engineer"),
    (r"\bki\b", "ai"),
    (r"künstliche intelligenz", "ai"),
    (r"maschinelles lernen", "ai"),
]

KEEP_TYPES = {"ARBEIT", "PRAKTIKUM_TRAINEE"}   # drops Ausbildung and Selbstaendigkeit
STUDENT_PATTERN = re.compile(
    r"werkstudent|working student|praktik|\bintern\b|internship|abschlussarbeit|masterarbeit|bachelorarbeit",
    re.IGNORECASE,
)


# ---------------------------------------------------------------- helpers

def get_json(session, url, params=None):
    """GET with a polite delay and a simple retry on rate limits or server errors."""
    for attempt in range(3):
        response = session.get(url, params=params, timeout=30)
        if response.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * (attempt + 1))
            continue
        response.raise_for_status()
        time.sleep(DELAY_SECONDS)
        return response.json()
    response.raise_for_status()
    return response.json()


def search_term(session, term, days):
    """Return all search hits for one term, across pages, and the total the API reports."""
    hits = []
    total = 0
    for page in range(1, MAX_PAGES_PER_TERM + 1):
        payload = get_json(session, SEARCH_URL, {
            "was": term,
            "veroeffentlichtseit": days,
            "size": PAGE_SIZE,
            "page": page,
        })
        batch = payload.get("ergebnisliste") or []
        hits.extend(batch)
        total = int(payload.get("maxErgebnisse") or 0)
        if len(batch) < PAGE_SIZE or page * PAGE_SIZE >= total:
            break
    return hits, total


def countries_of(record):
    """Set of lowercase country names across all locations of a posting (empty if unknown)."""
    found = set()
    for loc in record.get("stellenlokationen") or []:
        land = (loc.get("adresse") or {}).get("land")
        if land:
            found.add(land.strip().lower())
    return found


def german_city(record):
    """City of the first location in Germany, else of the first location."""
    locations = record.get("stellenlokationen") or []
    for loc in locations:
        adresse = loc.get("adresse") or {}
        if (adresse.get("land") or "").strip().lower() in GERMANY:
            return adresse.get("ort")
    return (locations[0].get("adresse") or {}).get("ort") if locations else None


def normalize_title(title):
    """Lowercase, drop (m/w/d), and turn hyphens, slashes and gender markers into spaces."""
    t = title.lower()
    t = re.sub(r"\([^)]*\)", " ", t)       # (m/w/d), (all genders)
    t = re.sub(r"[-/_:*|,]", " ", t)       # KI-Entwickler, Analyst:in, Analyst*in, Data-Engineer
    return re.sub(r"\s+", " ", t).strip()


def ba_role_type(title):
    t = normalize_title(title)
    role = match_role_type(t)              # English keywords from extract.py
    if role:
        return role
    for pattern, role_type in EXTRA_ROLE_PATTERNS:
        if re.search(pattern, t):
            return role_type
    return None


def parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def parse_timestamp(value):
    """Return a naive datetime so it compares cleanly with the TIMESTAMP column."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def clean_description(text):
    return re.sub(r"\*\*", "", text or "").strip()


def load_known_changes():
    """job_id -> changed_at for BA postings already in the database."""
    from pipeline.db import get_connection
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT job_id, changed_at FROM jobs WHERE source = 'ba'")
            return dict(cur.fetchall())
    finally:
        conn.close()


# ---------------------------------------------------------------- main logic

def extract(days=7, max_details=300, known=None):
    known = known or {}
    session = requests.Session()
    session.headers.update(HEADERS)
    stats = Counter()
    per_term = {}

    # 1. Search every term and dedupe by reference number
    candidates = {}
    for term in SEARCH_TERMS:
        hits, total = search_term(session, term, days)
        per_term[term] = total
        stats["search_hits"] += len(hits)
        for hit in hits:
            ref = hit.get("referenznummer")
            if ref:
                candidates.setdefault(ref, hit)
    stats["unique"] = len(candidates)

    # 2. Cheap filters first, detail calls only for what survives
    countries_seen = Counter()
    unclassified = Counter()
    results = []
    external_lengths = []
    for ref, hit in candidates.items():
        countries = countries_of(hit)
        countries_seen[", ".join(sorted(countries)) or "unknown"] += 1
        if countries and not countries & GERMANY:
            stats["dropped_not_germany"] += 1
            continue

        title = hit.get("stellenangebotsTitel") or ""
        if STUDENT_PATTERN.search(title):
            stats["dropped_student"] += 1
            continue
        role_type = ba_role_type(title)
        if role_type is None:
            stats["dropped_unclassified"] += 1
            unclassified[normalize_title(title)] += 1
            continue
        if hit.get("stellenangebotsart") and hit["stellenangebotsart"] not in KEEP_TYPES:
            stats["dropped_type"] += 1
            continue
        changed = parse_timestamp(hit.get("aenderungsdatum"))
        if ref in known and changed is not None and known[ref] == changed:
            stats["skipped_unchanged"] += 1
            continue
        if stats["details_fetched"] >= max_details:
            stats["deferred_to_next_run"] += 1
            continue

        encoded = base64.b64encode(ref.encode()).decode()
        try:
            detail = get_json(session, DETAIL_URL.format(encoded))
        except requests.HTTPError:
            stats["detail_failed"] += 1      # e.g. posting removed between search and detail
            continue
        stats["details_fetched"] += 1

        # Location was unknown in the search hit: check it again on the detail
        detail_countries = countries_of(detail)
        if detail_countries and not detail_countries & GERMANY:
            stats["dropped_not_germany"] += 1
            continue

        kind = detail.get("stellenangebotsart")
        if kind not in KEEP_TYPES:
            stats["dropped_type"] += 1
            continue

        description = clean_description(detail.get("stellenangebotsBeschreibung"))
        external_url = detail.get("externeURL")
        if external_url:
            external_lengths.append(len(description))

        results.append({
            # same keys as extract.py
            "job_id": ref,
            "title": detail.get("stellenangebotsTitel") or title,
            "company": detail.get("firma"),
            "city": german_city(detail),
            "remote": bool(detail.get("homeofficemoeglich")),   # "home office possible", not fully remote
            "role_type": role_type,
            "posted_at": parse_date(detail.get("datumErsteVeroeffentlichung")),
            "description_html": description,                    # plain text; the HTML cleaner leaves it as is
            "posting_url": external_url or BA_PAGE_URL.format(ref),
            # BA-only fields
            "source": "ba",
            "changed_at": parse_timestamp(detail.get("aenderungsdatum")),
            "employment_type": kind,
            "career_changer_ok": detail.get("quereinstiegGeeignet"),
            "is_temp_agency": detail.get("istArbeitnehmerUeberlassung"),
            "is_summary": bool(external_url) and len(description) < SUMMARY_MAX_CHARS,
            "partner_board": detail.get("allianzpartnerName"),
        })

    stats["kept"] = len(results)
    stats["external"] = len(external_lengths)
    stats["external_median_chars"] = int(statistics.median(external_lengths)) if external_lengths else 0
    stats["countries_seen"] = countries_seen.most_common(10)
    stats["unclassified_top"] = unclassified.most_common(25)
    return results, dict(stats), per_term


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract job postings from the BA Jobsuche API.")
    parser.add_argument("--days", type=int, default=7, help="only postings published in the last N days")
    parser.add_argument("--max-details", type=int, default=300, help="cap on detail requests per run")
    parser.add_argument("--no-db", action="store_true", help="do not read known postings from the database")
    args = parser.parse_args()

    known = {} if args.no_db else load_known_changes()
    jobs, stats, per_term = extract(args.days, args.max_details, known)

    print("API totals per term:")
    for term, total in per_term.items():
        print(f"  {term:<25} {total}")

    print("\nCountries in search hits (unique postings):")
    for country, count in stats["countries_seen"]:
        print(f"  {count:>4}  {country}")

    print("\nFunnel:")
    for key in ["search_hits", "unique", "dropped_not_germany", "dropped_student", "dropped_unclassified",
                "dropped_type", "skipped_unchanged", "deferred_to_next_run", "detail_failed",
                "details_fetched", "kept"]:
        print(f"  {key:<22} {stats.get(key, 0)}")

    print(f"\nExternal postings: {stats['external']} of {stats['kept']}, "
          f"median description length {stats['external_median_chars']} chars")
    print(f"Summary-only: {sum(j['is_summary'] for j in jobs)}, "
          f"temp agency: {sum(bool(j['is_temp_agency']) for j in jobs)}")

    print("\nSample:")
    for j in jobs[:5]:
        print(f"  [{j['role_type']}] {j['title']} | {j['company']} | {j['city']} | "
              f"{j['employment_type']} | {len(j['description_html'])} chars | summary={j['is_summary']}")

    print("\nMost common dropped titles (check for roles we miss):")
    for title, count in stats["unclassified_top"]:
        print(f"  {count:>3}  {title}")