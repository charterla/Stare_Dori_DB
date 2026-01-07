from typing import Union

from utils.db_pg import Database

class User:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.id: int = data[0]
        
        self.server_id: int = data[1]
        self.is_change_nofity: bool = data[2]
        self.is_CP_nofity: bool = data[3]
        
        self.uid: list[Union[int, None]] = data[4]
        self.recent_target_point: list[Union[tuple[int, int], None]] = data[5]
        
def getUser(database: Database, user_id: int) -> User:
    # Collecting user basic setting and Checking if user is in the database
    user_data: list = database.selectUserSetting(user_id)
    if user_data == []: 
        database.insertUserSetting(user_id)
        return User([user_id, 2, False, False, [None for _ in range(4)], [None for _ in range(4)]])
    
    # Collecting user additional info and Creating object
    user_data.append(database.selectUserUid(user_id))
    user_data.append(database.selectUserRecentTarget(user_id))
    return User(user_data)

class Channel:
    def __init__(self, data: list):
        # Initializing object with data provided
        self.id: int = data[0]
        self.server_id: int = data[1]
        
def getChannel(database: Database, channel_id: int) -> Channel:
    # Creating object and Confirming the existance in database
    channel_data: list = database.selectChannelSetting(channel_id)
    if channel_data == []: database.insertChannelSetting(channel_id); return Channel([channel_id, 2])
    else: return Channel(channel_data)