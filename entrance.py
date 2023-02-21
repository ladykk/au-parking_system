from time import sleep
from state import State
from transaction import Transaction
from line import callStaff
from config import ENTRANCE_SOURCE


class EntranceState(State):

    def __init__(self, dev=False):
        super().__init__('entrance', init_state='idle',
                         source="1" if dev else ENTRANCE_SOURCE)
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

    # [S1]: Detect.
    def _detect(self):  # > Logic
        # > Next state
        # 1.Hand hovered on Controller -> [S2:Process]
        if self.controller.k_hover is True:
            self.info = {"license_number": self.alpr.candidate_key()}
            self.next_state = "process"
            return
        # 2.No action after 30 seconds -> [S0:Idle]
        if self.seconds_from_now(30):
            self.next_state = "idle"
            return
        # 3.Cancel detection -> [S0:Idle]
        if self.controller.k_button is True:
            self.next_state = "idle"
            return

    # [S2]: Process.
    def _init_process(self):  # > Entry
        # Get license number.
        license_number = self.info.get("license_number", None)
        # 1.No license number -> [S4:Failed]
        if license_number is None:
            self.info = {"reason": "No license number to add."}
            self.next_state = "failed"
            return
        # Add transaction.
        success, tid = Transaction.add(license_number)
        # 2.Transaction added -> [S3:Success]
        if success is True:
            self.info = {"tid": tid}
            self.next_state = "success"
            return
        # 3.Has previous transaction -> [S4:Failed]
        if tid is not None:
            self.info = {
                "reason": "Previous transaction has an issue.", "tid": tid}
            self.next_state = "failed"
            return
        # 4.No previous transaction -> [S4: Failed]
        else:
            self.info = {"reason": "Cannot add transaction."}
            self.next_state = "failed"
            return

    def _c_set_process(self, input: str):  # > Command
        if input is str:
            self.info = {"license_number": input}
            self.next_state = "process"

    # [S3]: Success.
    def _init_success(self):  # > Entry
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

    # [S4]: Failed.
    def _init_failed(self):
        # Initialize call staff.
        self.info.update({"call_staff": False})

    def _failed(self):  # > Logic
        tid = self.info.get("tid", None)
        transaction = Transaction.get(tid)

        # Hover to call staff.
        if self.controller.k_hover is True and self.info.get("call_staff") is False:
            callStaff("in")
            self.info.update({"call_staff": True})

        # > Next state
        # 1.Button pressed on Controller -> [S0:Idle]
        if self.controller.k_button is True:
            self.next_state = "idle"
            return
        # 2.After 15 seconds and not have previous issue -> [S0:Idle]
        if self.seconds_from_now(15) and tid is None:
            self.next_state = "idle"
            return
        # 3.After issue solve or timeout 120 seconds  -> [S0:Idle]
        if transaction.is_paid() is True or self.seconds_from_now(120):
            self.next_state = "idle"
            return


def main():
    entrance = EntranceState(dev=True)
    entrance.start()


if __name__ == "__main__":
    main()
