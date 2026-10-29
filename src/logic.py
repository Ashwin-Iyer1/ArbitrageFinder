from itertools import chain
import math
import time
from typing import Generator, Iterable, Optional

import requests

BASE_URL = "api.the-odds-api.com/v4"
PROTOCOL = "https://"


class APIException(RuntimeError):
    def __str__(self):
        return str(self.args[0]) + " (HTTP " + str(self.args[1].status_code) + ")"


class AuthenticationException(APIException):
    pass


class RateLimitException(APIException):
    pass


def handle_faulty_response(response: requests.Response):
    if response.status_code == 401:
        raise AuthenticationException("Failed to authenticate with the API. Is the API key valid?", response)
    elif response.status_code == 429:
        raise RateLimitException("Encountered API rate limit.", response)
    else:
        raise APIException("Encountered unexpected error.", response)


def get_sports(key: str) -> list[str]:
    url = f"{PROTOCOL}{BASE_URL}/sports"
    response = requests.get(url, params={'apiKey': key})
    if response.status_code != 200:
        handle_faulty_response(response)
    sports = response.json()
    return [sport['key'] for sport in sports if not sport['has_outrights']]


def get_data(key: str, sport: str, region: str = 'eu') -> Generator[dict, None, None]:
    url = f"{PROTOCOL}{BASE_URL}/sports/{sport}/odds"
    response = requests.get(url, params={
        'apiKey': key,
        'regions': region,
        'markets': 'h2h',
        'dateFormat': 'unix'
    })
    if response.status_code != 200:
        handle_faulty_response(response)
    yield from response.json()


def process_data(matches: Iterable, include_started_matches: bool = False,
                 sportsbooks: Optional[Iterable[str]] = None) -> Generator[dict, None, None]:
    allowed_sportsbooks = {
        item.strip().lower()
        for sportsbook in sportsbooks
        for item in sportsbook.split(',')
        if item.strip()
    } if sportsbooks else None

    for match in matches:
        start_time = match.get('commence_time')
        now = time.time()
        if not include_started_matches and start_time and start_time < now:
            continue

        bookmakers = match.get('bookmakers', [])
        if allowed_sportsbooks:
            bookmakers = [
                bookmaker for bookmaker in bookmakers
                if bookmaker.get('key', '').lower() in allowed_sportsbooks
                or bookmaker.get('title', '').lower() in allowed_sportsbooks
            ]

        markets = [
            (bookmaker, market)
            for bookmaker in bookmakers
            for market in bookmaker.get('markets', [])
            if market.get('key') == 'h2h'
        ]
        if not markets:
            continue

        expected_outcomes = {match['home_team'], match['away_team']}
        if match.get('sport_key', '').startswith('soccer_'):
            expected_outcomes.add('Draw')
        if any(
            outcome.get('name') == 'Draw'
            for _, market in markets
            for outcome in market.get('outcomes', [])
        ):
            expected_outcomes.add('Draw')

        best_odd_per_outcome = {}
        for bookmaker, market in markets:
            outcomes = market.get('outcomes', [])
            names = {outcome.get('name') for outcome in outcomes}
            if names != expected_outcomes or len(outcomes) != len(expected_outcomes):
                continue
            if any(
                not isinstance(outcome.get('price'), (int, float))
                or not math.isfinite(outcome['price'])
                or outcome['price'] <= 1
                for outcome in outcomes
            ):
                continue
            for outcome in outcomes:
                name, odds = outcome['name'], outcome['price']
                if name not in best_odd_per_outcome or odds > best_odd_per_outcome[name][1]:
                    best_odd_per_outcome[name] = (bookmaker['title'], odds)

        if set(best_odd_per_outcome) != expected_outcomes:
            continue

        total_implied_odds = sum(1 / odds for _, odds in best_odd_per_outcome.values())
        yield {
            'match_name': f"{match['home_team']} v. {match['away_team']}",
            'match_start_time': start_time,
            'hours_to_start': (start_time - now) / 3600 if start_time else None,
            'league': match.get('sport_key'),
            'best_outcome_odds': best_odd_per_outcome,
            'total_implied_odds': total_implied_odds
        }


def get_arbitrage_opportunities(key: str, region: str = 'eu', cutoff: float = 0.0,
                                sportsbooks: Optional[Iterable[str]] = None):
    sports = get_sports(key)
    data = chain.from_iterable(get_data(key, sport, region=region) for sport in sports)
    data = filter(lambda match: match != "message", data)
    results = process_data(data, sportsbooks=sportsbooks)
    for result in results:
        if result['total_implied_odds'] < (1 - cutoff):
            yield result
