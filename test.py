from pathlib import Path
from environs import Env

from utils.db_pg import Database
from objs.activity import getRecentEvent, getRecentMonthly
from objs.player import getEventTopPlayers, getEventTopPlayerDetail, getMonthlyTopPlayers

env = Env(); env.read_env(Path("./.env"))

database: Database = Database(
    host = env.str("DB_HOST"), name = env.str("DB_NAME"), user = env.str("DB_USER"),
    password = env.str("DB_PASSWORD"), port = env.int("DB_PORT"))

server_id = 1
# recent_event = getRecentEvent(database, server_id)
# recent_event_tops = getEventTopPlayers(database, server_id, recent_event)

# point_rank = 1
# recent_event_top_detail = getEventTopPlayerDetail(database, server_id, recent_event, point_rank)

recent_monthly = getRecentMonthly(database, server_id)
recent_monthly_tops = getMonthlyTopPlayers(database, server_id, recent_monthly)
print([player.__dict__ for player in recent_monthly_tops])