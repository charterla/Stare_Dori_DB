from datetime import datetime, timedelta

from utils.db_pg import Database

class EventPlayer:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.uid: int
        self.server_id: int
        self.event_id: int
        
        self.name: str
        self.rank: int
        self.introduction: str
        
        self.point: int
        self.point_rank: int
        self.speed: int
        self.speed_rank: int
        return
    
def getEventTopPlayers(database: Database, server_id: int, event_id: int) -> list[EventPlayer]:
    # Collecting data of current top 10 player
    players_data: list[list] = database.selectEventTopPlayers(server_id, event_id)
    players_data = [
        player_data[:-1] + [i + 1, -1 if ((datetime.now().timestamp()
            - database.selectEventPlayerRecentUpTime(server_id, event_id, player_data[2])) <= 3600) else
            (player_data[6] - database.selectEventPlayerPointAtTimeBefore(server_id, event_id, player_data[2]))] 
        for i, player_data in enumerate(players_data)]
    
    # Counting speed rank of current top 10 player
    to_speed_rank: list[tuple[int, int]] = [(player_data[7] - 1, player_data[8]) for player_data in players_data]
    to_speed_rank = sorted(to_speed_rank, lambda x: x[1], reverse = True); players_data[to_speed_rank[0][0]].append(0)
    for last_to, now_to in zip(to_speed_rank[:-1], to_speed_rank[1:]):
        if last_to[1] == now_to[1]: players_data[now_to[0]].append(players_data[last_to[0]][-1])
        else: players_data[now_to[0]].append(players_data[last_to[0]][-1] + 1)
        
    # Creating objects from data
    return [EventPlayer(player_data) for player_data in players_data]