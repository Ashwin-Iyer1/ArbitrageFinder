"""Read-only odds analysis. Default input is the historical repository snapshot."""
import argparse
import json
import os
from pathlib import Path
from src.stakes import allocate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=Path(__file__).with_name('arbitrage_opportunities.json'))
    parser.add_argument('--live-read-only', action='store_true', help='Fetch odds explicitly; consumes API quota, requires API_KEY')
    parser.add_argument('-s', '--sportsbooks', nargs='+', help='Limit sportsbook selection (e.g. DraftKings FanDuel)')
    parser.add_argument('-k', '--key', default=os.environ.get('API_KEY'))
    parser.add_argument('-r', '--region', choices=['eu','us','au','uk'], default='eu')
    parser.add_argument('-c', '--cutoff', type=float, default=0, help='Minimum theoretical return percent')
    parser.add_argument('--budget', type=float, default=100)
    parser.add_argument('--commission', type=float, default=0, help='Illustrative commission on winning profit, percent')
    parser.add_argument('-u', '--unformatted', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.live_read_only:
            from dotenv import load_dotenv
            from src.logic import get_arbitrage_opportunities
            load_dotenv()
            key = args.key or os.environ.get('API_KEY')
            if not key: parser.error('API_KEY is required for explicit live reads')
            data = list(get_arbitrage_opportunities(key, args.region, args.cutoff / 100, sportsbooks=args.sportsbooks))
        else:
            data = json.loads(args.input.read_text(encoding='utf-8'))
            if args.sportsbooks:
                allowed = {s.strip().lower() for arg in args.sportsbooks for s in arg.split(',') if s.strip()}
                filtered_data = []
                for item in data:
                    odds = item.get('best_outcome_odds', {})
                                        books = {v[0].strip().lower() if isinstance(v, (list, tuple)) and v else v.get('bookmaker', '').strip().lower() for v in odds.values() if (isinstance(v, (list, tuple)) and v) or (isinstance(v, dict) and 'bookmaker' in v)}
                    if books and books.issubset(allowed):
                        filtered_data.append(item)
                data = filtered_data
        results = []
        for item in data:
            result = allocate(item['best_outcome_odds'], args.budget, args.commission / 100)
            if result['theoreticalReturn'] >= args.cutoff / 100:
                results.append({**item, 'analysis': result, 'sourceMode': 'live-read-only' if args.live_read_only else 'historical-snapshot'})
        results.sort(key=lambda item: item['analysis']['worstNet'], reverse=True)
        if args.output: args.output.write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
        if args.unformatted:
            print(json.dumps(results, indent=2))
        else:
            print(f'{len(results)} settlement analyses; no orders. Saved input is historical, not current odds.')
            for item in results:
                result = item['analysis']
                print(f"{item['match_name']}: spent {result['spent']:.2f}; worst net {result['worstNet']:.2f}; return {result['theoreticalReturn']*100:.2f}%")
                for leg in result['legs']: print(f"  {leg['outcome']}: {leg['stake']:.2f} at {leg['odds']} ({leg['bookmaker']})")
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
