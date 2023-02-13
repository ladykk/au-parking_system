from linenotipy import Line
from transaction import Transaction
from utils.logger import getLogger
from utils.datetimefunc import datetime_now

line = Line(token="vz3CSx5X2rqBaTecrRVgK3J9bunUFkP2jVfpmJRfswH")
logger = getLogger("LINENotify")


def callStaff(type: str):
    try:
        datetime, datetime_string = datetime_now()
        Transaction.get_image(type)
        image = "in.jpg" if type == "in" else "out.jpg"
        line.post(
            message=f'\nCALL STAFF AT\n[{"ENTRANCE" if type == "in" else "EXIT"}]\n({datetime_string})', imageFile=image)
        logger.info("Notification sent.")
    except Exception:
        logger.error(
            f'Cannot notify staff. [Type: {"Entrance" if type == "in" else "Exit"} | Timestamp: {datetime_string}]')
