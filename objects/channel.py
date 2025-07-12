from helpers.db_pg import Database

class Channel():
    def __init__(self, channel_status: list):
        self.id: int = channel_status[0]
        self.server_id: int = channel_status[1]
        self.is_change_nofity: bool = bool(channel_status[2])
        self.is_CP_nofity: bool = bool(channel_status[3])

def getChannelStatus(channel_id: int, database: Database) -> Channel:
    channel_status = database.getChannelsStatus([channel_id])
    if channel_status == (): 
        database.insertChannelStatus(channel_id)
        return Channel([channel_id, 2, False, False])
    else: return Channel(channel_status[0])
