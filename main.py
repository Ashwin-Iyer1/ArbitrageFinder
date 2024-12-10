"""A simple tool to find sports betting arbitrage opportunities.

The tool fetches the odds from The Odds API (https://the-odds-api.com/) and compares the odds at different
bookmakers to each other in order to determine whether there are profitable and risk-free bets available."""
from src.logic import get_arbitrage_opportunities
import os
import argparse
from dotenv import load_dotenv
from rich import print
import json

load_dotenv()



def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        prog="Arbitrage Finder",
        description=__doc__
    )
    parser.add_argument(
        "-k", "--key",
        default=os.environ.get("API_KEY"),
        help="The API key from The Odds API. If left blank it will default to the value of $API_KEY."
    )
    parser.add_argument(
        "-r", "--region",
        choices=["eu", "us", "au", "uk"],
        default="eu",
        help="The region in which to look for arbitrage opportunities."
    )
    parser.add_argument(
        "-u", "--unformatted",
        action="store_true",
        help="If set, turn output into the json dump from the opportunities."
    )
    parser.add_argument(
        "-c", "--cutoff",
        type=float,
        default=0,
        help="The minimum profit margin required for an arb to be displayed. Inputted as a percentage."
    )
    args = parser.parse_args()

    cutoff = args.cutoff/100

    arbitrage_opportunities = get_arbitrage_opportunities(key=args.key, region=args.region, cutoff=cutoff)

    arbitrage_opportunities = list(arbitrage_opportunities)

    with open("arbitrage_opportunities.json", "w") as f:
        json.dump(arbitrage_opportunities,f, indent=4)


    if args.unformatted:
        print(arbitrage_opportunities)
    else:
        print(f"{len(arbitrage_opportunities)} arbitrage opportunities found {':money-mouth_face:' if len(arbitrage_opportunities) > 0 else ':man_shrugging:'}")
        sorted_arbitrage_opportunities = []
        sorted_average_profit = []
        profit_per_dollar = []
        for arb in arbitrage_opportunities:
            valueList = []
            betDict = {}
            print(f"\t[italic]{arb['match_name']} in {arb['league']} [/italic]")
            print(f"\t\tTotal implied odds: {arb['total_implied_odds']} with these odds:")
            for key, value in arb['best_outcome_odds'].items():
                print(f"\t\t[bold red]{key}[/bold red] with [green]{value[0]}[/green] for {value[1]}")
                valueList.append(float(value[1]))
            largestValue = max(valueList)
            for value in valueList:
                if value in betDict:
                    betDict[value - .001] = round((largestValue * 100) / value, 4)
                if value == largestValue:
                    betDict[value] = 100
                else:
                    betDict[value] = round((largestValue * 100) / value, 4)
            Liability = sum(betDict.values())
            absoluteProfit = []
            for key, value in betDict.items():
                absoluteProfit.append(round((key * value) - Liability, 2))
            avgProfit = sum(absoluteProfit) / len(absoluteProfit)
            total_absoluteProfit = sum(absoluteProfit)
            print(f"\t\t absolute profit: {total_absoluteProfit:.2f}")
            print(f"\t\t Average profit: [green]${avgProfit:.2f}[/green]")
            print(f"\t\t amounts to bet: {betDict}")
            print(f"\t\t Liability: {Liability:.2f}")
            sorted_arbitrage_opportunities.append((arb, total_absoluteProfit))
            sorted_average_profit.append((arb, avgProfit))
            profit_per_dollar.append((arb, total_absoluteProfit/Liability))
        sorted_average_profit = sorted(sorted_average_profit, key=lambda x: x[1], reverse=True)
        sorted_arbitrage_opportunities = sorted(sorted_arbitrage_opportunities, key=lambda x: x[1], reverse=True)
        profit_per_dollar = sorted(profit_per_dollar, key=lambda x: x[1], reverse=True)

    print("\nSorted Arbitrage Opportunities by Absolute Profit:")
    for arb, profit in sorted_arbitrage_opportunities:
        print(f"\t[italic]{arb['match_name']} in {arb['league']}[/italic]: Absolute Profit = {profit:.2f}")
    print("\n")
    print("\n Sorted Arbitrage Opportunities by Average Profit:")
    for arb, profit in sorted_average_profit:
        print(f"\t[italic]{arb['match_name']} in {arb['league']}[/italic]: Average Profit = {profit:.2f}")
    print("\n")
    print("\n Sorted Arbitrage Opportunities by Profit per Dollar:")
    for arb, profit in profit_per_dollar:
        print(f"\t[italic]{arb['match_name']} in {arb['league']}[/italic]: Profit per Dollar = {profit:.2f}")

            

if __name__ == '__main__':
    main()