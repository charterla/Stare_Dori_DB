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

        self.createTableForChannels()
        self.channel_status = self.getChannelsStatus()

    def __del__(self):
        self.connection.close()
        print("DataBase disconnected.")

    def createTableForChannels(self):
        cursor = self.connection.cursor()
        table = f"CREATE TABLE IF NOT EXISTS channel_status ("\
              + f" id BIGINT PRIMARY KEY,"\
              + f" serverId SMALLINT,"\
              + f" isChangeNotify BOOLEAN,"\
              + f" isCPNotify BOOLEAN"\
              + f");"
        cursor.execute(table)
        self.connection.commit()
        cursor.close()

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
        index = f"CREATE INDEX IF NOT EXISTS \"{server_id}_{event_id}_event_players_nowPoints_desc\" "\
              + f"ON \"{server_id}_{event_id}_event_players\" (nowPoints DESC NULLS LAST);"
        cursor.execute(table)
        cursor.execute(index)
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
        table = f"CREATE TABLE IF NOT EXISTS \"{server_id}_{event_id}_event_rank\" ("\
              + f" uid INTEGER,"\
              + f" updateTime BIGINT,"\
              + f" fromRank SMALLINT,"\
              + f" toRank SMALLINT,"\
              + f" PRIMARY KEY (uid, updateTime),"\
              + f" CONSTRAINT to_player FOREIGN KEY (uid) REFERENCES \"{server_id}_{event_id}_event_players\"(uid)"\
              + f");"
        index = f"CREATE INDEX IF NOT EXISTS \"{server_id}_{event_id}_event_rank_updateTime_desc\" "\
              + f"ON \"{server_id}_{event_id}_event_rank\" (updateTime DESC NULLS LAST);"
        cursor.execute(table)
        cursor.execute(index)
        function = f"CREATE OR REPLACE FUNCTION \"{server_id}_{event_id}_event_newPoints\"() RETURNS TRIGGER AS $$\n"\
                 + f"BEGIN\n"\
                 + f"    UPDATE \"{server_id}_{event_id}_event_players\" SET nowPoints = new.value, lastUpdateTime = new.time\n"\
                 + f"        WHERE uid = new.uid AND nowPoints < new.value;\n"\
                 + f"    RETURN NEW;\n"\
                 + f"END;\n"\
                 + f"\n"\
                 + f"$$ LANGUAGE plpgsql;"
        trigger = f"CREATE OR REPLACE TRIGGER \"{server_id}_{event_id}_event_newPoints\" "\
                + f"AFTER INSERT ON \"{server_id}_{event_id}_event_points\" "\
                + f"FOR EACH ROW EXECUTE PROCEDURE\"{server_id}_{event_id}_event_newPoints\"();"
        cursor.execute(function)
        cursor.execute(trigger)
        function = f"CREATE OR REPLACE FUNCTION \"{server_id}_{event_id}_event_newUpdate\"() RETURNS TRIGGER AS $$\n"\
                 + f"DECLARE \n"\
                 + f"    checking RECORD;\n"\
                 + f"    now RECORD;\n"\
                 + f"BEGIN\n"\
                 + f"    FOR checking IN \n"\
                 + f"        (SELECT uid, RANK() OVER (ORDER BY nowPoints DESC) rank \n"\
                 + f"            FROM \"{server_id}_{event_id}_event_players\") \n"\
                 + f"    LOOP \n"\
                 + f"        FOR now IN (SELECT * FROM \"{server_id}_{event_id}_event_rank\" \n"\
                 + f"            WHERE uid = checking.uid ORDER BY updateTime DESC LIMIT 1) \n"\
                 + f"        LOOP \n"\
                 + f"            IF now.toRank <> checking.rank THEN \n"\
                 + f"                INSERT INTO \"{server_id}_{event_id}_event_rank\" (uid, updateTime, fromRank, toRank) \n"\
                 + f"                VALUES (checking.uid, new.lastUpdateTime, now.toRank, checking.rank) \n"\
                 + f"                ON CONFLICT (uid, updateTime) DO UPDATE SET toRank = EXCLUDED.toRank;\n"\
                 + f"            END IF;\n"\
                 + f"        END LOOP;\n"\
                 + f"    END LOOP;\n"\
                 + f"    IF new.lastUpdateTime - old.lastUpdateTime >= 420000 THEN\n"\
                 + f"        INSERT INTO \"{server_id}_{event_id}_event_intervals\" (uid, startTime, endTime, valueDelta) \n"\
                 + f"            VALUES (new.uid, old.lastUpdateTime, new.lastUpdateTime, new.nowPoints - old.nowPoints);\n"\
                 + f"    END IF;\n"\
                 + f"    RETURN NEW;\n"\
                 + f"END;\n"\
                 + f"\n"\
                 + f"$$ LANGUAGE plpgsql;"
        trigger = f"CREATE OR REPLACE TRIGGER \"{server_id}_{event_id}_event_newUpdate\" "\
                + f"AFTER UPDATE OF nowPoints ON \"{server_id}_{event_id}_event_players\" "\
                + f"FOR EACH ROW EXECUTE PROCEDURE\"{server_id}_{event_id}_event_newUpdate\"();"
        cursor.execute(function)
        cursor.execute(trigger)
        self.connection.commit() 
        cursor.close()

    def insertOrUpdateData(self, insert):
        cursor = self.connection.cursor()
        cursor.execute(insert)
        self.connection.commit()
        cursor.close()

    def insertChannelStatus(self, channel_id: int):
        self.insertOrUpdateData(
            f"INSERT INTO channel_status (id, serverId, isChangeNotify, isCPNotify) "\
          + f"VALUES ({channel_id}, 2, false, false)"\
          + f"ON CONFLICT (id) DO NOTHING;")

    def insertEventPlayers(self, event_id: int, players: list[dict], default_time: int, server_id: Optional[int] = 2):
        if players == []: return
        for player in players: 
            player["name"] = player["name"].replace("\'", "\'\'").replace("\"", "\"\"")
            player["introduction"] = player["introduction"].replace("\'", "\'\'").replace("\"", "\"\"")
        players_value = [f"({player['uid']}, \'{player['name']}\', \'{player['introduction']}\', {player['rank']}, 0, {default_time})"
                         for player in players]
        self.insertOrUpdateData(
            f"INSERT INTO \"{server_id}_{event_id}_event_players\" (uid, name, introduction, rank, nowPoints, lastUpdateTime) "\
          + f"VALUES {', '.join(players_value)} "\
          + f"ON CONFLICT (uid) DO UPDATE SET name = EXCLUDED.name, introduction = EXCLUDED.introduction, rank = EXCLUDED.rank;")

    def insertEventPoints(self, event_id: int, points: list[dict], server_id: Optional[int] = 2):
        if points == []: return
        points_value = [f"({point['time']}, {point['uid']}, {point['value']})" for point in points]
        self.insertOrUpdateData(
            f"INSERT INTO \"{server_id}_{event_id}_event_points\" (time, uid, value) "\
          + f"VALUES {', '.join(points_value)} "\
          + f"ON CONFLICT (uid, value) DO NOTHING;")

    def insertEventRanks(self, event_id: int, players: list[dict], default_time: int, server_id: Optional[int] = 2):
        if players == []: return
        ranks_value = [f"({player['uid']}, {default_time}, -1, -1)" for player in players]
        self.insertOrUpdateData(
            f"INSERT INTO \"{server_id}_{event_id}_event_rank\" (uid, updateTime, fromRank, toRank) "\
          + f"VALUES {', '.join(ranks_value)} "\
          + f"ON CONFLICT (uid, updateTime) DO UPDATE SET toRank = EXCLUDED.toRank;")

    def getData(self, query):
        cursor = self.connection.cursor()
        cursor.execute(query)
        result = cursor.fetchall()
        cursor.close()
        return result
    
    def getChannelsStatus(self, channels_id: Optional[list[int]] = []):
        if channels_id == []: return self.getData(f"SELECT * FROM channel_status;")
        else: return self.getData(
            f"SELECT * FROM channel_status WHERE id IN ({', '.join(map(str, channels_id))});")
    
    def getChannelsToNotifyChange(self):
        return self.getData( f"SELECT id FROM channel_status WHERE isChangeNotify = true;")
    
    def getChannelsToNotifyCP(self):
        return self.getData( f"SELECT id FROM channel_status WHERE isCPNotify = true;")

    def getEventPlayerName(self, event_id: int, uid: int, server_id: Optional[int] = 2):
        result = self.getData(f"SELECT name FROM \"{server_id}_{event_id}_event_players\" WHERE uid = {uid};")
        return None if result == () else result[0][0]

    def getEventTopPlayers(self, event_id: int, ranking: Optional[int] = 10, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT * FROM \"{server_id}_{event_id}_event_players\" ORDER BY nowPoints DESC LIMIT {ranking};")
        
    def getEventPlayerPointsAtTimeBefore(self, event_id: int, uid: int, time_before: Optional[int] = 3600000, server_id: Optional[int] = 2):
        result = self.getData(
            f"SELECT value FROM \"{server_id}_{event_id}_event_points\" "\
          + f"WHERE uid = {uid} AND time < (ROUND(EXTRACT(EPOCH FROM now()) * 1000) - {time_before}) "\
          + f"ORDER BY value DESC LIMIT 1;")
        return 0 if result == () else result[0][0]
    
    def getEventPlayerRecentPoints(self, event_id: int, uid: int, num: Optional[int] = 41, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT time, value FROM \"{server_id}_{event_id}_event_points\" "\
          + f"WHERE uid = {uid} ORDER BY time DESC LIMIT {num};")
    
    def getEventPlayerRecentPointsAtTimeAfter(self, event_id: int, uid: int, time_after: int, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT time, value FROM \"{server_id}_{event_id}_event_points\" "\
          + f"WHERE uid = {uid} AND time >= (ROUND(EXTRACT(EPOCH FROM now()) * 1000) - {time_after}) ORDER BY time DESC;")
    
    def getEventPlayerPointsNumAtTimeAfter(self, event_id: int, uid: int, time_after: Optional[int] = 3600000, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT COUNT(uid) FROM \"{server_id}_{event_id}_event_points\" "\
          + f"WHERE uid = {uid} AND time >= (ROUND(EXTRACT(EPOCH FROM now()) * 1000) - {time_after});")[0][0]
    
    def getEventPlayerIntervals(self, event_id: int, uid: int, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT startTime, endTime, valueDelta FROM \"{server_id}_{event_id}_event_intervals\" "\
          + f"WHERE uid = {uid} ORDER BY startTime DESC;")
    
    def getEventPlayerRanks(self, event_id: int, uid: int, num: Optional[int] = None, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT updateTime, fromRank, toRank FROM \"{server_id}_{event_id}_event_rank\" "\
          + f"WHERE uid = {uid} AND ((0 <= fromRank AND fromRank <= 10) OR (0 <= toRank AND toRank <= 10)) "\
          + f"ORDER BY updateTime DESC{'' if num == None else (' LIMIT ' + str(num))};")
    
    def getEventPlayerRankUpToTopTimes(self, event_id: int, uid: int, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT updateTime FROM \"{server_id}_{event_id}_event_rank\" "\
          + f"WHERE uid = {uid} AND (fromRank < 0 OR fromRank > 10) AND 0 <= toRank AND toRank <= 10 ORDER BY updateTime DESC;")
    
    def getEventPlayersRankChangesAtTimeAfter(self, event_id: int, time_after: Optional[int] = 60000, server_id: Optional[int] = 2):
        return self.getData(
            f"SELECT uid, fromRank, toRank FROM \"{server_id}_{event_id}_event_rank\" "\
          + f"WHERE updateTime >= (ROUND(EXTRACT(EPOCH FROM now()) * 1000) - {time_after}) "\
          + f"AND ((0 <= fromRank AND fromRank <= 10) OR (0 <= toRank AND toRank <= 10));")
    
    def updateChannelStatus(self, channel_id: int, server_id: Optional[int] = None, is_change_notify: Optional[bool] = None, is_CP_notify: Optional[bool] = None):
        update_parameters = []
        if server_id != None: update_parameters.append(f"serverId = {server_id}")
        if is_change_notify != None: update_parameters.append(f"isChangeNotify = {'true' if is_change_notify else 'false'}")
        if is_CP_notify != None: update_parameters.append(f"isCPNotify = {'true' if is_CP_notify else 'false'}")
        if update_parameters == []: return
        
        self.insertOrUpdateData(
            f"UPDATE channel_status SET {', '.join(update_parameters)} WHERE id = {channel_id};")
