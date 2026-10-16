import json
import subprocess
import unittest
from src.stakes import allocate
from src.logic import process_data


class StakesTest(unittest.TestCase):
    def test_equal_odds_retain_outcomes(self):
        r = allocate({'A': ['One', 2.1], 'B': ['Two', 2.1]})
        self.assertEqual([l['stake'] for l in r['legs']], [50, 50])
        self.assertAlmostEqual(r['worstNet'], 5)

    def test_rounding_respects_budget_and_worst_case(self):
        r = allocate({'A': ['One', 3.3], 'B': ['Two', 3.4], 'Draw': ['Three', 3.5]}, 101.03)
        self.assertAlmostEqual(sum(l['stake'] for l in r['legs']), 101.03)
        self.assertEqual(r['worstNet'], min(l['netIfWins'] for l in r['legs']))

    def test_commission_can_remove_edge(self):
        r = allocate({'A': ['One', 2.01], 'B': ['Two', 2.01]}, 100, .05)
        self.assertLess(r['worstNet'], 0)

    def test_invalid_and_small_budget(self):
        for b in [0, float('nan'), -3]:
            with self.assertRaises(ValueError): allocate({'A': ['One', 2], 'B': ['Two', 2]}, b)
        self.assertFalse(allocate({'A': ['One', 2], 'B': ['Two', 2]}, .01)['allLegsFunded'])

    def test_javascript_python_parity(self):
        cases = [{'odds': {'A': ['One', 2.1], 'B': ['Two', 2.1]}, 'budget': 100, 'fee': 0}, {'odds': {'A': ['X', 3.15], 'B': ['Y', 4.4], 'Draw': ['Z', 2.9]}, 'budget': 123.45, 'fee': .02}]
        js = "import {allocate} from './lab.js';console.log(JSON.stringify(JSON.parse(process.argv[1]).map(c=>allocate(c.odds,c.budget,c.fee))))"
        results = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', js, json.dumps(cases)], text=True))
        for case, actual in zip(cases, results):
            expected = allocate(case['odds'], case['budget'], case['fee'])
            self.assertAlmostEqual(actual['worstNet'], expected['worstNet'])
            self.assertEqual([l['stake'] for l in actual['legs']], [l['stake'] for l in expected['legs']])

    def test_only_complete_h2h_books(self):
        match = {'home_team': 'A', 'away_team': 'B', 'commence_time': 9999999999, 'sport_key': 'soccer_test', 'bookmakers': [{'title': 'X', 'markets': [{'key': 'spreads', 'outcomes': [{'name': 'A', 'price': 99}]}, {'key': 'h2h', 'outcomes': [{'name': 'A', 'price': 3}, {'name': 'B', 'price': 4}]}]}]}
        self.assertEqual(list(process_data([match])), [])
        match['bookmakers'][0]['markets'][1]['outcomes'].append({'name': 'Draw', 'price': 3.5})
        r = list(process_data([match]))[0]
        self.assertEqual(r['best_outcome_odds']['A'][1], 3)

    def test_empty_markets_are_skipped(self):
        m = {'home_team':'A','away_team':'B','commence_time':9999999999,'sport_key':'basketball_test','bookmakers':[{'title':'X','markets':[]}]}
        self.assertEqual(list(process_data([m])), [])


if __name__ == '__main__': unittest.main()
