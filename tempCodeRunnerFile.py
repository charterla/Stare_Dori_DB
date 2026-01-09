from datetime import datetime
from pathlib import Path
from environs import Env

from utils.db_pg import Database
from objs.activity import getRecentEvent, getRecentMonthly
from objs.player import getEventTopPlayers, getEventTopPlayerDetail, getEventTopPlayerDaily, getMonthlyTopPlayers

env = Env(); env.read_env(Path("./.env"))

database: Database = Database(
    host = env.str("DB_HOST"), name = env.str("DB_NAME"), user = env.str("DB_USER"),
    password = env.str("DB_PASSWORD"), port = env.int("DB_PORT"))

server_id = 2; now_time = int(datetime.now().timestamp())

recent_event = getRecentEvent(database, server_id)
# recent_event_tops = getEventTopPlayers(database, server_id, recent_event, now_time)
# print([player.__dict__ for player in recent_event_tops])

point_rank = 1
# recent_event_top_detail = getEventTopPlayerDetail(database, server_id, recent_event, now_time, point_rank)
# print(recent_event_top_detail.__dict__)

recent_event_top_daily = getEventTopPlayerDaily(database, server_id, recent_event, now_time, point_rank)
print(recent_event_top_daily.__dict__)

# recent_monthly = getRecentMonthly(database, server_id)
# recent_monthly_tops = getMonthlyTopPlayers(database, server_id, recent_monthly)
# print([player.__dict__ for player in recent_monthly_tops])