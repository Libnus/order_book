

# order book implementation

from enum import Enum
import heapdict
import random
from fastapi import FastAPI, WebSocket
import asyncio
import uvicorn

app = FastAPI()
connected_clients = set()


async def send_order_book(websocket, stocks):
    stocks_m = {}

    for stock in stocks:
        i = 0
        asks = []
        bids = []
        for sell in stock.order_book["sell"]:
            order = stock.order_book["sell"][sell]
            asks.append({
                "price": order.price,
                "quantity": order.quant
            })
            i+=1


        i = 0
        for buy in stock.order_book["buy"]:
            if i > 10: break
            order = stock.order_book["buy"][buy]
            bids.append({
                "price": order.price,
                "quantity": order.quant
            })
            i+=1


        asks = asks[-10:]
        asks.sort(key=lambda x: x["price"])
        bids.sort(key=lambda x: x["price"], reverse=True)
        stocks_m[str(stock.stock_id)] = {"asks": asks, "bids": bids, "history": stock.history, "price": stock.price}
        # asks.append(ask)
        # bids.append(bid)


    message = {"stocks": stocks_m}
    # await websocket.send(json.dumps(message))
    try:
        await websocket.send_json(message)
    except Exception as e:
        print("Failed to send to a client:", e)
        connected_clients.remove(websocket)
        exit(1)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        while True:
            await asyncio.sleep(1)  # keep connection alive
    except Exception as e:
        print("Client disconnected:", e)
    finally:
        connected_clients.remove(websocket)

TIME = 0

class Stock:
    stock_id = 0
    def __init__(self):
        self.history = [] # history of prices over time
        self.stock_id = Stock.stock_id
        Stock.stock_id += 1
        self.order_book = {"sell": heapdict.heapdict(), "buy": heapdict.heapdict()}
        self.price = random.uniform(90.0, 120.0) # the last traded price
        self.mean_reversion = self.price + random.uniform(-20.0, 20.0)
    '''
    takes an order and adds it to the order book

    order: (price, quant, seller)
    '''
    def buy(self, order):
        # TODO if market order match right away

        # there is a bidder buying
        # heapq.heappush(self.order_book["buy"], (-order[0], order[1], order[2]))

        # reserve the cash
        # NOTE this ensures bots dont spend the money while the order is being filled
        order.trader.cash -= order.order_cost

        # if the trader doesn't have enough cash dont add the order
        if order.trader.cash < 0.0:
            print("trader doesn't have enough cash for order < 0", order.trader.strat, order.trader.cash, order.order_cost, order.order_type)
            order.trader.cash += order.order_cost
            order.quant = 0
            return
            # exit(1)

        if order.stock not in order.trader.shares:
            order.trader.shares[order.stock] = {"quant": 0}

        # add the buy order
        print("MARKET BUY :: ", order.price, order.quant)
        self.order_book["buy"][order.order_id] = order


    def sell(self, order):
        # heapq.heappush(self.order_book["sell"], (order[0], order[1], order[2]))

        # if order.quant > order.trader.shares:
        #     print("selling more shares than onwed!!!!")
        #     exit(1)

        # remove shares from seller to avoid double selling
        order.trader.shares[order.stock]["quant"] -= order.quant

        # if order.trader.shares[order.stock]["quant"] == 0:
        #     del order.trader.shares[order.stock]

        # add the sell order
        print("MARKET SELL :: ", order.price, order.quant)
        self.order_book["sell"][order.order_id] = order
        # self.orders[order.order_id] = order

    # return best bid price
    def bid(self):
        if len(self.order_book["buy"]) > 0:
            return self.order_book["buy"].peekitem()[1].price
        return self.price


    # return best ask price
    def ask(self):
        if len(self.order_book["sell"]) > 0:
            return self.order_book["sell"].peekitem()[1].price
        return self.price

    # NOTE there is no modifying quant as of yet
    # new_quant is expected to be the quant of the current order
    # i.e. you canno tmodify how manys hares you are selling or buying
    def modify_order(self, order, new_price, new_quant):
        if type(order) is BuyOrder:
            buy_order = self.order_book["buy"][order.order_id]


            # we need to reserve more cash if the new price is higher
            if new_price > buy_order.price:
                diff = new_price - buy_order.price
                cash_needed = diff*new_quant

                # reserve more cash from trader
                if buy_order.trader.cash < cash_needed:
                    # dont modify the order
                    return

                order_cost_before = buy_order.order_cost
                buy_order.trader.cash -= cash_needed
                buy_order.order_cost += cash_needed # make sure to track this in case we need to return it

            buy_order.price = new_price
            buy_order.quant = new_quant
            self.order_book["buy"][order.order_id] = buy_order
        else:
            sell_order = self.order_book["sell"][order.order_id]
            sell_order.price = new_price
            sell_order.quant = new_quant
            self.order_book["sell"][order.order_id] = sell_order

    # cancel orders
    def cancel(self, order):
        if type(order) is BuyOrder:
            del self.order_book["buy"][order.order_id]
            # refund any amount take as reserve
            # NOTE this only applies to cancelling buy orders
            print("cancel", order.price, order.quant, order.order_cost, order.execution_cost)
            order.trader.cash += order.order_cost - order.execution_cost
        else:
            order.trader.shares[order.stock]["quant"] += order.quant
            del self.order_book["sell"][order.order_id]


    '''
    match orders
    '''
    def match(self):
        # this is limit orders

        # edge case: the order book is empty
        print()
        while True:
            if len(self.order_book["buy"]) == 0 or len(self.order_book["sell"]) == 0:
                break

            if self.order_book["buy"].peekitem()[1].price < self.order_book["sell"].peekitem()[1].price:
                break


            # branch: if the max buy is greater than the min sell
            # check if its a market order

            # match the buyer and seller
            buyer = self.order_book["buy"].peekitem()
            seller = self.order_book["sell"].peekitem()

            print("MATCHED BUYER:", buyer[1].price, "SELLER:", seller[1].price)

            quant = min(buyer[1].quant, seller[1].quant)

            if seller[1].quant <= 0:
                print("ERROR, seller has no shares left to sell", seller[1].quant)
                exit(1)


            # if seller[1].trader.shares < seller[1].quant:
            #     print(seller[1].trader == buyer[1].trader)
            #     print(buyer[1].quant, seller[1].quant)
            #     print("selling more shares than owned", seller[1].trader.shares, seller[1].quant)
            #     exit(1)

            buyer[1].quant -= quant
            seller[1].quant -= quant

            # after match we need to add this to the execution cost
            buyer[1].execution_cost += seller[1].price*quant

            # then give seller the cash
            seller[1].trader.cash += seller[1].price*quant

            # adjust last traded price
            self.price = seller[1].price # sell at the seller price

            # update the shares quant each trader owns
            buyer[1].trader.shares[self]["quant"] += quant

            # TODO avoid double selling (fixed)
            # seller[1].trader.shares -= quant

            if seller[1].trader.shares[self]["quant"] < 0:
                print("error, seller shares owned < 0", seller[1].trader.shares)
                exit(1)


            # the quantity is filled now pop it
            if buyer[1].quant <= 0:
                self.order_book["buy"].popitem()
            if seller[1].quant <= 0:
                self.order_book["sell"].popitem()

class OrderType(Enum):
    MARKET_ORDER = 1
    LIMIT_ORDER = 2

class Order:
    order_id = 0
    def __init__(self, trader, stock, price, quant, order_type):

        global TIME
        self.order_type = order_type
        self.trader = trader
        self.stock = stock

        self.order_cost = 0.0
        self.execution_cost = 0.0

        self.order_id = Order.order_id
        Order.order_id += 1
        self.quant = quant
        self.price = price
        self.time = TIME

    def modify(self, price, quant):
        self.stock.modify_order(self, price, quant)

    # cancel order
    def cancel(self):
        self.stock.cancel(self)

class BuyOrder(Order):
    def __init__(self, trader, stock, price, quant, order_type):
        super().__init__(trader, stock,price,quant, order_type)
        if self.order_type is OrderType.MARKET_ORDER:
           self.price = stock.ask() # set the price to highest ask
        self.order_cost = self.price*quant

    def __lt__(self, other):
        if self.price != other.price: return self.price > other.price
        return TIME - self.time > TIME -  other.time


class SellOrder(Order):
    def __init__(self, trader, stock, price, quant, order_type):
        super().__init__(trader, stock, price, quant, order_type)
        if self.order_type is OrderType.MARKET_ORDER:
            self.price = stock.bid() # set the price to highest bid

    def __lt__(self, other):
        if self.price != other.price: return self.price < other.price
        return TIME - self.time > TIME -other.time

class Strategy:
    def __init__(self, trader):
        self.trader = trader

    def step(self, stock):
        raise NotImplementedError

# class RandomBot(Strategy):
#     def __init__(self, trader):
#         super().__init__(trader)

#     def step(self, stocks):
#         # pick a ranodm stock to buy or sell


#     def manage(self, trader):

class MomentumBot(Strategy):
    def __init__(self, trader):
        super().__init__(trader)
        self.lookback = random.randint(2,20)
        self.momentum_threshold = random.uniform(0.005, 0.03)
        self.aggression = random.uniform(0.2, 1.0)

    def step(self, stocks):
        n_trials = 10
        # first review our current porfolio
        for stock in self.trader.shares:
            if len(stock.history) < self.lookback: return

            past_price = stock.history[-self.lookback]
            momentum = (stock.price - past_price) / past_price

            if momentum < -self.momentum_threshold:
                max_sell = self.trader.shares[stock]["quant"]
                quant = int(max_sell * self.aggression)
                self.trader.sell(stock, quant)


        stocks = random.sample(stocks, len(stocks))
        for stock in stocks:

            if len(stock.history) < self.lookback: return

            past_price = stock.history[-self.lookback]
            momentum = (stock.price - past_price) / past_price

            if momentum > self.momentum_threshold:
                max_buy = int(self.trader.cash // stock.price)
                quant = int(max_buy * self.aggression)
                self.trader.buy(stock, quant)

        

class MeanReversion(Strategy):
    def __init__(self, trader):
        super().__init__(trader)
        #self.value_bias = random.gauss(-5.0, 5.0)  # how much their idea of "value" is distorted
        self.risk_tolerance = random.uniform(0.05, 2.0)  # how aggressively to act
        self.reversion_threshold = random.uniform(0.01, 0.25)  # min gap to trigger a trade

        # value a stock and then place an order based on that
    def mean_revert(self, stock):
        pass

    def eval_idea(self, stock, quant):
        score = 0

        value_bias = random.gauss(-10.0, 10.0)
        fair_value = stock.mean_reversion + value_bias
        price = stock.price
        deviation = (fair_value - price) / price


        weight = deviation * self.risk_tolerance

        # if buying get positive deivation (possible undervalued)
        # else selling we want negative deviation (possible overvalue)
        direction = 1 if quant > 0 else -1 if quant < 0 else 0
        score = int(abs(quant) * weight * direction)

        return score



    def step(self, stocks):

        # use monte carlo to eval ideas
        n_trials = 25
        best_score = float(0)

        best_idea = [(stock, 0) for stock in stocks]
        stocks = random.sample(stocks, len(stocks)) # shuffle for each time step to make sure bots dont just waste their money on the first few stocks

        for _ in range(n_trials):
            idea = []
            idea_score = 0
            cash = self.trader.cash
            # max_cash = 0
            #


            # we can do better by perofmring an o(n) loop and randomly deicding a porfolio to try

            for i, stock in enumerate(stocks):
                if random.random() < 0.33: continue # randomly skip to get different portfolio ideas between trials

                current = self.trader.shares.get(stock, {"quant": 0})["quant"]
                # max_cash += current * stock.price
                max_buy = int(cash // stock.price)
                max_sell = int(current)

                if random.random() < 0.5:
                    # SELL
                    delta = -random.randint(1, max_sell) if max_sell > 0 else 0
                else:
                    # BUY
                    delta = random.randint(1, max_buy) if max_buy > 0 else 0
                    cash -= delta * stock.price # only sub cash if we buy since selling doesn't give cash right away

                idea.append((stock, delta))
                idea_score += self.eval_idea(stock, delta)

            if idea_score > best_score:
                best_score = idea_score
                best_idea = idea

        # now with the best idea in mind, perform actions
        for quant in best_idea:
            if quant[1] > 0:
                self.trader.buy(quant[0], abs(quant[1]))
            if quant[1] < 0: # selling logic
                self.trader.sell(quant[0], abs(quant[1]))



                # OLD LOGIC BELOW


        # self.value_bias = random.gauss(-30.0, 30.0)
        # fair_value = stock.mean_reversion + self.value_bias

        # price = stock.price
        # deviation = (fair_value - price) / price

        # # --- BUY LOGIC ---
        # if deviation > self.reversion_threshold:
        #     weight = deviation * self.risk_tolerance
        #     budget = self.trader.cash * weight
        #     quant = int(budget // price)

        #     if quant > 0:
        #         self.trader.buy(stock, quant)

        # # --- SELL LOGIC ---
        # elif deviation < self.reversion_threshold:
        #     owned = self.trader.shares
        #     quant = int(owned * abs(deviation) * self.risk_tolerance)
        #     quant = min(quant, owned)

        #     if quant > self.trader.shares:
        #         print(owned, abs(deviation), self.risk_tolerance)
        #         print("trying to sell more shares than owned", quant, self.trader.shares)
        #         exit(1)

        #     if quant > 0:
        #         self.trader.sell(stock, quant)

class MarketMakerBot(Strategy):
    def __init__(self, trader):
        super().__init__(trader)

    def step(self, stock):
        factor = 2
        # p_last = stock.price

        if TIME > 100: factor = 1

        # p_bid = p_last * (1-self.spread/2)
        can_buy = int(self.trader.cash // stock.price)
        self.trader.buy(stock, min(5*factor, can_buy))

        # post a sell
        # p_ask = p_last * (1+self.spread/2)
        self.trader.sell(stock, min(5*factor, self.trader.shares[stock]["quant"]))

# TODO implement contrarian investing bot
# TODO implement arbitrage bot
# TODO technical indicator bot
# TODO news reactive bot
# TODO stop-loss take-profit bot
# TODO inventory constrained balancing


# TODO noise bot
class NoiseBot(Strategy):
    def __init__(self, trader, trade_chance=0.3, max_positions=3):
        super().__init__(trader)
        self.max_positions = 3
        self.trade_chance = 0.3

   # requires stocks to contain at laest 3 elements
    def step(self, stocks):
        select = random.sample(stocks, self.max_positions)

        for stock in select:
            if random.random() > self.trade_chance:
                continue

            action = random.choice(["buy", "sell", "hold"])

            if action == "buy":
                # ranodmly decide how much to buy
                max_buy = int(self.trader.cash // stock.ask())
                if max_buy > 0:
                    quant = random.randint(1, max_buy)
                    self.trader.buy(stock, quant)
            elif action == "sell":
                # ranodmly decide how much to sell
                max_sell = self.trader.shares.get(stock, {"quant": 0})["quant"]
                if max_sell > 0:
                    quant =  random.randint(1, max_sell)
                    self.trader.sell(stock, quant)


    
class OrderStrategy:

    def __init__(self, trader):
        self.trader = trader
        self.sell_orders = set()
        self.buy_orders = set()


    def manage(self):
        pass

    # def step(self):
    #     pass

class Undercut(OrderStrategy):
    def buy(self, stock, quant):
        target_price = stock.price#max(stock.ask() - 0.01,0.01)

        # check if the target price exceeds cost
        # if target_price * quant > self.trader.cash:
        #     print("just before heres hoping", stock.price)
        #     target_price = stock.price

        # 70% chance its a limit order
        prob = random.random()

        order_type = OrderType.MARKET_ORDER
        if prob <= 0.5: order_type = OrderType.LIMIT_ORDER

        order = BuyOrder(self.trader, stock, target_price, quant, order_type)
        self.buy_orders.add(order)
        stock.buy(order)

    def sell(self, stock, quant):
        quant = min(self.trader.shares[stock]["quant"], quant)
        if quant == 0: return

        # 70% chance its a limit order
        prob = random.random()
        order_type = OrderType.MARKET_ORDER
        if prob <= 0.5: order_type = OrderType.LIMIT_ORDER

        target_price = max(stock.bid() + 0.01,0.01)
        order = SellOrder(self.trader, stock, target_price, quant, order_type)
        self.sell_orders.add(order)
        stock.sell(order)

    def manage(self):
        # print("managin", len(self.buy_orders))
        # step over the sells and buys
        new_sells = set()
        for sell in self.sell_orders:
            if sell.quant <= 0: continue

            if (TIME + (sell.time+1)) % 5 == 0:
                if sell.order_type == OrderType.LIMIT_ORDER:
                    # lower the price target
                    target_price = max(sell.stock.bid(), sell.price - (0.005*sell.price))
                    sell.modify(target_price, sell.quant)
                else:
                    # cancel the order just in case we have any lingering market orders
                    sell.cancel()
                    continue
            elif TIME - sell.time > 20: # if the order has been on the market for more than 20 steps
                # cancel the order
                sell.cancel()
                continue

            new_sells.add(sell)


        if self.trader.cash < 0.0:
            print("out of cash before buy loop")
            exit(1)
        new_buys = set()
        for buy in self.buy_orders:

            if buy.quant <= 0: continue

            # adjusting buy price

            if (TIME + (buy.time+1)) % 5 == 0:
                # print("adjusting buy price")
                if buy.order_type == OrderType.LIMIT_ORDER:
                    target_price = min(buy.stock.ask(), buy.price + (0.005*buy.price))
                    if self.trader.cash < 0.0:
                        print("outo fcash after modify buy")
                        exit(1)
                    buy.modify(target_price, buy.quant)
                    if self.trader.cash < 0.0:
                        print("outo fcash after modify buy")
                        exit(1)
                else:
                    if self.trader.cash < 0.0:
                        print("outo fcash after modify buy2")
                    buy.cancel()
                    if self.trader.cash < 0.0:
                        print("outo fcash after modify bu2y")
                        exit(1)
                    continue

            elif TIME - buy.time > 20: # if the order has been on the market for more than 20 steps
                # cancel the order
                if self.trader.cash < 0.0:
                    print("outo fcash before cancel buy")
                buy.cancel()
                if self.trader.cash < 0.0:
                    print("outo fcash afeter acncel buy")
                    exit(1)
                continue
            new_buys.add(buy)

        self.buy_orders = new_buys
        self.sell_orders = new_sells

    # def step(self, stock):
    #     # NOTE for debugging
    #     # if TIME == 0:
    #     #     self.buy(stock, 5)


    #     if TIME > 250:
    #         prob_buy = 0.0005
    #         prob_sell = 0.5
    #     # else:
    #     #     prob_buy = 0.05
    #     #     prob_sell = 0.4
    #     else:
    #         prob_buy = 0.0005
    #         prob_sell = 0.50

    #     # return

    #     # buy or sell
    #     prob = random.random()

    #     if prob <= prob_buy: # buy the stock with a 25% chance
    #         # buy for slightly less than current ask
    #         self.buy(stock, random.randint(1, 10)) # buy a random amount 1 to 10
    #     elif prob <= prob_sell: self.sell(stock,random.randint(1, 10)) # 5% chance of selling
        # 70% chance of doing nothing


class MarketOrder(OrderStrategy):
    def __init__(self, trader):
        super().__init__(trader)

    def buy(self, stock, quant):
        order = BuyOrder(self.trader, stock, 0.0, quant, OrderType.MARKET_ORDER)
        self.buy_orders.add(order)
        stock.buy(order)

    def sell(self, stock, quant):
        order = SellOrder(self.trader, stock, 0.0, quant, OrderType.MARKET_ORDER)
        self.sell_orders.add(order)
        stock.sell(order)

    def manage(self):
        new_sells = set()
        for sell in self.sell_orders:
            if sell.quant <= 0: continue
            if TIME - sell.time >= 10:
                sell.cancel()
                continue
            new_sells.add(sell)

        new_buys = set()
        for buy in self.buy_orders:
            if buy.quant <= 0: continue
            if TIME - buy.time >= 10:
                buy.cancel()
                if self.trader.cash < 0.0:
                    print("out of cash here")
                    exit(1)
                continue
            new_buys.add(buy)

        self.buy_orders = new_buys
        self.sell_orders = new_sells


class MarketMaker(OrderStrategy):
    def __init__(self, trader):
        super().__init__(trader)
        # TODO adjust spread based on volatility
        # TODO inventory management
        #       If you own too much stock → lower ask price (sell quicker).
        #       If you own too little stock → raise bid price (buy quicker).
        # TODO adaptive quoting
        #       Move bid and ask around as market price shifts.
        self.spread = 0.02 # spread of 2%

    def buy(self, stock, quant):
        p_last = stock.price
        p_bid = p_last * (1-self.spread/2)

        print("market maker buy ::", p_bid)
        order_type = OrderType.LIMIT_ORDER
        order = BuyOrder(self.trader, stock, p_bid, quant, order_type)

        self.buy_orders.add(order)
        stock.buy(order)

    def sell(self, stock, quant):
        if quant <= 0: return

        p_last = stock.price

        p_ask = p_last * (1+self.spread/2)
        print("market maker sell ::", p_ask)
        order_type = OrderType.LIMIT_ORDER
        order = SellOrder(self.trader, stock, p_ask, quant, order_type)

        self.sell_orders.add(order)
        stock.sell(order)

    # manage orders
    def manage(self):
        # first cancel stale orders
        new_sells = set()
        new_buys = set()

        for sell in self.sell_orders:
            # remove the order if quant is 0
            if sell.quant <= 0: continue
            if TIME - sell.time >= 1:
                sell.cancel()
            else: new_sells.add(sell)

        for buy in self.buy_orders:
            if buy.quant <= 0: continue
            if TIME - buy.time >= 1:
                buy.cancel()
            else: new_buys.add(buy)

        self.buy_orders = new_buys
        self.sell_orders = new_sells


    # perofrm a trader step
    # def step(self, stock):
    #     factor = 2
    #     # post a buy and sell order with spread
    #     # current price
    #     p_last = stock.price

    #     if TIME > 100:
    #         factor = 1

    #     # post a buy
    #     p_bid = p_last * (1-self.spread/2)
    #     self.buy(stock, p_bid, 5*factor)
    #     print("market maker buy ::", p_bid)

    #     # post a sell
    #     p_ask = p_last * (1+self.spread/2)
    #     print("market maker sell ::", p_ask)
    #     self.sell(stock, p_ask, min(5*factor, self.trader.shares))



    
class Trader:
    def __init__(self, moment, strat=MarketMakerBot, order_strat=MarketMaker):
        self.shares = {} # simply keep track of the shares owned
        self.moment = moment
        self.strat = strat(self)
        self.order_strat = order_strat(self) # buying/selling strategy
        self.cash = 500.0

    def buy(self, stock, quant):
        # buy the shares
        # we call strategy for this step
        if quant == 0: return

        self.order_strat.buy(stock, quant)

    def sell(self, stock, quant):
        if quant == 0: return

        # sell the shares
        # we call strategy for this step
        self.order_strat.sell(stock, min(quant, self.shares[stock]["quant"]))
        # self.shares -= quant

    # trader step
    def step(self, stocks):
        # SANITY CHECK
        if self.cash < 0.0:
            print(self.strat, self.cash)
            print("trader cash < 0")
            exit(1)

        # perform a step
        self.strat.step(stocks)
        if self.cash < 0.0:
            print(self.strat, self.cash)
            print('trader at end of step <0 cash')
            exit(1)

        # manage current orders
        self.order_strat.manage()

        if self.cash < 0.0:
            print("out of fucking cahs", self.strat)
            exit(1)

async def simulation():
    global TIME
    moment = 0.6

    factor = 5 # best found so far is 5
    amount = -5
    ratio_mean = 0.65
    ratio_mom = 0.3
    ratio_noise = 0.05

    traders = [Trader(moment, strat=MeanReversion, order_strat=Undercut) for _ in range(int(100*factor*ratio_mean))]
    traders_mom = [Trader(moment, strat=MomentumBot, order_strat=Undercut) for _ in range(int(100*factor*ratio_mom))]
    traders_noise = [Trader(moment, strat=NoiseBot, order_strat=MarketOrder) for _ in range(int(100*factor*ratio_noise))]
    traders = traders + traders_mom + traders_noise
    #stock = Stock()
    stocks = [Stock() for _ in range(10)] # stocks to start

    # market_maker = Trader(moment, strat=MarketMakerBot, order_strat=MarketMaker)
    market_makers = [] # 1 market maker for each stock

    # init the market makers
    for i in range(10):
        maker = Trader(moment, strat=MarketMakerBot, order_strat=MarketMaker)
        maker.shares[stocks[i]] = {"quant": 50*factor}
        market_makers.append(maker)

    # market_maker.shares = 50*factor # give the market maker some inventory
    # print("STARTING PRICE", stock.price)
    # x = []
    # y = []
    # stocks[0].mean_reversion = 50.0

    # simulation loop
    while TIME < 5000:
        # x.append(TIME)
        print(TIME)
        for trader in traders:
            trader.step(stocks)
        # market_maker.match
        for i, maker in enumerate(market_makers):
            maker.step(stocks[i])


        
        # market_maker.step(stocks)
        print("\n --- Matching ---\n\n")

        # TODO market maker step
        for stock in stocks:
            if (TIME+1) % 100 == 0:
                # stock.mean_reversion = 0.0
                stock.mean_reversion += random.uniform(-10.0, 10.0)

            stock.match()
            stock.history.append(stock.price)

        TIME += 1

        # if TIME % 100 == 0:
        #     stock.mean_reversion += amount
        # if TIME % 1000 == 0: amount *= -1

        # send to all connected clients
        for websocket in connected_clients.copy():
            await send_order_book(websocket, stocks)
        await asyncio.sleep(0.1)#0.1)  # Control simulation speed
        # y.append(stock.price)
    # print("ENDING PRICE", stock.price)

    # import matplotlib.pyplot as plt
    # # Create the line chart
    # plt.plot(x, y)

    # # Add labels and title
    # plt.xlabel("X-axis")
    # plt.ylabel("Y-axis")
    # plt.title("Simple Line Chart")

    # # Show the chart
    # plt.show()




# simulation loop
# def main():

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(simulation())

if __name__ == "__main__":
    uvicorn.run("order:app", host="0.0.0.0", port=8000, reload=False)


# main()
