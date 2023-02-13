# DVR
DVR_USERNAME = "admin"
DVR_PASSWORD = "a1234567"
DVR_IP_ADDR = "10.0.0.100"

# Global
DEV = False

# Transaction
ENTRANCE_CHANNEL = 101
EXIT_CHANNEL = 201


def getRTSP(channel: int):
    return f"rtsp://{DVR_USERNAME}:{DVR_PASSWORD}@{DVR_IP_ADDR}:554/Streaming/Channels/{str(channel)}/"


# ALPR
MODEL_NAME = "tha-license-plate-detection.pt"
ENTRANCE_SOURCE = getRTSP(ENTRANCE_CHANNEL)
EXIT_SOURCE = getRTSP(EXIT_CHANNEL)

# Controller
HOVER_CMS = 5
CAR_CMS = 150
