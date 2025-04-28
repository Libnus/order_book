# Order Book Simulator

My simple order book simulator. I've implemeneted two types of bots: market maker bot and mean reversion bot. The market maker is simply there to ensure a liquid market and the mean reversion bot attempts to buy and sell based on what it thinks the value of the stock is (i.e. mean reverting). 


### Limit Order Strategy
The mean reversion bot uses an undercut algorithm which simply involves placing a bid or ask, and walking the valu eup or down depending on how the order is filling. Orders that aren't filling are adjusted or cancelled if they spend too much time unfilled. 

### Order Book Implementation
The order book uses a heapdict from python to maintain priority based on price and time. Orders on the market longer have higher priority.

#### Matching Orders
The matching process simply involves taking the min of both heaps and matching them until we can no longer find a proper bid/ask pair. 

##### Buy Orders
When a buy order is placed, take the cash asa reserves and attempt to fill. We return cash that was not used (i.e. we got a better deal). This ensures bots don't buy with money that doesn't exist and ensures the order book runs smoothly and fills orders without messing with cash calculations. 

#### Sell Orders
Similarly, we take the shares and only return them if the order is cancelled. This ensures bots don't sell what they don't have and we can qucikly transfer the shares when we match orders.

### Example
An example run is shown in the video. Note that the price is being determined completely by the bots and orders being filled. For demonstration purposes the "mean reversion value" of the stock is varied from time to time to create new trading environments in a short period. 

https://github.com/user-attachments/assets/30ab8feb-db7a-47d6-abe8-1c079b59e2b1


