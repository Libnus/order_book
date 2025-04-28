class Order:
    order_counter = 0  # class-level counter

    def __init__(self, price, quant):
        self.order_id = Order.order_counter
        Order.order_counter += 1  # Increment the global counter
        self.price = price
        self.quant = quant

    def __lt__(self, other):
        return self.price < other.price

import heapdict

h = heapdict.heapdict()

order_first = Order(100.01, 5)
order_update = Order(99.01, 5)
order_second = Order(111.01, 5)
h[order_first.order_id] = order_first
h[order_update.order_id] = order_update
h[order_second.order_id] = order_second


order_update.price = 111.0  # Now you actually modify it
h[order_update.order_id] = order_update

print(h.peekitem()[1].price)  # Should now print 111.0

order_second.price = 85.0

h[order_second.order_id] = order_second
print(h.peekitem()[1].price)  # Should now print 85.0
