from datetime import datetime, timedelta

from utils.db_pg import Database
from objs.activity import EventInfo, MonthlyInfo

class EventPlayer:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.server_id: int = data[0]
        self.event_id: int = data[1]
        self.uid: int = data[2]
        
        self.name: str = data[3]
        self.introduction: str = data[4]
        self.rank: int = data[5]
        
        self.last_update_time: int = data[6]
        self.recent_up_time: int = data[7]
        self.point: int = data[8]
        self.point_rank: int = data[9]
        self.speed: int = data[10]
        self.speed_rank: int = data[11]
        return
    
def getEventTopPlayers(database: Database, server_id: int, event: EventInfo) -> list[EventPlayer]:
    # Collecting data of current top 10 player
    players_data: list[list] = database.selectEventTopPlayers(server_id, event.id)
    players_data = [player_data[:-2] + [player_data[-1], 
            database.selectEventPlayerUpsTime(server_id, event.id, player_data[2], 1)[0], player_data[-2]] 
        for player_data in players_data]
    players_data = [player_data + [i + 1, -1 if ((datetime.now().timestamp() - player_data[-2]) <= 3600) else
            (player_data[8] - database.selectEventPlayerPointsAtTime(server_id, event.id, player_data[2], 
                                                                     before = 3600, limit = 1)[0][0])] 
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
        
def getEventTopPlayerDetail(database: Database, server_id: int, event: EventInfo, point_rank: int) -> EventPlayerDetail:
    # Collecting top players info
    players: list[EventPlayer] = getEventTopPlayers(database, server_id, event); point_rank -= 1
    
    # Collecting player detail from database
    player_detail_data: list = []
    player_detail_data.append(0 if point_rank == 0 else (players[point_rank - 1].point - players[point_rank].point))
    player_detail_data.append(0 if point_rank == 9 else (players[point_rank].point - players[point_rank + 1].point))
    player_detail_data.append(database.selectEventPlayerPointsNumAtTime(server_id, event.id, players[point_rank].uid) - 1)
    
    # Counting recent point changes
    player_ups_time: list[int] = database.selectEventPlayerUpsTime(server_id, event.id, players[point_rank].uid)
    to_recent_point_changes: list[list[int]] = database.selectEventPlayerPointsAtTime(
        server_id, event.id, players[point_rank].uid, 
        after = int(datetime.now().timestamp() - players[point_rank].recent_up_time + 1), 
        limit = 21 + len(player_ups_time), with_time = True)
    player_detail_data.append([])
    for now_to, last_to in zip(to_recent_point_changes[:-1], to_recent_point_changes[1:]):
        if now_to[0] in player_ups_time: continue
        player_detail_data[-1].append((now_to[0], now_to[1] - last_to[1]))
    player_detail_data[-1] = player_detail_data[-1][:min(20, len(player_detail_data[-1]))]
        
    # Counting recent ranges detail
    player_detail_data.append([])
    for time in [3600, 7200, 43200, 86400]:
        after = int(datetime.now().timestamp() - time)
        if after <= event.start_at and after <= players[point_rank].recent_up_time: break
        point_changes = database.selectEventPlayerPointsNumAtTime(server_id, event.id, players[point_rank].uid, 
                                                                  after = time) - 1
        point_before = database.selectEventPlayerPointsAtTime(server_id, event.id, players[point_rank].uid, 
                                                              before = time, limit = 1)[0][0]
        player_detail_data[-1].append((after, point_changes, round(time / point_changes), 
                                       round((players[point_rank].point - point_before) / point_changes)))
    
    # Creating objects from data
    return EventPlayerDetail(players[point_rank], player_detail_data)

class MonthlyPlayer:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.server_id: int = data[0]
        self.event_id: int = data[1]
        self.uid: int = data[2]
        
        self.name: str = data[3]
        self.introduction: str = data[4]
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