import logging

from clients.broker.broker_client import BrokerClient
from clients.database.database_client import DatabaseClient
from custom_types.market import OrderType


def run(
    logger: logging.Logger,
    db_client: DatabaseClient,
    system_orders_file_name: str,
    broker: BrokerClient,
):
    logger.info("Running place_system_orders.py...")

    logger.info("Listing parameters...")
    logger.info("DB Client:%s", db_client)
    logger.info("System Orders file_name:%s", system_orders_file_name)

    logger.info("Retrieving system orders...")
    system_orders = db_client.get_system_orders(file_name=system_orders_file_name)
    logger.info(
        "Retrieved system orders:\n\t\t%s",
        "\n\t\t".join(str(order) for order in system_orders),
    )

    logger.info("Placing system orders...")
    for order in system_orders:
        if order.order_type == OrderType.MKT:
            broker.place_market_order(
                ticker=order.ticker, quantity=order.quantity, action=order.action
            )

        elif order.order_type == OrderType.LMT:
            broker.place_limit_order(
                ticker=order.ticker,
                quantity=order.quantity,
                action=order.action,
                limit_price=order.limit_price,
            )

        elif order.order_type == OrderType.STP:
            broker.place_stop_order(
                ticker=order.ticker,
                quantity=order.quantity,
                action=order.action,
                stop_price=order.stop_price,
            )

        elif order.order_type == OrderType.STP_LMT:
            broker.place_stop_limit_order(
                ticker=order.ticker,
                quantity=order.quantity,
                action=order.action,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
            )

        else:
            logger.info("Unrecognized order type:\n%s", order)
    logger.info("Finished placing system orders")

    logger.info("Finished running place_system_orders.py!!!")
