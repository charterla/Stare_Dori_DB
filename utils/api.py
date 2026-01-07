import requests, json, asyncio, time, traceback
from datetime import datetime
from pathlib import Path
from environs import Env
from logging import Logger

from utils.db_pg import Database
from utils.logger import getLogger, logExceptionToFile
from objs.activity import EVENT_TYPE, EventInfo, getRecentEvent, MonthlyInfo, getRecentMonthly

PACKAGE_URL = [
    "https://itunes.apple.com/jp/lookup?bundleId=jp.co.craftegg.band",
    "https://itunes.apple.com/us/lookup?bundleId=com.bushiroad.en.bangdreamgbp",
    "https://itunes.apple.com/tw/lookup?bundleId=net.gamon.bdTW",
    "https://itunes.apple.com/cn/lookup?bundleId=com.bilibili.star"
]

class API:
    def __init__(self, server_id: int, env_file_path: Path, log_base_path: Path):
        self.logger: Logger = getLogger(f"{__name__}.{server_id}")
        self.log_file_path: Path = log_base_path / f"{__name__}.{server_id}.txt"
        self.server_id: int = server_id
        
        env = Env(); env.read_env(env_file_path)
        self.database: Database = Database(
            host = env.str("DB_HOST"), name = env.str("DB_NAME"), user = env.str("DB_USER"), 
            password = env.str("DB_PASSWORD"), port = env.int("DB_PORT"), logger = self.logger)
        
        try: 
            from utils.parser import Parser
            url_base = env.str("URL_BASE").split(",")[self.server_id]
            self.url_base = None if url_base == "-" else f"https://{url_base}/api/"
            uid = env.str("UID").split(",")[self.server_id]
            self.uid = None if uid == "-" else uid
            uuid = env.str("UUID").split(",")[self.server_id]
            self.uuid = None if uuid == "-" else uuid
            kiv = env.str("KIV").split(",")[self.server_id].split(":")
            self.parser = None if kiv == ["-"] else Parser(kiv[0], kiv[1])
        except: self.parser = None
        self.version = None; self.__updateGameVersion()
        if self.parser != None: self.unavailability: int = 0; self.__checkStatusOfGame()
        
        asyncio.run(self.__monitor())
    
    # %% Getting and Parsing data from http response
    def __updateGameVersion(self) -> None:
        try:
            response = requests.get(PACKAGE_URL[self.server_id], timeout = 4)
            self.version = json.loads(response.text)["results"][0]["version"]
        except: logExceptionToFile(self.log_file_path, 
                                   "Fail to update game version", 
                                   traceback.format_exc()); return
    
    def __getDataFromBestdori(self, url: str) -> dict:
        try: response = requests.get(url, timeout = 4)
        except: logExceptionToFile(self.log_file_path, "Fail to get response from Bestdori", 
                                   traceback.format_exc()); return None
        try: return json.loads(response.text)
        except: logExceptionToFile(self.log_file_path, "Fail to load response from Bestdori", 
                                   traceback.format_exc(), {"response": response}); return None
        
    def __getDataFromGame(self, url: str) -> list:
        headers = {
            "Content-Type": "application/octet-stream", "Accept": "application/octet-stream",
            "X-ClientVersion": self.version, "X-Signature": self.uuid}
        try: return self.parser.parse(requests.get(url, headers = headers, timeout = 4).content)
        except: 
            try: response = requests.get(url, headers = headers, timeout = 10)
            except: logExceptionToFile(self.log_file_path, "Fail to get response from Game", 
                                       traceback.format_exc()); return None
            try: return self.parser.parse(response.content)
            except: logExceptionToFile(self.log_file_path, "Fail to load response from Game", 
                                       traceback.format_exc(), {"response": response}); return None
    
    # %% Fetching and Storing data to database
    def __fetchRecentEvents(self) -> bool:
        try:
            if self.parser != None and self.unavailability < 3:
                recent_events: list = self.__getDataFromGame(self.url_base + "event")
                for event in recent_events:
                        if isinstance(event, list):
                            self.database.insertEventDetail(
                                self.server_id, event[0], event[2], EVENT_TYPE[event[1]], 
                                int(event[4] / 1000), int(event[5] / 1000))
                return True
        except: self.logger.warning("Fail to get recent events from Game")
        try: 
            recent_events: dict[str, dict[str, dict[str, list]]] \
                = self.__getDataFromBestdori("https://bestdori.com/api/news/dynamic/recent.json")
            for event_id, event in recent_events["events"].items():
                event = json.loads(requests.get(f"https://bestdori.com/api/events/{event_id}.json"
                                                , timeout = 2).text)
                if event["startAt"][self.server_id] != None:
                    self.database.insertEventDetail(
                        self.server_id, event_id, event["eventName"][self.server_id], EVENT_TYPE[event["eventType"]], 
                        int(int(event["startAt"][self.server_id]) / 1000), int(int(event["endAt"][self.server_id]) / 1000))
            return True
        except: self.logger.warning("Fail to get recent events from Bestdori")
        return False
        
    def __fetchEventTop(self, event: EventInfo) -> bool:
        try:
            if self.parser != None and self.unavailability < 3:
                fetch_time = int(datetime.now().timestamp())
                event_tops: list = self.__getDataFromGame(
                    self.url_base + f"user/{self.uid}/event/{event.id}/{event.type}/ranking")[0]
                self.database.insertEventPlayers(
                    self.server_id, event.id, [[event_top[6], event_top[0], event_top[3], event_top[2]] 
                                            for event_top in event_tops], event.start_at)
                self.database.insertDefaultEventRanks(
                    self.server_id, event.id, [event_top[6] for event_top in event_tops], event.start_at)
                self.database.insertEventPoints(
                    self.server_id, event.id, [[event_top[6], event_top[5], fetch_time] for event_top in event_tops])
                return True
        except: self.logger.warning(f"Fail to get top of event {event.id} from Game")
        try:
            event_tops: dict[str, list[dict[str]]] = self.__getDataFromBestdori(
                f"https://bestdori.com/api/eventtop/data?server={self.server_id}&event={event.id}&mid=0&interval=864000000")
            self.database.insertEventPlayers(
                self.server_id, event.id, [[event_top["uid"], event_top["name"], event_top["introduction"], 
                                            event_top["rank"]] for event_top in event_tops["users"]], event.start_at)
            self.database.insertDefaultEventRanks(
                self.server_id, event.id, [event_top["uid"] for event_top in event_tops["users"]], event.start_at)
            self.database.insertEventPoints(
                self.server_id, event.id, [[event_top["uid"], event_top["value"], int(event_top["time"] / 1000)] 
                                           for event_top in event_tops["points"]])
            return True
        except: self.logger.warning(f"Fail to get top of event {event.id} from Bestdori")
        return False
    
    def __fetchFullEventTop(self, event: EventInfo) -> bool:
        try:
            event_tops: dict[str, list[dict[str]]] = self.__getDataFromBestdori(
                f"https://bestdori.com/api/eventtop/data?server={self.server_id}&event={event.id}&mid=0&interval=60000")
            self.database.insertEventPlayers(
                self.server_id, event.id, [[event_top["uid"], event_top["name"], event_top["introduction"], 
                                            event_top["rank"]] for event_top in event_tops["users"]], event.start_at)
            self.database.insertDefaultEventRanks(
                self.server_id, event.id, [event_top["uid"] for event_top in event_tops["users"]], event.start_at)
            self.database.insertEventPoints(
                self.server_id, event.id, [[event_top["uid"], event_top["value"], int(event_top["time"] / 1000)] 
                                           for event_top in event_tops["points"]])
            return True
        except: self.logger.warning(f"Fail to get full top of event {event.id} from Bestdori")
        return False
    
    def __fetchRecentMonthlys(self) -> bool:
        try:
            if self.parser != None and self.unavailability < 3:
                recent_monthlys: list = self.__getDataFromGame(self.url_base + "monthlyranking")
                for monthly in recent_monthlys:
                    if isinstance(monthly, list):
                        self.database.insertMonthlyDetail(
                            self.server_id, monthly[0], monthly[1], int(monthly[5] / 1000), int(monthly[6] / 1000))
                return True
        except: self.logger.warning("Fail to get recent monthlys from Game")
        return False
        
    def __fetchMonthlyTop(self, monthly: MonthlyInfo) -> bool:
        try:
            if self.parser != None and self.unavailability < 3:
                fetch_time = int(datetime.now().timestamp())
                monthly_tops: list = self.__getDataFromGame(
                    self.url_base + f"user/{self.uid}/monthlyranking/{monthly.id}/ranking")[0]
                self.database.insertMonthlyPlayers(
                    self.server_id, monthly.id, [[monthly_top[6], monthly_top[0], monthly_top[3], monthly_top[2]] 
                                            for monthly_top in monthly_tops], monthly.start_at)
                self.database.insertMonthlyPoints(
                    self.server_id, monthly.id, [[monthly_top[6], monthly_top[5], fetch_time] 
                                                for monthly_top in monthly_tops])
                return True
        except: self.logger.warning(f"Fail to get top of monthly {monthly.id} from Game")
        return False
    
    # %% Monitoring data regularly
    def __checkStatusOfGame(self) -> None: 
        headers = {"Content-Type": "application/octet-stream", "Accept": "application/octet-stream",
                   "X-ClientVersion": self.version}
        try:
            try: status = self.parser.parse(requests.get(self.url_base + "application", 
                                                         headers = headers, timeout = 4).content)
            except: 
                self.__updateGameVersion(); headers["X-ClientVersion"] = self.version
                status = self.parser.parse(requests.get(self.url_base + "application", 
                                                        headers = headers, timeout = 4).content)
            if status[2] == "available":
                if self.unavailability > 3:
                    self.logger.error(f"Connection to game was down for {self.unavailability} min(s)")
                self.unavailability = 0
            else:
                if self.unavailability == 3: self.logger.error("Connection to game is down")
                self.unavailability += 1
        except: 
            if self.unavailability == 3: self.logger.error("Connection to game is down")
            self.unavailability += 1
        return
    
    async def __monitor(self) -> None:
        flag = False; s_time = time.time()
        while True:
            self.__fetchRecentEvents(); recent_event = getRecentEvent(self.database, self.server_id)
            if self.server_id != 1: 
                self.__fetchRecentMonthlys(); recent_monthly = getRecentMonthly(self.database, self.server_id)
            
            for _ in range(60):
                if flag == False: flag = self.__fetchFullEventTop(recent_event)
                else: flag = self.__fetchEventTop(recent_event)
                if self.server_id != 1 and recent_monthly != None: self.__fetchMonthlyTop(recent_monthly)
                
                await asyncio.sleep(max(0, 60 - time.time() + s_time)); s_time = time.time()
                if self.parser != None: self.__checkStatusOfGame()