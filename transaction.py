from datetime import datetime, timedelta
from firebase import Db, Storage
from utils.datetimefunc import datetime_to_upload_string
from utils.logger import getLogger
from hikvisionapi import Client as HikvisionClient
from config import DVR_IP_ADDR, DVR_PASSWORD, DVR_USERNAME, ENTRANCE_CHANNEL, EXIT_CHANNEL, DEV


class Transaction(object):

    list = dict()
    ref = Db.collection("transactions")
    _logger = getLogger('Transaction')
    _dvr = None if DEV else HikvisionClient(f'http://{DVR_IP_ADDR}', DVR_USERNAME, DVR_PASSWORD)

    def __init__(
        self,
        tid: str,
        license_number: str,
        timestamp_in: datetime,
        fee: float, status: str,
        paid: float,
        timestamp_out: datetime = None
    ):
        self.tid = tid
        self.license_number = license_number
        self.timestamp_in = timestamp_in
        self.fee = fee
        self.status = status
        self.paid = paid
        self.timestamp_out = timestamp_out

    @staticmethod
    def from_dict(data: dict) -> 'Transaction':
        return Transaction(
            data.get("tid", ""),
            data.get("license_number"),
            data.get("timestamp_in"),
            data.get("fee", 0),
            data.get("status", ""),
            data.get("paid", 0),
            data.get("timestamp_out", None)
        )

    @staticmethod
    def on_transactions_snapshot(collection, changes, read_time):
        for change in changes:
            if change.type.name == "ADDED":
                Transaction.list.update(
                    {change.document.id: Transaction.from_dict(change.document.to_dict())})
            elif change.type.name == "MODIFIED":
                transaction = Transaction.list.get(change.document.id, None)
                if transaction is None:
                    Transaction.list.update(
                        {change.document.id: Transaction.from_dict(change.document.to_dict())})
                else:
                    transaction.update(change.document.to_dict())
            elif change.type.name == "REMOVED":
                Transaction.list.pop(change.document.id, None)

    @staticmethod
    def is_license_number_exists(license_number: str):
        for tid, transaction in Transaction.list.items():
            if transaction.license_number == license_number:
                if transaction.is_out() is False:
                    Transaction._logger.info(
                        f"License number: {license_number} [EXISTS] | TID: {tid}")
                    return True, tid
        Transaction._logger.info(
            f"License number: {license_number} [NOT EXISTS]")
        return False, None

    @staticmethod
    def is_license_number_unpaid(license_number: str):
        for tid, transaction in Transaction.list.items():
            if transaction.license_number == license_number:
                if transaction.is_paid() is False and transaction.is_out() is True:
                    Transaction._logger.info(
                        f"License number: {license_number} [UNPAID] | TID: {tid}")
                    return True, tid
        Transaction._logger.info(
            f"License number: {license_number} [NO UNPAID]")
        return False, None

    @staticmethod
    def get_image(type: str):
        if DEV:
            raise
        response = Transaction._dvr.Streaming.channels[ENTRANCE_CHANNEL if type == "in" else EXIT_CHANNEL].picture(
            method='get', type='opaque_data')
        with open(f'{type}.jpg', 'wb') as f:
            # Save image.
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

    @staticmethod
    def _upload_image(license_number: str, timestamp: datetime, type: str):
        try:
            # Get image.
            Transaction.get_image(str)
            # Upload image.
            ref = Storage.blob(
                f'transactions/{timestamp.strftime("%Y-%m-%d")}/{type}/{datetime_to_upload_string(timestamp)}_{license_number}.jpg')
            ref.upload_from_filename(f'{type}.jpg')
            ref.make_public()
            return ref.public_url
        except Exception:
            Transaction._logger.error(
                f'Cannot upload {"Entrance" if type == "in" else "Exit"} image.')
            return None

    @staticmethod
    def add(license_number: str):
        # Check if license_number exists.
        is_exists, tid = Transaction.is_license_number_exists(license_number)
        if is_exists is True:
            Transaction._logger.error(
                f'Cannot add transaction "{license_number}". (Reason: License number is existing in the system.)')
            return False, tid
        # Check if license_number is unpaid.
        is_unpaid, tid = Transaction.is_license_number_unpaid(license_number)
        if is_unpaid is True:
            Transaction._logger.error(
                f'Cannot add transaction "{license_number}". (Reason: License number has an unpaid transaction.)')
            return False, tid
        # Format info.
        info = {"license_number": license_number,
                "timestamp_in": datetime.now()}
        # Upload image.
        image = Transaction._upload_image(
            license_number, info.get("timestamp_in"), "in")
        if image is not None:
            info.update({"image_in": image})
        # Add transaction.
        update_time, ref = Transaction.ref.add(info)
        Transaction._logger.info(
            f'Transaction added. [License number: {license_number} | TID: {ref.id}]')
        return True, ref.id

    @staticmethod
    def get(tid: str):
        return Transaction.list.get(tid, None)

    def update(self, data: dict):
        self.tid = data.get("tid", self.tid)
        self.license_number = data.get("license_number", self.license_number)
        self.timestamp_in = data.get("timestamp_in", self.timestamp_in)
        self.fee = data.get("fee", self.fee)
        self.status = data.get("status", self.status)
        self.paid = data.get("paid", self.paid)
        self.timestamp_out = data.get("timestamp_out", self.timestamp_out)

    def is_paid(self):
        return self.status == "Paid"

    def is_out(self):
        return self.timestamp_out is not None

    def closed(self):
        # Format info.
        info = {"timestamp_out": datetime.now(), "is_edit": True}
        # Upload image.
        image = Transaction._upload_image(
            self.license_number, info.get("timestamp_out"), "out")
        if image is not None:
            info.update({"image_out": image})
        # Close transaction.
        update_time = Db.collection(
            "transactions").document(self.tid).update(info)
        Transaction._logger.info(f"Transaction closed. [TID: {self.tid}]")


Transaction.ref.where("timestamp_in", ">=", datetime.now(
) - timedelta(weeks=4)).on_snapshot(Transaction.on_transactions_snapshot)
