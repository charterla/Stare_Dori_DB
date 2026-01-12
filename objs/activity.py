from utils.db_pg import Database

EVENT_TYPE = {
    "challenge": 0,
    "versus": 1,
    "live_try": 2,
    "mission_live": 3,
    "festival": 4,
    "medley": 5
}

EVENT_LINK = [
    "challenge", 
    "versus", 
    "livetry", 
    "mission", 
    "festival", 
    "medley"
]

SERVER_NAME = ["日服", "國際服", "繁中服", "簡中服"]
OBJECT_TYPE = ["操作用戶", "當前頻道"]

class EventInfo:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.id: int = data[0]
        self.server_id: int = data[1]
        self.name: str = data[2]
        self.type: str = EVENT_LINK[data[3]]
        self.start_at: int = data[4]
        self.end_at: int = data[5]

def getRecentEvent(database: Database, server_id: int) -> EventInfo:
    # Creating objects with data directly selected from database
    event_data: list = database.selectRecentEventDetail(server_id)
    return None if event_data == [] else EventInfo(event_data)

class MonthlyInfo:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.id: int = data[0]
        self.server_id: int = data[1]
        self.name: int = data[2]
        self.start_at: int = data[3]
        self.end_at: int = data[4]

def getRecentMonthly(database: Database, server_id: int) -> MonthlyInfo:
    # Creating objects with data directly selected from database
    monthly_data: list = database.selectRecentMonthlyDetail(server_id)
    return None if monthly_data == [] else MonthlyInfo(monthly_data)