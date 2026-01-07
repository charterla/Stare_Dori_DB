import logging, json
from pathlib import Path
from datetime import datetime
from typing import Optional

from discord.utils import stream_supports_colour, _ColourFormatter

def getLogger(name: str, level: Optional[int] = None) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO if level == None else level)
    handler = logging.StreamHandler()
    if isinstance(handler, logging.StreamHandler) and stream_supports_colour(handler.stream):
        formatter = _ColourFormatter()
    else:
        dt_fmt = '%Y-%m-%d %H:%M:%S'
        formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def __jsonSerialize(vars):
    if isinstance(vars, (int, float, bool, str)): return vars
    if isinstance(vars, bytes): return vars.hex()
    if isinstance(vars, dict): return {key: __jsonSerialize(value) for key, value in vars.items()}
    if isinstance(vars, list): return [__jsonSerialize(value) for value in vars]
    try: return __jsonSerialize(vars.__dict__)
    except: return str(vars)

def logExceptionToFile(path: Path, log: str, trace: str, objects: Optional[dict] = None) -> None:
    path.parent.mkdir(parents = True, exist_ok = True)
    with path.open("a", encoding = "utf-8") as file:
        file.write("\n" + "=" * 32)
        file.write("\n" + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + ": " + log)
        file.write("\n" + "-" * 32)
        file.write("\n" + trace)
        if objects != None:
            file.write("\n" + "-" * 32)
            file.write("\n" + json.dumps(__jsonSerialize(objects), ensure_ascii = False, indent = 4))
        file.write("\n" + "=" * 32)
    return
        