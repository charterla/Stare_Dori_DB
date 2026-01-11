import pg8000
from typing import Optional
from logging import Logger

class Database:
    def __init__(self, host: str, name: str, user: str, password: str, port: int, logger: Optional[Logger] = None):
        self.connection = pg8000.connect(
            host = host,
            database = name,
            user = user,
            password = password,
            port = port
        ); self.logger = logger
        if self.logger != None: self.logger.info("Database connected")
        return

    def __del__(self):
        self.connection.close()
        if self.logger != None: self.logger.info("Database disconnected")
        return
    
    # %% generating SQL command 
    def __createTable(self, table_name: str, columns: dict[str, str],
                      primary_keys: Optional[list[str]] = [], 
                      foreign_keys: Optional[list[list[str]]] = []) -> str:
        command = f"CREATE TABLE IF NOT EXISTS {table_name} (" \
                + (", ".join([f"{name} {type}" for name, type in columns.items()])) \
                + ("" if primary_keys == [] else f", PRIMARY KEY ({', '.join(primary_keys)})") \
                + ("" if foreign_keys == [] else ", " + ", ".join([
                    f"CONSTRAINT {attr[0]} FOREIGN KEY ({attr[1]}) REFERENCES {attr[2]}({attr[3]})" 
                    for attr in foreign_keys])) \
                + ");"
        return command
        
    def __createIndex(self, index_name: str, table_name: str, orders: list[str]) -> str:
        command = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({', '.join(orders)});"
        return command
    
    def __select(self, tables: list[str], columns: list[str], conditions: Optional[str] = "", 
                 group_by: Optional[str] = "", order_by: Optional[list[str]] = [], limit: Optional[int] = None) -> str:
        command = f"SELECT {', '.join(columns)} FROM {', '.join(tables)}" \
                + ("" if conditions == "" else f" WHERE {conditions}") \
                + ("" if group_by == "" else f" GROUP BY {group_by}") \
                + ("" if order_by == [] else f" ORDER BY {', '.join(order_by)}") \
                + ("" if limit == None else f" LIMIT {str(limit)}") \
                + ";"
        return command
    
    def __insert(self, table_name: str, columns: list[str], values: list[list[str]], 
                 conflict_targets: list[str], conflict_action: str) -> str:
        command = f"INSERT INTO {table_name} ({', '.join(columns)})" \
                + " VALUES " + ", ".join([f"({', '.join(value)})" for value in values]) \
                + f" ON CONFLICT ({', '.join(conflict_targets)}) DO {conflict_action};"
        return command
    
    def __update(self, table_name: str, set_columns: dict[str, str], conditions: str) -> str:
        set_columns: list = [column + " = " + value for column, value in set_columns.items()]
        command = f"UPDATE {table_name} SET {', '.join(set_columns)}" \
                + ("" if conditions == "" else f" WHERE {conditions}") \
                + ";"
        return command
    
    def __conditional(self, conditions: list[str], commands_list: list[list[str]]) -> str:
        command = f"IF {conditions[0]} THEN {' '.join(commands_list[0])}" \
                + " " + " ".join([f"ELSIF {condition} THEN {' '.join(commands)}" 
                                  for condition, commands in zip(conditions[1:], commands_list[1:])]) \
                + (f" ELSE {commands_list[-1]}" \
                       if len(commands_list) > 1 and len(commands_list) - len(conditions) == 1 else "") \
                + " END IF;"
        return command
    
    def __forLoop(self, index: str, range: str, commands: list[str]) -> str:
        command = f"FOR {index} IN ({range}) LOOP {' '.join(commands)} END LOOP;"
        return command
    
    def __createTriggerFunction(self, function_name: str, commands: list[str], 
                                declares: Optional[dict[str, str]] = {}) -> str:
        command = f"CREATE OR REPLACE FUNCTION {function_name}() RETURNS TRIGGER AS $$" \
                + ("" if declares == {} else " DECLARE " \
                     + " ".join([f"{var_name} {var_type};" for var_name, var_type in declares.items()])) \
                + f" BEGIN {' '.join(commands)} RETURN NEW; END; $$ LANGUAGE plpgsql;"
        return command
    
    def __createTrigger(self, trigger_name: str, trigger_when: str, trigger_event: str,
                        table_name: str, execute_procedure: str, for_each: Optional[str] = ""):
        command = f"CREATE OR REPLACE TRIGGER {trigger_name} {trigger_when} {trigger_event} ON {table_name}" \
                + ("" if for_each == "" else f" FOR EACH {for_each}") \
                + f" EXECUTE PROCEDURE {execute_procedure}();"
        return command
    
    # %% creating table and corresponding trigger with function
    def createTableForUsers(self) -> None:
        cursor = self.connection.cursor()
        table = self.__createTable("user_setting", 
                                   {"id": "BIGINT PRIMARY KEY", "serverId": "SMALLINT", 
                                    "isChangeNotify": "BOOLEAN", "isCPNotify": "BOOLEAN"})
        cursor.execute(table)
        table = self.__createTable("user_uid", {"id": "BIGINT", "serverId": "SMALLINT", "uid": "BIGINT"},
                                   ["serverId", "id"], [["to_user", "id", "user_setting", "id"]])
        cursor.execute(table)
        table = self.__createTable("user_target",
                                   {"id": "BIGINT", "serverId": "SMALLINT", "eventId": "SMALLINT", 
                                    "targetPoints": "INTEGER"},
                                   ["serverId", "eventId", "id"], 
                                   [["to_user_uid", "serverId, id", "user_uid", "serverId, id"]])
        cursor.execute(table); self.connection.commit()
        cursor.close()
        
    def createTableForChannels(self) -> None:
        cursor = self.connection.cursor()
        table = self.__createTable("channel_setting", 
                                   {"id": "BIGINT PRIMARY KEY", "serverId": "SMALLINT"})
        cursor.execute(table); self.connection.commit()
        cursor.close()
        
    def createTableForEvents(self) -> None:
        cursor = self.connection.cursor()
        table = self.__createTable("event_detail",
                                   {"id": "SMALLINT", "serverId": "SMALLINT", "name": "VARCHAR(128)", 
                                    "type": "SMALLINT", "startAt": "BIGINT", "endAt": "BIGINT"},
                                   ["serverId", "id"])
        cursor.execute(table); self.connection.commit()
        
        table = self.__createTable("event_player",
                                   {"serverId": "SMALLINT", "eventId": "SMALLINT", "uid": "BIGINT",
                                    "name": "VARCHAR(32)", "introduction": "VARCHAR(64)",
                                    "rank": "SMALLINT", "nowPoints": "INTEGER", "lastUpdateTime": "BIGINT"},
                                   ["serverId", "eventId", "uid"], 
                                   [["to_event", "serverId, eventId", "event_detail", "serverId, id"]])
        index = self.__createIndex("event_player_nowPoints_desc", "event_player", 
                                   ["serverId", "eventId", "nowPoints DESC NULLS LAST"])
        cursor.execute(table); cursor.execute(index); self.connection.commit()
        
        table = self.__createTable("event_points",
                                   {"serverId": "SMALLINT", "eventId": "SMALLINT", "uid": "BIGINT",
                                    "value": "INTEGER", "time": "BIGINT"},
                                   ["serverId", "eventId", "uid", "value"],
                                   [["to_player", "serverId, eventId, uid", "event_player", "serverId, eventId, uid"]])
        cursor.execute(table)
        table = self.__createTable("event_intervals",
                                   {"serverId": "SMALLINT", "eventId": "SMALLINT", "uid": "BIGINT",
                                    "startTime": "BIGINT", "endTime": "BIGINT", "valueDelta": "INTEGER"},
                                   ["serverId", "eventId", "uid", "startTime"],
                                   [["to_player", "serverId, eventId, uid", "event_player", "serverId, eventId, uid"]])
        cursor.execute(table)
        table = self.__createTable("event_ranks",
                                   {"serverId": "SMALLINT", "eventId": "SMALLINT", "uid": "BIGINT",
                                    "updateTime": "BIGINT", "fromRank": "SMALLINT", "toRank": "SMALLINT"},
                                   ["serverId", "eventId", "uid", "updateTime"],
                                   [["to_player", "serverId, eventId, uid", "event_player", "serverId, eventId, uid"]])
        index = self.__createIndex("event_ranks_updateTime_desc", "event_ranks", 
                                   ["serverId", "eventId", "updateTime DESC NULLS LAST"])
        cursor.execute(table); cursor.execute(index); self.connection.commit()
        
        update = self.__update("event_player", {"nowPoints": "new.value", "lastUpdateTime": "new.time"}, 
                               "serverId = new.serverId AND eventId = new.eventId AND uid = new.uid AND nowPoints < new.value")
        trigger_function = self.__createTriggerFunction("event_newPoints", [update])
        trigger = self.__createTrigger("event_newPoints", "AFTER", "INSERT", "event_points", "event_newPoints", "ROW")
        cursor.execute(trigger_function); cursor.execute(trigger); self.connection.commit()
        
        insert = self.__insert("event_ranks", ["serverId", "eventId", "uid", "updateTime", "fromRank", "toRank"], 
                               [["new.serverId", "new.eventId", "checking.uid", 
                                 "new.lastUpdateTime", "now.toRank", "checking.rank"]],
                               ["serverId", "eventId", "uid", "updateTime"], "UPDATE SET toRank = EXCLUDED.toRank")
        conditional = self.__conditional(["now.toRank <> checking.rank"], [[insert]])
        range = self.__select(["event_ranks"], ["*"], "uid = checking.uid", 
                              order_by = ["updateTime DESC"], limit = 1)[:-1]
        for_loop = self.__forLoop("now", range, [conditional])
        range = self.__select(["event_player"], ["uid", "RANK() OVER (ORDER BY nowPoints DESC) AS rank"], 
                              "serverId = new.serverId AND eventId = new.eventId")[:-1]
        for_loop = self.__forLoop("checking", range, [for_loop])
        commands = [for_loop]
        insert = self.__insert("event_intervals", ["serverId", "eventId", "uid", "startTime", "endTime", "valueDelta"], 
                               [["new.serverId", "new.eventId", "new.uid", 
                                 "old.lastUpdateTime", "new.lastUpdateTime", "new.nowPoints - old.nowPoints"]], 
                               ["serverId", "eventId", "uid", "startTime"], "NOTHING")
        conditional = self.__conditional(["new.lastUpdateTime - old.lastUpdateTime >= 1200000"], [[insert]])
        commands.append(insert)
        trigger_function = self.__createTriggerFunction("event_newUpdate", commands, 
                                                        {"checking": "RECORD", "now": "RECORD"})
        trigger = self.__createTrigger("event_newUpdate", "AFTER", "UPDATE OF nowPoints", 
                                       "event_player", "event_newUpdate", "ROW")
        cursor.execute(trigger_function); cursor.execute(trigger); self.connection.commit()
        
        cursor.close()
        
    def createTableForMonthlys(self) -> None:
        cursor = self.connection.cursor()
        table = self.__createTable("monthly_detail",
                                   {"id": "SMALLINT", "serverId": "SMALLINT",
                                    "name": "VARCHAR(128)", "startAt": "BIGINT", "endAt": "BIGINT"},
                                   ["serverId", "id"])
        cursor.execute(table); self.connection.commit()
        
        table = self.__createTable("monthly_player",
                                   {"serverId": "SMALLINT", "monthlyId": "SMALLINT", "uid": "BIGINT",
                                    "name": "VARCHAR(32)", "introduction": "VARCHAR(64)",
                                    "rank": "SMALLINT", "nowPoints": "INTEGER", "lastUpdateTime": "BIGINT"},
                                   ["serverId", "monthlyId", "uid"], 
                                   [["to_monthly", "serverId, monthlyId", "monthly_detail", "serverId, id"]])
        index = self.__createIndex("monthly_players_nowPoints_desc", "monthly_player", 
                                   ["serverId", "monthlyId", "nowPoints DESC NULLS LAST"])
        cursor.execute(table); cursor.execute(index); self.connection.commit()
        
        table = self.__createTable("monthly_points",
                                   {"serverId": "SMALLINT", "monthlyId": "SMALLINT", "uid": "BIGINT",
                                    "value": "INTEGER", "time": "BIGINT"}, ["serverId", "monthlyId", "uid", "value"],
                                   [["to_player", "serverId, monthlyId, uid", 
                                     "monthly_player", "serverId, monthlyId, uid"]])
        cursor.execute(table); self.connection.commit()
        
        update = self.__update("monthly_player", {"nowPoints": "new.value", "lastUpdateTime": "new.time"}, 
                               "serverId = new.serverId AND monthlyId = new.monthlyId AND uid = new.uid AND nowPoints < new.value")
        trigger_function = self.__createTriggerFunction("monthly_newPoints", [update])
        trigger = self.__createTrigger("monthly_newPoints", "AFTER", "INSERT", 
                                       "monthly_points", "monthly_newPoints", "ROW")
        cursor.execute(trigger_function); cursor.execute(trigger); self.connection.commit()
        
        cursor.close()
        
    # %% inserting data
    def __insertValueProcess(self, values: list[list]) -> list[list[str]]:
        return [["\'" + var.replace("\'", "\'\'").replace("\"", "\"\"") + "\'" 
                 if isinstance(var, str) else (str(var).lower() if isinstance(var, bool) 
                                               else ("NULL" if var == None else str(var)))
                 for var in value] for value in values]
        
    def __doInsert(self, insert: str) -> None:
        cursor = self.connection.cursor(); cursor.execute(insert); 
        self.connection.commit(); cursor.close(); return
        
    def insertUserSetting(self, user_id: int, server_id: Optional[int] = None, 
                          is_change_notify: Optional[bool] = None, is_CP_notify: Optional[bool] = None) -> None:
        conflict_actions = []
        if server_id == None: server_id = 2 
        else: conflict_actions.append("serverId = EXCLUDED.serverId")
        if is_change_notify == None: is_change_notify = False
        else: conflict_actions.append("isChangeNotify = EXCLUDED.isChangeNotify")
        if is_CP_notify == None: is_CP_notify = False
        else: conflict_actions.append("isCPNotify = EXCLUDED.isCPNotify")
        
        values = self.__insertValueProcess([[user_id, server_id, is_change_notify, is_CP_notify]])
        insert = self.__insert("user_setting", ["id", "serverId", "isChangeNotify", "isCPNotify"], values, ["id"], 
                               "NOTHING" if conflict_actions == [] else "UPDATE SET " + ", ".join(conflict_actions))
        self.__doInsert(insert); return
        
    def insertUserUid(self, user_id: int, server_id: int, uid: int) -> None:
        values = self.__insertValueProcess([[user_id, server_id, uid]])
        insert = self.__insert("user_uid", ["id", "serverId", "uid"], values, 
                               ["serverId", "id"], "UPDATE SET uid = EXCLUDED.uid")
        self.__doInsert(insert); return
        
    def insertUserTarger(self, user_id: int, server_id: int, event_id: int, target_points: int) -> None:
        values = self.__insertValueProcess([[user_id, server_id, event_id, target_points]])
        insert = self.__insert("user_uid", ["id", "serverId", "eventId", "targetPoints"], values, 
                               ["serverId", "eventId", "id"], "UPDATE SET targetPoints = EXCLUDED.targetPoints")
        self.__doInsert(insert); return
        
    def insertChannelSetting(self, channel_id: int, server_id: Optional[int] = None) -> None:
        if server_id == None: server_id = 2; conflict_action = "NOTHING"
        else: conflict_action = "UPDATE SET serverId = EXCLUDED.serverId"
        
        values = self.__insertValueProcess([[channel_id, server_id]])
        insert = self.__insert("channel_setting", ["id", "serverId"], values, ["id"], conflict_action)
        self.__doInsert(insert); return
    
    def insertEventDetail(self, server_id: int, event_id: int, event_name: str,  
                          event_type: int, event_start_at: int, event_ent_at: int) -> None:
        values = self.__insertValueProcess([[event_id, server_id, event_name, 
                                             event_type, event_start_at, event_ent_at]])
        insert = self.__insert("event_detail", ["id", "serverId", "name", "type", "startAt", "endAt"], 
                               values, ["serverId", "id"], "NOTHING")
        self.__doInsert(insert); return
        
    def insertEventPlayers(self, server_id: int, event_id: int, players: list[list], default_time: int) -> None:
        if players == []: return
        values = self.__insertValueProcess([[server_id, event_id] + player + [0, default_time] for player in players])
        insert = self.__insert("event_player", ["serverId", "eventId", "uid", "name", "introduction", "rank", 
                                "nowPoints", "lastUpdateTime"], values, ["serverId", "eventId", "uid"], 
                               "UPDATE SET name = COALESCE(EXCLUDED.name, event_player.name), "
                             + "introduction = COALESCE(EXCLUDED.introduction, event_player.introduction), "
                             + "rank = COALESCE(EXCLUDED.rank, event_player.rank);")
        self.__doInsert(insert); return
    
    def insertDefaultEventRanks(self, server_id: int, event_id: int, uids: list[int], default_time: int) -> None:
        if uids == []: return
        values = self.__insertValueProcess([[server_id, event_id, uid, default_time, -1, -1] for uid in uids])
        insert = self.__insert("event_ranks", ["serverId", "eventId", "uid", "updateTime", "fromRank", "toRank"],
                               values, ["serverId", "eventId", "uid", "updateTime"], 
                               "UPDATE SET toRank = EXCLUDED.toRank")
        self.__doInsert(insert); return
    
    def insertEventPoints(self, server_id: int, event_id: int, points: list[list]) -> None:
        if points == []: return
        values = self.__insertValueProcess([[server_id, event_id] + point for point in points])
        insert = self.__insert("event_points", ["serverId", "eventId", "uid", "value", "time"],
                               values, ["serverId", "eventId", "uid", "value"], "NOTHING")
        self.__doInsert(insert); return
    
    def insertMonthlyDetail(self, server_id: int, monthly_id: int, monthly_name: str,  
                            monthly_start_at: int, monthly_ent_at: int) -> None:
        values = self.__insertValueProcess([[monthly_id, server_id, monthly_name, monthly_start_at, monthly_ent_at]])
        insert = self.__insert("monthly_detail", ["id", "serverId", "name", "startAt", "endAt"], 
                               values, ["serverId", "id"], "NOTHING")
        self.__doInsert(insert); return
        
    def insertMonthlyPlayers(self, server_id: int, monthly_id: int, players: list[list], default_time: int) -> None:
        if players == []: return
        values = self.__insertValueProcess([[server_id, monthly_id] + player + [0, default_time] for player in players])
        insert = self.__insert("monthly_player", ["serverId", "monthlyId", "uid", "name", "introduction", "rank", 
                                "nowPoints", "lastUpdateTime"], values, ["serverId", "monthlyId", "uid"], 
                               "UPDATE SET name = EXCLUDED.name, introduction = EXCLUDED.introduction, rank = EXCLUDED.rank;")
        self.__doInsert(insert); return
    
    def insertMonthlyPoints(self, server_id: int, monthly_id: int, points: list[list]) -> None:
        if points == []: return
        values = self.__insertValueProcess([[server_id, monthly_id] + point for point in points])
        insert = self.__insert("monthly_points", ["serverId", "monthlyId", "uid", "value", "time"],
                               values, ["serverId", "monthlyId", "uid", "value"], "NOTHING")
        self.__doInsert(insert); return
    
    # %% getting data
    def __doSelect(self, select: str) -> tuple:
        cursor = self.connection.cursor(); cursor.execute(select)
        result = cursor.fetchall(); cursor.close(); return result
    
    def selectUserSetting(self, user_id: int) -> list:
        select = self.__select(["user_setting"], ["*"], f"id = {user_id}")
        result = self.__doSelect(select); return ([] if result == () else list(result)[0])
    
    def selectUserUid(self, user_id: int) -> list:
        select = self.__select(["user_uid"], ["serverId", "uid"], f"id = {user_id}")
        response = self.__doSelect(select); result = [None for _ in range(4)]
        for server_id, uid in list(response): result[server_id] = uid; return result
        
    def selectUserRecentTarget(self, user_id: int) -> list:
        select = self.__select(["user_target"], ["serverId", "eventId", "targetPoints"], f"id = {user_id}")
        response = self.__doSelect(select); result = [None for _ in range(4)]
        for server_id, event_id, target_points in list(response): result[server_id] = (target_points, event_id)
        return result
    
    def selectChannelSetting(self, channel_id: int) -> list:
        select = self.__select(["channel_setting"], ["*"], f"id = {channel_id}")
        result = self.__doSelect(select); return ([] if result == () else list(result)[0])
    
    def selectRecentEventDetail(self, server_id: int) -> list:
        select = self.__select(["event_detail"], ["*"], 
                               f"serverId = {server_id} AND startAt <= ROUND(EXTRACT(EPOCH FROM now()) + 14400)",
                               order_by = ["startAt DESC"], limit = 1)
        result = self.__doSelect(select); return ([] if result == () else list(result)[0])
    
    def selectRecentMonthlyDetail(self, server_id: int) -> list:
        select = self.__select(["monthly_detail"], ["*"], 
                               f"serverId = {server_id} AND startAt <= ROUND(EXTRACT(EPOCH FROM now()) + 14400)",
                               order_by = ["startAt DESC"], limit = 1)
        result = self.__doSelect(select); return ([] if result == () else list(result)[0])
        
    def selectEventTopPlayers(self, server_id: int, event_id: int) -> list:
        select = self.__select(["event_player"], ["*"], f"serverId = {server_id} AND eventId = {event_id}",
                               order_by = ["nowPoints DESC", "lastUpdateTime ASC"], limit = 10)
        result = self.__doSelect(select); return list(result)
        
    def selectMonthlyTopPlayers(self, server_id: int, monthly_id: int) -> list:
        select = self.__select(["monthly_player"], ["*"], f"serverId = {server_id} AND monthlyId = {monthly_id}",
                               order_by = ["nowPoints DESC", "lastUpdateTime ASC"], limit = 10)
        result = self.__doSelect(select); return list(result)
        
    def selectEventPlayerPointsAtTime(self, server_id: int, event_id: int, uid: int, 
                                      before: Optional[int] = None, after: Optional[int] = None, 
                                      limit: Optional[int] = None, with_time: Optional[bool] = False) -> list[list[int]]:
        conditions = f"serverId = {server_id} AND eventID = {event_id} AND uid = {uid}"
        if before != None: conditions += f" AND time < {before}"
        if after != None: conditions += f" AND time >= {after}"
        select = self.__select(["event_points"], (["time", "value"] if with_time else ["value"]), 
                               conditions, order_by = ["value DESC"], limit = limit)
        result = self.__doSelect(select); return ([[0]] if result == () else list(result))
        
    def selectEventPlayerPointsNumAtTime(self, server_id: int, event_id: int, uid: int, 
                                         before: Optional[int] = None, after: Optional[int] = None) -> int:
        conditions = f"serverId = {server_id} AND eventID = {event_id} AND uid = {uid}"
        if before != None: conditions += f" AND time < {before}"
        if after != None: conditions += f" AND time >= {after}"
        select = self.__select(["event_points"], ["COUNT(uid)"], conditions)
        result = self.__doSelect(select); return result[0][0]
        
    def selectEventPlayerPointsNumHourly(self, server_id: int, event_id: int, uid: int, start_at: int) -> list[int]:
        select = self.__select(["event_points"], ["COUNT(uid)", f"((time - {start_at}) / 3600)"], 
                               f"serverId = {server_id} AND eventID = {event_id} AND uid = {uid}", 
                               group_by = f"((time - {start_at}) / 3600)", order_by = [f"((time - {start_at}) / 3600)"])
        response = self.__doSelect(select); result = [0 for _ in range(response[-1][1] + 2)]
        for num, index in list(response): result[index] = num
        return list(result)
        
    def selectEventPlayerIntervals(self, server_id: int, event_id: int, uid: int) -> list[list[int]]:
        select = self.__select(["event_intervals"], ["startTime", "endTime", "valueDelta"], 
                               f"serverId = {server_id} AND eventID = {event_id} AND uid = {uid}")
        result = self.__doSelect(select); return ([] if result == () else list(result))
        
    def selectEventPlayerRanks(self, server_id: int, event_id: int, uid: int) -> list[list[int]]:
        select = self.__select(["event_ranks"], ["updateTime", "fromRank", "toRank"], 
                               f"serverId = {server_id} AND eventID = {event_id} AND uid = {uid}")
        result = self.__doSelect(select); return ([] if result == () else list(result))
    
    def selectEventPlayerUpsTime(self, server_id: int, event_id: int, uid: int, 
                                 limit: Optional[int] = None) -> list[int]:
        select = self.__select(["event_ranks"], ["updateTime"], 
                               f"serverId = {server_id} AND eventID = {event_id} AND uid = {uid}"
                             + f" AND (fromRank < 0 OR fromRank > 10) AND (0 <= toRank AND toRank <= 10)", 
                               order_by = ["updateTime DESC"], limit = limit)
        result = self.__doSelect(select); return [value[0] for value in list(result)]
        
    def selectEventPlayerDownsTime(self, server_id: int, event_id: int, uid: int, 
                                   limit: Optional[int] = None) -> list[int]:
        select = self.__select(["event_ranks"], ["updateTime"], 
                               f"serverId = {server_id} AND eventID = {event_id} AND uid = {uid}"
                             + f" AND (0 < fromRank AND fromRank <= 10) AND (toRank < 0 OR toRank > 10)", 
                               order_by = ["updateTime DESC"], limit = limit)
        result = self.__doSelect(select); return [value[0] for value in list(result)]
