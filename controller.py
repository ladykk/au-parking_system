from threading import Event, Thread
import time
from serial import Serial
from utils.logger import getLogger
from firebase import TempDb
from firebase_admin.db import Event as dbEvent
from deepdiff import DeepDiff
from datetime import datetime
from utils.datetimefunc import datetime_now, seconds_from_now
from config import HOVER_CMS, CAR_CMS
import argparse


class ControllerClient:

    def __init__(
        self,
        name: str,  # node name.
        port: str,  # serial port number
        hover_cms: int = HOVER_CMS,  # centimeters to detect hover.
        car_cms: int = CAR_CMS,  # centimeters to detect car.
        baud_rate: int = 9600,  # baud_rate
    ):
        # > Local variables
        self.name = name
        self._logger = getLogger(name.title())

        # > Arduino configuration
        if port is not None:
            self._arduino = Serial(port, baud_rate)
            self._arduino.close()
        self._hover_cms = hover_cms
        self._car_cms = car_cms

        # > Controller variables
        self.mode = False
        self.b_open = False
        self.b_close = False
        self.k_sensor = 0
        self.k_button = False
        self.p_sensor = 0
        self.p_barricade = False

        # > Database
        self._connected_timestamp = datetime.now()
        self._status = {}
        self._config = {}
        self._command = ''
        self._db_ref = TempDb.reference(f'{self.name}/controller')
        # listen on status.
        self._db_ref.child('status').listen(self._db_status_callback)
        # listen on config.
        self._db_ref.child('config').listen(self._db_config_callback)
        # listen on command.
        self._db_ref.child('command').listen(self._db_command_callback)

        # > Thread
        self._thread = Thread(target=self._process, daemon=True)
        self._stop_event = Event()

        self._logger.info(
            f"{self.name.title()} Controller Client initialized.")

    # > Get functions
    def k_hover(self): return self.k_sensor <= self._hover_cms
    def p_has_car(self): return self.p_sensor <= self._car_cms

    # > Database functions
    def _format_db_status(self): return {
        "mode": self.mode,
        "b_open": self.b_open,
        "b_close": self.b_close,
        "k_hover": self.k_hover(),
        "k_button": self.k_button,
        "p_has_car": self.p_has_car(),
        "p_barricade": self.p_barricade
    }

    def _format_db_config(self): return {
        "hover_cms": self._hover_cms,
        "car_cms": self._car_cms
    }

    def _is_status_difference(self):
        return len(DeepDiff(self._format_db_status(), self._status)) != 0

    def _is_config_difference(self):
        return len(DeepDiff(self._format_db_config(), self._config)) != 0

    def _db_status_callback(self, event: dbEvent):
        self._status = event.data

    def _db_config_callback(self, event: dbEvent):
        self._config = event.data

    def _db_command_callback(self, event: dbEvent):
        self._command = event.data if event.data else ''

    # > Thread functions
    def start(self):
        self._logger.info(
            f"{self.name.title()} Controller Client is starting.")
        if self._thread.is_alive():
            return self._logger.warning('Update thread is already running.')
        self._stop_event.clear()
        self._thread.start()

    def stop(self):
        self._logger.info(
            f"{self.name.title()} Controller Client is stopping.")
        self._stop_event.set()

    # > Thread logic functions
    def _process(self):
        self._logger.info(
            f"{self.name.title()} Controller Client has started.")
        self._logger.info("Open serial communication.")
        self._arduino.open()  # open serial communication.
        time.sleep(5)  # wait for serial communication to open.

        # initialize value in the database.
        self._db_ref.child('status').set(self._format_db_status())
        self._db_ref.child('config').set(self._format_db_config())
        self._db_ref.child('command').set(self._command)
        new_datetime, new_datetime_string = datetime_now()
        self._connected_timestamp = new_datetime
        self._db_ref.child("connected_timestamp").set(new_datetime_string)
        self._logger.info(
            "Initialize controller's infos to Realtime Database.")

        while not self._stop_event.is_set():
            while self._arduino.in_waiting:
                self._update()
                self._command_exec()
        self._logger.info(
            f"{self.name.title()} Controller Client has stopped.")

    def _update(self):
        try:
            data = self._arduino.readline().decode('ascii')
            input = data.strip('\n\r').split(':')
            if(input[0] != "Values"):
                return  # skipping if not values.
            variables = input[1].split(',')  # convert into array and assign.
            self.mode = True if variables[0] == '1' else False
            self.b_open = True if variables[1] == '1' else False
            self.b_close = True if variables[2] == '1' else False
            self.k_button = True if variables[3] == '1' else False
            self.p_barricade = True if variables[4] == '1' else False
            self.k_sensor = int(variables[5])
            self.p_sensor = int(variables[6])
        except UnicodeDecodeError:
            self._logger.warning('Cannot read input for this line.')
        except IndexError:
            self._logger.warning(
                'Cannot extract value from input for this line.')
        except:
            self._logger.warning('Some error occured.')

        if self._is_status_difference():
            self._logger.debug("Update status's infos to Realtime Database.")
            self._db_ref.child('status').set(self._format_db_status())

        if self._is_config_difference():
            self._logger.debug("Update config's infos to Realtime Database.")
            self._db_ref.child('config').set(self._format_db_config())

        if seconds_from_now(self._connected_timestamp, 5):
            new_datetime, new_datetime_string = datetime_now()
            self._connected_timestamp = new_datetime
            self._db_ref.child("connected_timestamp").set(new_datetime_string)

    def _command_exec(self):
        if self._command != '':
            self._logger.info(f'Received command: {self._command}')
            input = self._command.split(':')
            if hasattr(self, f'_c_{input[0]}'):
                if len(input) == 2:
                    self._logger.info(
                        f'Command Executed. [_c_{input[0]}({input[1]})]')
                    getattr(self, f'_c_{input[0]}')(input[1])
                elif len(input) == 1:
                    self._logger.info(f'Command Executed. [_c_{input[0]}()]')
                    getattr(self, f'_c_{input[0]}')()
            self._db_ref.child('command').set('')

    # > Command functions
    def _c_set_hover_cms(self, input: str):
        self._hover_cms = int(input)
        self._logger.info(f"Set hover cms to: {input}")

    def _c_set_car_cms(self, input: str):
        self._car_cms = int(input)
        self._logger.info(f"Set car cms to: {input}")

    def _c_open_barricade(self):
        self._arduino.write(b'open barricade.\n')
        self._logger.info("Barricade opened.")

    def _c_close_barricade(self):
        self._arduino.write(b'close barricade.\n')
        self._logger.info("Barricade closed.")


class ControllerServer:

    def __init__(
        self,
        name: str,
        hover_cms: int = HOVER_CMS,  # centimeters to detect hover.
        car_cms: int = CAR_CMS,  # centimeters to detect car.
    ):
        # > Local variables
        self.name = name
        self._logger = getLogger(name.title())

        # > Controller variable
        self.mode = False
        self.b_open = False
        self.b_close = False
        self.k_hover = False
        self.k_button = False
        self.p_has_car = False
        self.p_barricade = False

        # > Controller configuration
        self.hover_cms = hover_cms
        self.car_cms = car_cms

        # > Database
        self._command = None
        self._db_ref = TempDb.reference(f'{self.name}/controller')
        # listen on status.
        self._db_ref.child('status').listen(self._db_status_callback)
        # listen on config.
        self._db_ref.child('config').listen(self._db_config_callback)
        # listen on command.
        self._db_ref.child('command').listen(self._db_command_callback)

        self._logger.info(
            f"{self.name.title()} Server Controller initialized.")

    # > Database functions
    def _db_status_callback(self, event: dbEvent):
        if type(event.data) is dict:
            self.mode = event.data.get('mode', False)
            self.b_open = event.data.get('b_open', False)
            self.b_close = event.data.get('b_close', False)
            self.k_hover = event.data.get('k_hover', False)
            self.k_button = event.data.get('k_button', False)
            self.p_has_car = event.data.get('p_has_car', False)
            self.p_barricade = event.data.get('p_barricade', False)

    def _db_config_callback(self, event: dbEvent):
        if type(event.data) is dict:
            self.hover_cms = event.data.get('hover_cms', self.hover_cms)
            self.car_cms = event.data.get('car_cms', self.car_cms)

    def _db_command_callback(self, event: dbEvent):
        self._command = event.data if event.data else ''

    # > Command functions
    def set_hover_cms(self, cms: int):
        self._db_ref.child('command').set(f'set_hover_cms:{cms}')
        self._logger.info(f"Set hover cms: {cms}")

    def set_car_cms(self, cms: int):
        self._db_ref.child('command').set(f'set_car_cms:{cms}')
        self._logger.info(f"Set car cms: {cms}")

    def open_barricade(self):
        self._db_ref.child('command').set(f'open_barricade')
        self._logger.info(f"Open barricade.")

    def close_barricade(self):
        self._db_ref.child('command').set(f'close_barricade')
        self._logger.info(f"Close barricade.")


def parse_opt():
    parser = argparse.ArgumentParser()
    parser.add_argument('--entrance', action='store_true',
                        help="Connect the controller to the entrance node.")
    parser.add_argument('--exit', action='store_true',
                        help="Connect the controller to the exit node.")
    parser.add_argument('--port', type=str, default='',
                        help="Controller's serial port.")
    return parser.parse_args()


def main(opt):
    # Check for arguments
    if opt.port == '' or (not opt.entrance and not opt.exit):
        print("Invalid arguments.")
        return

    # > Create contrller client.
    controller = ControllerClient(
        'entrance' if opt.entrance else 'exit' if opt.exit else '', opt.port)
    controller.start()


if __name__ == '__main__':
    opt = parse_opt()
    main(opt)
