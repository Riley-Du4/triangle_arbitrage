import requests
import json
import time
import os
from datetime import datetime
from itertools import permutations
from itertools import combinations
import networkx as nx
import math
from networkx.classes.function import path_weight
import matplotlib.pyplot as plt
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca_trade_api.rest import REST, TimeFrame
from alpaca.trading.enums import OrderSide, TimeInForce
import csv
import base64


BASE_URL = "https://paper-api.alpaca.markets"
API_KEY= 'xxxxxx'
API_SECRET = 'xxxxx'
client = TradingClient(API_KEY, API_SECRET, paper=True)
account = client.get_account()
available_balance = float(account.cash)
print("your available paper balance:", available_balance)
github_token = "xxxxx"
github_rep = "xxxxx"
github_branch = "main"
file_path = "final_project/exchange_info.json"
#used crypto currencies to identify potential arbitrage
coins = {"algorand":"algousd",
               "cardano":"ada",
               "bitcoin-cash":"bch",
               "chainlink":"link",
               "litecoin":"ltc",
               "ethereum":"eth",
               "bitcoin":"btc",
               "tether":"usdt",
               "bitcoin cash":"bch",
               "bnb":"bnb",
               "USDC":"usdc",
               "Dogecoin":"doge",
               "avalanche":"avax"}
edges = []
#function to pull crytpo currencies and tickers into one json
def get_exchange_info():
    #identify keys and values
    ids = ','.join(coins.keys())
    vs_currencies = ','.join(coins.values())
    #insert keys and values into url
    url = 'https://api.coingecko.com/api/v3/simple/price?ids='+ids+'&vs_currencies='+vs_currencies
    try:
        #load json file for all currencies
        response = requests.get(url)
        data = response.json()
        path = r"C:\Users\Riley\Documents\vscode_projects\data5500_hw\Inclasswork\Hw9\exchange_info.json"
        with open(path, "w") as json_file:
            json.dump(data, json_file, indent=4)
        return data
    #create exception if data can not be pulled
    except requests.exceptions.RequestException as e:
        print("An error occurred:", e)
        return None
#call function
data = get_exchange_info()

#build a directed graph from the created crypto json
def build_graph(data):
    g = nx.DiGraph()
    for coin, coin_rate in data.items():
        #get the source node's ticker
        node_from = coins.get(coin)
        #skip if data is missing a coin
        if not node_from or coin_rate.get(node_from) is None:
            print(f"skipping missing data for {coin}.")
            continue
        #add edges between nodes besed on exchange rates
        for tkr, rate in coin_rate.items():
            #only use tickers that is in the coins dictionary
            if tkr in coins.values():
                node_to = tkr
                if node_from and node_to:
                    g.add_edge(node_from,node_to, weight=rate)
            else:
                print(f"skipping invalid ticker {tkr} for {coin}")
    return g
#build the graph using the exchange data
if data:
    graph = build_graph(data)
    print("Graph built with nodes and edges:", graph.nodes, graph.edges)
#function to check for arbitrage in the constructed graph

def arbitrage_checker(graph):
    best_path = []
    best_weight = 1
    rows = []
    now = datetime.now()
    date = now.strftime("%Y.%m.%d-%H.%M.%S")
    #iterate through all unique pairs of nodes
    for c1, c2 in combinations(graph.nodes,2):
        #iterate over all simple paths from the source to the target
        for path in nx.all_simple_paths(graph, source=c1,target=c2):
            forward_weight = 1
            #calculate forward path weight using negative logarithm to transform rates
            for i in range(len(path)-1):
                forward_weight *= graph[path[i]][path[i+1]]['weight']
            #find the revers path and its weight
            reverse_path = list(reversed(path))
            reverse_weight = 1
            for i in range(len(reverse_path)-1):
              if graph.has_edge(reverse_path[i],reverse_path[i+1]):
                reverse_weight *= graph[reverse_path[i]][reverse_path[i+1]]['weight']
              else:
                reverse_weight = 0
                break
            #combine the forward and reverse weights.
            combined_weight = forward_weight * reverse_weight
            #save the currency pair and exhange rate
            rows.append({"Currency Pair": f"{path[0]},{path[-1]}","Exchange Rate":combined_weight})
            #check for arbitrage opportunity if combined weight is over 1.
            if combined_weight > best_weight :
                best_weight = combined_weight
                best_path.append(path)
                # print(f"Arbitrage opportunity found along path {path} with path weight: {combined_weight}")
            else:
                continue
                # print("no arbitrage opportunity found")
    filename = f"currency_pair_",date,".csv"
    with open("currency_pair_", mode="w", newline="") as file:
        fieldnames = ["Currency Pair","Exchange Rate"]
        writer = csv.DictWriter(file,fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(' ')
    print("the best arbitrage path is ",best_path,"and the arbitrage is ",best_weight)
    return best_path[-1]


arbitrage_checker(graph)
best_arbitrage_path = arbitrage_checker(graph)

def simulate_trades(path, available_balance):
  current_amount = available_balance
  for i in range(len(path)-1):
    currency_from = path[i].upper()
    currency_to = path[i + 1].upper()

    #create buy symbol for example BTC/USD
    buy_symbol = f"{currency_from}USD".replace("\\","")
    sell_symbol = f"{currency_to}USD".replace("\\","") if i +2 < len(path) else f"{currency_to}/{path[0]}"
    # Calculate the buy/sell amount based on current holdings and exchange rate
    exchange_rate = graph[currency_from.lower()][currency_to.lower()]['weight']  # Get rate from graph
    buy_amount = current_amount  

    # Execute buy order
    try:
        buy_order = MarketOrderRequest(
            symbol=buy_symbol,
            qty=1,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.GTC
        )
        buy_response = client.submit_order(order_data=buy_order)
        print(f"Buy order placed: {buy_response}")
    except Exception as e:
        print(f"Error placing buy order for {buy_symbol}: {e}")
        continue

    # Update current holdings after buy
    current_amount = buy_amount * exchange_rate  # Reflect the exchange

  # Finally, sell back to the original currency to realize profit
    try:
        sell_order = MarketOrderRequest(
            symbol=sell_symbol,  # Sell back to the starting currency
            qty=1,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.GTC
        )
        sell_response = client.submit_order(order_data=sell_order)
        print(f"Sell order placed for {sell_symbol}")
    except Exception as e:
        print(f"Error placing sell order: {e}")
        continue
  final_currency = path[-1]
  if final_currency != path[0].upper():
      final_symbol = f"{final_currency}/USD"
      try:
          final_sell_order = MarketOrderRequest(
              symbol = final_symbol,
              qty= 1,
              side= OrderSide.SELL,
              TimeInForce=TimeInForce.GTC
          )
          final_sell_response = client.submit_order(order_data=final_sell_order)
          print(f"Final sell order placed.")
      except Exception as e:
          print(f"Error placing final sell order for {final_symbol}: {e}")
      else:
          print("Finalized trades.")

simulate_trades(best_arbitrage_path, available_balance)
