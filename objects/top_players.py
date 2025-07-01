from datetime import datetime, timedelta
from helpers.db_pg import Database

class TopPlayerInfo():
    def __init__(self, top_player: list):
        # Initializing object with data provided
        self.uid: int = top_player[0]
        self.name: str = top_player[1]
        self.introduction: str = top_player[2]
        self.rank: int = top_player[3]
        self.now_points: int = top_player[4]
        self.last_update_time: int = top_player[5]

        # Waiting to be filled with details
        self.speed: int
        self.speed_rank: int
        self.now_rank: int
        self.points_up_delta: int
        self.points_down_delta: int
        self.recent_points_deltas: list[dict] = []
        self.interval_details: list[dict] = []
        self.stop_intervals: dict[list[dict]] = {}

def getTopPlayersBriefList(recent_event_id: int, database: Database) -> list[TopPlayerInfo]:
    # Constructing the list of by raw data get from database
    top_players = [
        TopPlayerInfo(top_player) for top_player in database.getEventTopPlayers(recent_event_id)
    ]

    # Assigning the rank of players and Generating the list players' speed
    speeds: list[list] = []
    for i, top_player in enumerate(top_players):
        # Assigning the rank of players
        top_player.now_rank = i + 1

        # Geting recent interval to judge whether player keeped in top 10 or not
        player_recent_interval = database.getEventPlayerIntervals(recent_event_id, top_player.uid)[0]
        if player_recent_interval[2] > 130000 and (datetime.now().timestamp() - \
            (player_recent_interval[2] / 1000)) <= 3600: speeds.append([i, -1])
        else: speeds.append([i, top_player.now_points - database.\
            getEventPlayerPointsAtTimeBefore(recent_event_id, top_players[i].uid)])
            
    # Sorting the speed list order by speed descending 
    speeds = sorted(speeds, key = lambda x: x[1], reverse = True)

    # Assignment the speed and speed rank to the players
    for i in range(len(speeds)):
        top_players[speeds[i][0]].speed = speeds[i][1]
        if i == 0: top_players[speeds[i][0]].speed_rank = 1
        elif top_players[speeds[i - 1][0]].speed == speeds[i][1]:
            top_players[speeds[i][0]].speed_rank = top_players[speeds[i - 1][0]].speed_rank
        else: top_players[speeds[i][0]].speed_rank = top_players[speeds[i - 1][0]].speed_rank + 1

    return top_players

def getTopPlayerDetail(rank: int, recent_event_id: int, database: Database) -> TopPlayerInfo:
    # Getting the list of top 10 players' brief and Locating the specified player
    top_players = getTopPlayersBriefList(recent_event_id, database)
    top_player = top_players[rank]

    # Counting the points delta with the players upper and lower
    if rank == 0: top_player.points_up_delta = 0
    else: top_player.points_up_delta = top_players[rank - 1].now_points - top_player.now_points
    if rank == 9: top_player.points_down_delta = 0
    else: top_player.points_down_delta = top_player.now_points - top_players[rank + 1].now_points

    # Counting the recent points delta of specified player
    recent_points = database.getEventPlayerRecentPoints(recent_event_id, top_player.uid)
    top_player.recent_points_deltas = [{
            "change_time": datetime.fromtimestamp(recent_points[i][0] / 1000).strftime("%H:%M"), 
            "change_points": recent_points[i][1] - recent_points[i + 1][1]
        } for i in range(20)
    ]

    # Counting the interval datails of specified player
    eles = [1, 2, 12, 24]
    interval_data = [[
            database.getEventPlayerPointsNumAtTimeAfter(recent_event_id, top_player.uid, 3600000 * ele),
            database.getEventPlayerPointsAtTimeBefore(recent_event_id, top_player.uid, 3600000 * ele)
        ] for ele in eles
    ]
    top_player.interval_details = [{
            "time_interval_start": (datetime.now() - timedelta(minutes = 60 * ele)).strftime("%H:%M"),
            "time_interval_end": datetime.now().strftime("%H:%M"),
            "change_num": interval_data[i][0],
            "average_change_interval": "--:--" if interval_data[i][0] == 0 \
                else datetime.fromtimestamp(3600 * ele / interval_data[i][0]).strftime("%M:%S"),
            "average_change_points": "-----" if interval_data[i][0] == 0 \
                else int((top_player.now_points - interval_data[i][1]) / interval_data[i][0])
        } for i, ele in enumerate(eles)
    ]
    
    # Counting the stop intervals of specified player
    stop_intervals = database.getEventPlayerIntervals(recent_event_id, top_player.uid)
    if datetime.now().timestamp() - (top_player.last_update_time / 1000) > 420:
        stop_intervals = ([top_player.last_update_time, \
                           int(datetime.now().timestamp() * 1000), 0], ) + stop_intervals
    stop_intervals = [{
            "start_time": datetime.fromtimestamp(stop_interval[0] / 1000).strftime("%m-%d %H:%M"),
            "end_time": datetime.fromtimestamp(stop_interval[1] / 1000).strftime("%m-%d %H:%M"),
            "time_delta": timedelta(milliseconds = stop_interval[1] - stop_interval[0])
        } for stop_interval in stop_intervals
    ]
    for stop_interval in stop_intervals:
        if stop_interval["start_time"].split()[0] not in top_player.stop_intervals:
            top_player.stop_intervals[stop_interval["start_time"].split()[0]] = []
        top_player.stop_intervals[stop_interval["start_time"].split()[0]].append({
            "start_time": stop_interval["start_time"].split()[-1],
            "end_time": stop_interval["end_time"].split()[-1],
            "time_delta": f"{str(stop_interval['time_delta'].days).rjust(2)}d"\
                        + f"{str(int(stop_interval['time_delta'].seconds / 3600) % 24).rjust(2)}h"\
                        + f"{str(int(stop_interval['time_delta'].seconds / 60) % 60).rjust(2)}m"
        })
        
    return top_player