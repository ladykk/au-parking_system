from time import sleep
from state import State
from transaction import Transaction
from line import callStaff
from config import EXIT_SOURCE


class ExitState(State):

    def __init__(self, dev=False):
        super().__init__('exit', init_state='idle',
                         source="0" if dev else EXIT_SOURCE)
        self.alpr.start()

    # [S0]: Idle
    def _init_idle(self):  # > Entry
        # Clear keys on ALPR.
        self.alpr.clear()
        # Close barricade on Controller.
        self.controller.close_barricade()
        # Clear state info.
        self.info.clear()

    def _idle(self):  # > Logic
        # > Next state
        # 1.ALPR detected -> [S1:Detect]
        if self.alpr.is_detect():
            self.next_state = "detect"
            return

    def _c_set_idle(self):  # > Command
        self.next_state = "idle"

    # [S1]: Detect
    def _init_detect(self):  # > Entry
        # Create checked_license_numbers.
        self.info.update({"checked_license_numbers": list()})

    def _detect(self):  # > Logic
        # Check for license_number in transaction.
        f_tid = None
        f_license_number = None
        for license_number in self.alpr.keys():
            # Continue if already checked.
            if license_number in self.info.get("checked_license_numbers"):
                continue
            # Check is license_number exit.
            is_exists, tid = Transaction.is_license_number_exists(
                license_number)
            if is_exists is True:  # Break if license_number exists.
                f_tid = tid
                f_license_number = license_number
                break
            else:  # Append to checked_license_numbers if not found.
                self.info["checked_license_numbers"].append(license_number)

        # > Next state
        # 1.Found tid -> [S2:Get]
        if f_tid is not None:
            self.next_state = "get"
            self.info = {"tid": f_tid, "license_number": f_license_number}
            return
        # 2.Hand hovered on Controller -> [S0:Idle]
        if self.controller.k_hover is True:
            self.next_state = "idle"
            return
        # 3.If not found all afer (30 seconds) -> [S5:Failed]
        if len(self.alpr.keys()) == len(self.info.get("checked_license_numbers", [])) and self.seconds_from_now(30):
            self.info = {"reason": "Not found license_number in the system."}
            self.next_state = "failed"
            return

    # [S2]: Get transaction
    def _init_get(self):  # > Entry
        # Get transaction
        transaction = Transaction.get(self.info.get("tid"))

        # > Next state
        # 1.No tid -> [S5: Failed]
        if self.info.get("tid", None) is None:
            self.info = {"reason": "No transaction id."}
            self.next_state = "failed"
            return
        # 2.No transaction -> [S5:Failed]
        if transaction is None:
            self.info = {"reason": "Transaction not exists in the system."}
            self.next_state = "failed"
            return
        # 3.Transaction paid -> [S3: Success]
        if transaction.is_paid() is True:
            self.next_state = "success"
            return
        # 4.Transaction paid -> [S4: Payment]
        else:
            self.next_state = "payment"
            return

    def _c_set_get(self, input: str):  # > Command
        args = input.split(",")
        if len(args) == 2:
            self.info = {"tid": args[0], "license_number": args[1]}
            self.next_state = "get"

    # [S3]: Success
    def _init_success(self):  # > Entry
        # Get transaction
        transaction = Transaction.get(self.info.get("tid"))
        if transaction is None:  # No transaction -> [S5:Failed]
            self.info = {"reason": "Transaction not exists in the system."}
            self.next_state = "failed"
            return
        # Close transaction.
        transaction.closed()
        # Open barricade.
        self.controller.open_barricade()
        # Create is_car_pass.
        self.info.update({"is_car_pass": False})

    def _success(self):  # > Logic
      # Update is_car_pass when detected car at first time.
        if self.controller.p_has_car is True and self.info.get("is_car_pass") is False:
            self.info.update({"is_car_pass": True})

        # > Next state
        # 1. Car has pass and not detected car.
        if self.info.get("is_car_pass") is True and self.controller.p_has_car is False and self.seconds_from_now(5):
            self.next_state = "idle"
            return

    def _end_success(self):  # > End
        # wait 5 more seconds.
        sleep(5)

    # [S4]: Payment
    def _init_payment(self):  # > Init
        # Initialize call staff.
        self.info.update({"call_staff": False})

    def _payment(self):  # > Logic
        # Get transaction
        transaction = Transaction.get(self.info.get("tid"))

        # Hover to call staff.
        if self.controller.k_hover is True and self.info.get("call_staff") is False:
            callStaff("out")
            self.info.update({"call_staff": True})

        # > Next state
        # 1.No tid -> [S5: Failed]
        if self.info.get("tid", None) is None:
            self.info = {"reason": "No transaction id."}
            self.next_state = "failed"
            return
        # 2.No transaction -> [S5:Failed]
        if transaction is None:
            self.info = {"reason": "Transaction not exists in the system."}
            self.next_state = "failed"
            return
        # 3.Transaction paid -> [S3: Success]
        if transaction.is_paid() is True:
            self.next_state = "success"
            return
        # 4.Transaction unpaid after 120 seconds -> [S4: Failed]
        if self.seconds_from_now(120):
            self.info = {"reason": "Payment timeout."}
            self.next_state = "failed"
            return
        # 5.Cancel payment. -> [S0: Idle]
        if self.controller.k_button is True:
            self.next_state = "idle"
            return

    # [S5]: Failed.
    def _init_failed(self):  # > Init
        # Initialize call staff.
        self.info.update({"call_staff": False})

    def _failed(self):  # > Logic
        # Hover to call staff.
        if self.controller.k_hover is True and self.info.get("call_staff") is False:
            callStaff("out")
            self.info.update({"call_staff": True})

        # > Next state
        # 1.After 15 seconds and not have previous issue -> [S0:Idle]
        if self.seconds_from_now(15):
            self.next_state = "idle"
            return
        # 2.Button pressed on Controller -> [S0:Idle]
        if self.controller.k_button is True:
            self.next_state = "idle"
            return


def main():
    exit = ExitState(dev=True)
    exit.start()


if __name__ == "__main__":
    main()
