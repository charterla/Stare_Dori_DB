import pg8000
from typing import Optional

class Database():
    def __init__(self, host: str, name: str, user: str, password: str, port: int):
        self.connection = pg8000.connect(
            host = host,
            database = name,
            user = user,
            password = password,
            port = port
        )
        print("DataBase connected.")

    def __del__(self):
        self.connection.close()
        print("DataBase disconnected.")

    def createTableForEvent(self, event_id: int, server_id: Optional[int] = 2):
        cursor = self.connection.cursor()
        table = f"CREATE TABLE IF NOT EXISTS \"{server_id}_{event_id}_event_players\" ("\
              + f" uid BIGINT PRIMARY KEY,"\
              + f" name VARCHAR(16),"\
              + f" introduction VARCHAR(32),"\
              + f" rank SMALLINT,"\
              + f" nowPoints INTEGER,"\
              + f" lastUpdateTime BIGINT"\
              + f");"
        cursor.execute(table)
        table = f"CREATE TABLE IF NOT EXISTS \"{server_id}_{event_id}_event_points\" ("\
              + f" time BIGINT,"\
              + f" uid INTEGER,"\
              + f" value INTEGER,"\
              + f" PRIMARY KEY (uid, value),"\
              + f" CONSTRAINT to_player FOREIGN KEY (uid) REFERENCES \"{server_id}_{event_id}_event_players\"(uid)"\
              + f");"
        cursor.execute(table)
        table = f"CREATE TABLE IF NOT EXISTS \"{server_id}_{event_id}_event_intervals\" ("\
              + f" uid INTEGER,"\
              + f" startTime BIGINT,"\
              + f" endTime BIGINT,"\
              + f" valueDelta INTEGER,"\
              + f" PRIMARY KEY (uid, startTime),"\
              + f" CONSTRAINT to_player FOREIGN KEY (uid) REFERENCES \"{server_id}_{event_id}_event_players\"(uid)"\
              + f");"
        cursor.execute(table)
        function = f"CREATE OR REPLACE FUNCTION \"{server_id}_{event_id}_event_newPoints\"() RETURNS TRIGGER AS $$\n"\
                 + f"BEGIN\n"\
                 + f"    UPDATE \"{server_id}_{event_id}_event_players\" SET nowPoints = new.value, lastUpdateTime = new.time\n"\
                 + f"        WHERE uid = new.uid and nowPoints < new.value;\n"\
                 + f"    RETURN NEW;\n"\
                 + f"END;\n"\
                 + f"\n"\
                 + f"$$ LANGUAGE plpgsql;"
        cursor.execute(function)
        trigger = f"CREATE OR REPLACE TRIGGER \"{server_id}_{event_id}_event_newPoints\" "\
                + f"AFTER INSERT ON \"{server_id}_{event_id}_event_points\" "\
                + f"FOR EACH ROW "\
                + f"EXECUTE PROCEDURE\"{server_id}_{event_id}_event_newPoints\"();"
        cursor.execute(trigger)
        function = f"CREATE OR REPLACE FUNCTION \"{server_id}_{event_id}_event_newUpdate\"() RETURNS TRIGGER AS $$\n"\
                 + f"BEGIN\n"\
                 + f"    IF new.lastUpdateTime - old.lastUpdateTime >= 420000 THEN\n"\
                 + f"        INSERT INTO \"{server_id}_{event_id}_event_intervals\" (uid, startTime, endTime, valueDelta) \n"\
                 + f"            VALUES (new.uid, old.lastUpdateTime, new.lastUpdateTime, new.nowPoints - old.nowPoints);\n"\
                 + f"    END IF;\n"\
                 + f"    RETURN NEW;\n"\
                 + f"END;\n"\
                 + f"\n"\
                 + f"$$ LANGUAGE plpgsql;"
        cursor.execute(function)
        trigger = f"CREATE OR REPLACE TRIGGER \"{server_id}_{event_id}_event_newUpdate\" "\
                + f"AFTER UPDATE OF lastUpdateTime ON \"{server_id}_{event_id}_event_players\" "\
                + f"FOR EACH ROW "\
                + f"EXECUTE PROCEDURE\"{server_id}_{event_id}_event_newUpdate\"();"
        cursor.execute(trigger)
        self.connection.commit()
        cursor.close()

    def insertData(self, insect):
        cursor = self.connection.cursor()
        cursor.execute(insect)
        self.connection.commit()
        cursor.close()

    def insertEventPlayers(self, event_id: int, players: list[dict], default_time: int, server_id: Optional[int] = 2):
        if players == []: return
        for player in players: 
            player["name"] = player["name"].replace("\'", "\'\'").replace("\"", "\"\"")
            player["introduction"] = player["introduction"].replace("\'", "\'\'").replace("\"", "\"\"")
        players_value = [f"({player['uid']}, \'{player['name']}\', \'{player['introduction']}\', {player['rank']}, 0, {default_time})"
                         for player in players]
        self.insertData(
            f"INSERT INTO \"{server_id}_{event_id}_event_players\" (uid, name, introduction, rank, nowPoints, lastUpdateTime) "\
          + f"VALUES {', '.join(players_value)} "\
          + f"ON CONFLICT (uid) DO UPDATE SET name = EXCLUDED.name, introduction = EXCLUDED.introduction, rank = EXCLUDED.rank;")

    def insertEventPoints(self, event_id: int, points: list[dict], server_id: Optional[int] = 2):
        if points == []: return
        points_value = [f"({point['time']}, {point['uid']}, {point['value']})"
                         for point in points]
        self.insertData(
            f"INSERT INTO \"{server_id}_{event_id}_event_points\" (time, uid, value) "\
          + f"VALUES {', '.join(points_value)} "\
          + f"ON CONFLICT (uid, value) DO NOTHING;")

    def getData(self, query):
        cursor = self.connection.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        return result

    def getEventTopPlayers(self, event_id: int, ranking: Optional[int] = 10, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT * FROM \"{server_id}_{event_id}_event_players\" ORDER BY nowPoints DESC LIMIT {ranking};")
        
    def getEventPlayerPointsAtTimeBefore(self, event_id: int, uid: int, time_before: Optional[int] = 3600000, server_id: Optional[int] = 2):
        result = self.getData(
            f"SELECT value FROM \"{server_id}_{event_id}_event_points\" "\
          + f"WHERE uid = {uid} and time < (ROUND(EXTRACT(EPOCH FROM now()) * 1000) - {time_before}) "\
          + f"ORDER BY value DESC LIMIT 1;")
        return 0 if result == [] else result[0][0]
    
    def getEventPlayerRecentPoints(self, event_id: int, uid: int, num: Optional[int] = 21, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT time, value FROM \"{server_id}_{event_id}_event_points\" "\
          + f"WHERE uid = {uid} ORDER BY time DESC LIMIT {num};")
    
    def getEventPlayerPointsNumAtTimeAfter(self, event_id: int, uid: int, time_before: Optional[int] = 3600000, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT COUNT(uid) FROM \"{server_id}_{event_id}_event_points\" "\
          + f"WHERE uid = {uid} and time >= (ROUND(EXTRACT(EPOCH FROM now()) * 1000) - {time_before});")[0][0]
    
    def getEventPlayerIntervals(self, event_id: int, uid: int, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT startTime, endTime, valueDelta FROM \"{server_id}_{event_id}_event_intervals\" "\
          + f"WHERE uid = {uid} ORDER BY startTime DESC;")
