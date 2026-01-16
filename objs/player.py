import math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import Optional

from utils.db_pg import Database
from objs.activity import EventInfo, MonthlyInfo

class EventPlayer:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.server_id: int = data[0]
        self.event_id: int = data[1]
        self.uid: int = data[2]
        
        self.name: str = data[3].replace("\n", "") if data[3] != None else ""
        self.introduction: str = data[4].replace("\n", "") if data[4] != None else ""
        self.rank: int = data[5]
        
        self.last_update_time: int = data[6]
        self.recent_up_time: int = data[7]
        self.point: int = data[8]
        self.point_rank: int = data[9]
        self.speed: int = data[10]
        self.speed_rank: int = data[11]
        return
    
def getEventTopPlayers(database: Database, server_id: int, event: EventInfo, request_time: int) -> list[EventPlayer]:
    # Collecting data of current top 10 player
    players_data: list[list] = database.selectEventTopPlayers(server_id, event.id)
    players_data = [player_data[:-2] + [player_data[-1], 
            database.selectEventPlayerUpsTime(server_id, event.id, player_data[2], 1)[0], player_data[-2]] 
        for player_data in players_data]
    players_data = [player_data + [i + 1, -1 if ((request_time - player_data[-2]) <= 3600) else
            (player_data[8] - database.selectEventPlayerPointsAtTime(server_id, event.id, player_data[2], 
                                                                     before = request_time - 3600, limit = 1)[0][0])] 
        for i, player_data in enumerate(players_data)]
    
    # Counting speed rank of current top 10 player
    to_speed_rank: list[tuple[int, int]] = [(player_data[-2] - 1, player_data[-1]) for player_data in players_data]
    to_speed_rank = sorted(to_speed_rank, key = lambda x: x[1], reverse = True)
    players_data[to_speed_rank[0][0]].append(1)
    for last_to, now_to in zip(to_speed_rank[:-1], to_speed_rank[1:]):
        if last_to[1] == now_to[1]: players_data[now_to[0]].append(players_data[last_to[0]][-1])
        else: players_data[now_to[0]].append(players_data[last_to[0]][-1] + 1)
        
    # Creating objects from data
    return [EventPlayer(player_data) for player_data in players_data]

class EventPlayerDetail(EventPlayer):
    def __init__(self, player: EventPlayer, data: list):
        # Initializing object from base object
        super().__init__(list(player.__dict__.values()))
        
        # Initializing object with data provided
        self.point_up_delta: int = data[0]
        self.point_down_delta: int = data[1]
        self.point_change_times: int = data[2]
        
        self.recent_point_changes: list[tuple[int, int]] = data[3]
        self.recent_ranges_detail: list[tuple[int, int, int, int]] = data[4]
        
def getEventTopPlayerDetail(database: Database, server_id: int, event: EventInfo, 
                            request_time: int, point_rank: int) -> EventPlayerDetail:
    # Collecting top players info
    players: list[EventPlayer] = getEventTopPlayers(database, server_id, event, request_time); point_rank -= 1
    player: EventPlayer = players[point_rank]
    
    # Collecting player detail from database
    player_detail_data: list = []
    player_detail_data.append(0 if point_rank == 0 else (players[point_rank - 1].point - player.point))
    player_detail_data.append(0 if point_rank == 9 else (player.point - players[point_rank + 1].point))
    player_detail_data.append(database.selectEventPlayerPointsNumAtTime(server_id, event.id, player.uid) - 1)
    
    # Counting recent point changes
    player_ups_time: list[int] = database.selectEventPlayerUpsTime(server_id, event.id, player.uid)
    to_recent_point_changes: list[list[int]] = database.selectEventPlayerPointsAtTime(
        server_id, event.id, player.uid, after = player.recent_up_time, 
        limit = 21 + len(player_ups_time), with_time = True)
    player_detail_data.append([])
    for now_to, last_to in zip(to_recent_point_changes[:-1], to_recent_point_changes[1:]):
        if now_to[0] in player_ups_time: continue
        player_detail_data[-1].append((now_to[0], now_to[1] - last_to[1]))
    player_detail_data[-1] = player_detail_data[-1][:min(20, len(player_detail_data[-1]))]
        
    # Counting recent ranges detail
    player_detail_data.append([])
    for time in [3600, 7200, 43200, 86400]:
        after_time = request_time - time
        if after_time <= event.start_at and after_time <= player.recent_up_time: break
        point_changes = database.selectEventPlayerPointsNumAtTime(
            server_id, event.id, player.uid, after = after_time) - 1
        point_before = database.selectEventPlayerPointsAtTime(
            server_id, event.id, player.uid, before = after_time, limit = 1)[0][0]
        if point_changes <= 0: player_detail_data[-1].append((after_time, 0, 0, 0))
        else: player_detail_data[-1].append((after_time, point_changes, round(time / point_changes), 
                                             round((player.point - point_before) / point_changes)))
    
    # Creating objects from data
    return EventPlayerDetail(player, player_detail_data)

class EventPlayerDaily(EventPlayer):
    def __init__(self, player: EventPlayer, data: list):
        # Initializing object from base object
        super().__init__(list(player.__dict__.values()))
        
        # Initializing object with data provided
        self.point_delta: list[int] = data[0]
        self.point_change_times: list[int] = data[1]
        self.point_change_times_hourly: list[list[int]] = data[2]
        self.stop_total: list[int] = data[3]
        self.stop_intervals: list[list[tuple[tuple[int, int], int]]] = data[4]
        self.rank_changes: list[list[tuple[int, tuple[int, int]]]] = data[5]
        
def getEventTopPlayerDaily(database: Database, server_id: int, event: EventInfo, 
                           request_time: int, timezone: ZoneInfo, point_rank: int) \
    -> tuple[EventPlayerDaily, list[int]]:
    # Collecting top players info and Counting time splits day by day
    player: EventPlayer = getEventTopPlayers(database, server_id, event, request_time)[point_rank - 1]
    day_split: list[int] = [event.start_at]
    last_day_split_datetime: datetime \
        = datetime.fromtimestamp(day_split[-1], tz = timezone).replace(hour = 0, minute = 0, second = 0, microsecond = 0)
    while True:
        last_day_split_datetime += timedelta(days = 1); day_split.append(int(last_day_split_datetime.timestamp()))
        if day_split[-1] > min(request_time, event.end_at): day_split[-1] = min(request_time, event.end_at); break
    player_daily_data: list = []
    
    # Collecting and Processing point data from database
    to_point_delta: list[int] \
        = [database.selectEventPlayerPointsAtTime(server_id, event.id, player.uid, before = split, limit = 1)[0][0]
           for split in day_split]
    player_daily_data.append([now_point - last_point for now_point, last_point 
                              in zip(to_point_delta[1:], to_point_delta[:-1])])
    to_point_change_times: list[int] = database.selectEventPlayerPointsNumHourly(
        server_id, event.id, player.uid, event.start_at, 
        int((min(request_time, event.end_at) - event.start_at) // 3600) + 1); player_daily_data += [[], []]
    for now_split, last_split in zip(day_split[1:], day_split[:-1]):
        num = min(int(math.ceil((now_split - last_split) / 3600)), len(to_point_change_times))
        player_daily_data[-2].append(sum(to_point_change_times[:num]))
        player_daily_data[-1].append(to_point_change_times[:num])
        if len(to_point_change_times) > num: to_point_change_times = to_point_change_times[num:]
        
    # Collecting and Processing stop data from database
    to_stop: list[list[int]] = database.selectEventPlayerIntervals(server_id, event.id, player.uid)
    if request_time - player.last_update_time >= 1200: to_stop.append([player.last_update_time, request_time, 0])
    player_daily_data += [[0 for _ in range(len(day_split) - 1)], [[] for _ in range(len(day_split) - 1)]]; index = 0
    for to in to_stop:
        while True:
            while to[0] > day_split[index + 1]: index += 1
            sub_to: tuple[int, int] = (max(to[0], day_split[index]), min(to[1], day_split[index + 1]))
            player_daily_data[-2][index] += sub_to[1] - sub_to[0]
            player_daily_data[-1][index].append((sub_to, sub_to[1] - sub_to[0]))
            if to[1] > day_split[index + 1]: index += 1
            else: break
            
    # Collecting and Processing rank changes data from database
    to_rank_changes: list[list[int]] = database.selectEventPlayerRanks(server_id, event.id, player.uid)
    player_daily_data += [[[] for _ in range(len(day_split) - 1)]]; index = 0
    for to in to_rank_changes:
        while to[0] > day_split[index + 1]: index += 1
        if (to[1] < 1 or to[1] > 11) and (to[2] < 1 or to[2] > 11): continue
        player_daily_data[-1][index].append((to[0], ((-1 if (to[1] < 1 or to[1] > 10) else to[1]), 
                                                     (-1 if (to[2] < 1 or to[2] > 10) else to[2]))))
        
    # Creating objects from data
    return EventPlayerDaily(player, player_daily_data), day_split

class MonthlyPlayer:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.server_id: int = data[0]
        self.event_id: int = data[1]
        self.uid: int = data[2]
        
        self.name: str = data[3] if data[3] != None else ""
        self.introduction: str = data[4] if data[4] != None else ""
        self.rank: int = data[5]
        
        self.point: int = data[6]
        self.point_rank: int = data[7]
        return
    
def getMonthlyTopPlayers(database: Database, server_id: int, monthly: MonthlyInfo) -> list[MonthlyPlayer]:
    # Check if monthly exists
    if monthly == None: return []
    
    # Collecting data of current top 10 player
    players_data: list[list] = database.selectMonthlyTopPlayers(server_id, monthly.id)
    players_data = [player_data[:-1] + [i + 1] for i, player_data in enumerate(players_data)]
        
    # Creating objects from data
    return [MonthlyPlayer(player_data) for player_data in players_data]