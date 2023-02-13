from entrance import EntranceState
from exit import ExitState
from config import DEV

def main():
    try:
        entrance = EntranceState(dev=DEV)
        entrance.start()
        exit = ExitState(dev=DEV)
        exit.start()
        while entrance.is_running() and exit.is_running():
            pass
    except Exception:
        entrance.stop()
        exit.stop()


if __name__ == '__main__':
    main()
