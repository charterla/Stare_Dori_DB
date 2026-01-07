from pathlib import Path
from environs import Env

from utils.db_pg import Database

env = Env(); env.read_env(Path("./.env"))

database: Database = Database(
    host = env.str("DB_HOST"), name = env.str("DB_NAME"), user = env.str("DB_USER"),
    password = env.str("DB_PASSWORD"), port = env.int("DB_PORT"))

database.createTableForUsers()
database.insertUserSetting(int(env.str("OWNER")))
database.insertUserUid(int(env.str("OWNER")), 2, 8888888)
test_result = database.selectUserUid(int(env.str("OWNER")))
print(test_result)