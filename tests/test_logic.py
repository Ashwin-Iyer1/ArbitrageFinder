import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import main
from src import logic


class LogicTests(unittest.TestCase):
    def test_get_sports_excludes_outrights(self):
        response = Mock(status_code=200)
        response.json.return_value = [
            {'key': 'soccer_epl', 'has_outrights': False},
            {'key': 'outrights', 'has_outrights': True},
        ]
        url = f"{logic.PROTOCOL}{logic.BASE_URL}/sports"

        with patch.object(logic.requests, 'get', return_value=response) as get:
            self.assertEqual(logic.get_sports('secret'), ['soccer_epl'])

        get.assert_called_once_with(url, params={'apiKey': 'secret'})

    def test_get_data_uses_region_and_yields_response(self):
        response = Mock(status_code=200)
        response.json.return_value = [{'id': 'match-1'}, {'id': 'match-2'}]
        url = f"{logic.PROTOCOL}{logic.BASE_URL}/sports/soccer_epl/odds"

        with patch.object(logic.requests, 'get', return_value=response) as get:
            result = list(logic.get_data('secret', 'soccer_epl', region='us'))

        self.assertEqual(result, response.json.return_value)
        get.assert_called_once_with(url, params={
            'apiKey': 'secret',
            'regions': 'us',
            'markets': 'h2h',
            'dateFormat': 'unix'
        })

    def test_faulty_responses_raise_typed_errors(self):
        for status, error_type in (
            (401, logic.AuthenticationException),
            (429, logic.RateLimitException),
            (503, logic.APIException),
        ):
            with self.subTest(status=status):
                response = Mock(status_code=status)
                with self.assertRaises(error_type) as raised:
                    logic.handle_faulty_response(response)
                self.assertIn(f'HTTP {status}', str(raised.exception))

    def test_process_data_filters_comma_separated_sportsbooks(self):
        match = {
            'home_team': 'A',
            'away_team': 'B',
            'commence_time': 5000,
            'sport_key': 'soccer_test',
            'bookmakers': [
                self._book('draftkings', 'DraftKings', [2.2, 2.3, 2.5]),
                self._book('fanduel', 'FanDuel', [2.4, 2.1, 2.4]),
                self._book('caesars', 'Caesars', [9.0, 9.0, 9.0]),
            ],
        }

        with patch.object(logic.time, 'time', return_value=1000):
            results = list(logic.process_data([match], sportsbooks=[' DraftKings, FanDuel ']))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['best_outcome_odds'], {
            'A': ('FanDuel', 2.4),
            'B': ('DraftKings', 2.3),
            'Draw': ('DraftKings', 2.5),
        })

    @staticmethod
    def _book(key, title, prices):
        names = ['A', 'B', 'Draw']
        return {
            'key': key,
            'title': title,
            'markets': [{
                'key': 'h2h',
                'outcomes': [
                    {'name': name, 'price': price}
                    for name, price in zip(names, prices)
                ],
            }],
        }


class MainTests(unittest.TestCase):
    def test_historical_sportsbook_filter_accepts_dict_odds(self):
        data = [
            {
                'match_name': 'Included match',
                'best_outcome_odds': {
                    'A': {'bookmaker': 'DraftKings', 'odds': 2.1},
                    'B': {'bookmaker': 'FanDuel', 'odds': 2.1},
                },
            },
            {
                'match_name': 'Excluded match',
                'best_outcome_odds': {
                    'A': ['DraftKings', 2.1],
                    'B': ['OtherBook', 2.1],
                },
            },
        ]

        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / 'opportunities.json'
            input_path.write_text(json.dumps(data), encoding='utf-8')
            output = io.StringIO()
            argv = [
                'main.py', '--input', str(input_path), '--sportsbooks',
                'DraftKings,FanDuel', '--unformatted'
            ]
            with patch('sys.argv', argv), redirect_stdout(output):
                main.main()

        results = json.loads(output.getvalue())
        self.assertEqual([item['match_name'] for item in results], ['Included match'])
        self.assertEqual(
            {leg['bookmaker'] for leg in results[0]['analysis']['legs']},
            {'DraftKings', 'FanDuel'},
        )


if __name__ == '__main__':
    unittest.main()
