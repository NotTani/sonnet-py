# cache generation tools
# Ultabear 2020

from sonnet_cfg import *
import json, random, os

from lib_db_obfuscator import db_hlapi


# LCIF system ported for blacklist loader, converted to little endian
def directBinNumber(inData,length):
    return tuple([(inData >> (8*i) & 0xff ) for i in range(length)])


# Load config from cache, or load from db if cache isint existant
def load_message_config(guild_id, ramfs):
    try:
        blacklist_cache = ramfs.read_f(f"datastore/{guild_id}.cache.db")
        blacklist_cache.seek(0)
        message_config = {}
        for i in ["word-blacklist","filetype-blacklist","word-in-word-blacklist"]:
            message_config[i] = blacklist_cache.read(int.from_bytes(blacklist_cache.read(2), "little")).decode("utf8")
            if message_config[i]:
                message_config[i] = message_config[i].split(",")
            else:
                message_config[i] = []
        for i in ["prefix","blacklist-action","starboard-emoji","starboard-enabled","starboard-count","blacklist-whitelist"]:
            message_config[i] = blacklist_cache.read(int.from_bytes(blacklist_cache.read(2), "little")).decode("utf8")
        for regex in ["regex-blacklist"]:
            prelist = []
            for i in range(int.from_bytes(blacklist_cache.read(2), "little")):
                prelist.append(blacklist_cache.read(int.from_bytes(blacklist_cache.read(2), "little")).decode("utf8"))
            message_config[regex] = prelist

        return message_config

    except FileNotFoundError:
        db = db_hlapi(guild_id)
        message_config = {}

        # Loads base db
        for i in ["word-blacklist","regex-blacklist","filetype-blacklist","prefix","blacklist-action","starboard-emoji","starboard-enabled","starboard-count","word-in-word-blacklist","blacklist-whitelist"]:
            message_config[i] = db.grab_config(i)
        db.close()

        # Loads regex
        if message_config["regex-blacklist"]:
            message_config["regex-blacklist"] = [i.split(" ")[1][1:-2] for i in json.loads(message_config["regex-blacklist"])["blacklist"]]
        else:
            message_config["regex-blacklist"] = []

        # Loads word, filetype blacklist
        for i in ["word-blacklist","filetype-blacklist","word-in-word-blacklist"]:
            if message_config[i]:
                message_config[i] = message_config[i].lower().split(",")

        # Generate various defaults
        if not message_config["prefix"]:
            message_config["prefix"] = GLOBAL_PREFIX

        if not message_config["blacklist-action"]:
            message_config["blacklist-action"] = BLACKLIST_ACTION

        if not message_config["starboard-emoji"]:
            message_config["starboard-emoji"] = STARBOARD_EMOJI

        if not message_config["starboard-enabled"]:
            message_config["starboard-enabled"] = "0"
            
        if not message_config["starboard-count"]:
            message_config["starboard-count"] = STARBOARD_COUNT

        # Generate SNOWFLAKE DBCACHE
        blacklist_cache = ramfs.create_f(f"datastore/{guild_id}.cache.db")
        # ORDER : word blacklist, filetype blacklist, prefix, blacklist-action, starboard-count, regex blacklist
        for i in ["word-blacklist","filetype-blacklist","word-in-word-blacklist"]:
            if message_config[i]:
                outdat = ",".join(message_config[i]).encode("utf8")
                blacklist_cache.write(bytes(directBinNumber(len(outdat),2))+outdat)
            else:
                blacklist_cache.write(bytes(2))

        # Add prefix, blacklist action, starboard emoji, starboard enabled
        for i in ["prefix","blacklist-action","starboard-emoji","starboard-enabled","starboard-count","blacklist-whitelist"]:
            if message_config[i]:
                outdat = message_config[i].encode("utf8")
                blacklist_cache.write(bytes(directBinNumber(len(outdat),2))+outdat)
            else:
                blacklist_cache.write(bytes(2))

        # Serialize regex blacklist
        for i in ["regex-blacklist"]:
            if message_config[i]:
                preout = b""
                for regex in message_config[i]:
                    preout += bytes(directBinNumber(len(regex.encode("utf8")),2))+regex.encode("utf8")
                blacklist_cache.write(bytes(directBinNumber(len(message_config[i]),2))+preout)
            else:
                blacklist_cache.write(bytes(2))

        return message_config


def generate_infractionid():
    try:
        num_words = os.path.getsize("datastore/wordlist.cache.db")-1
        with open("datastore/wordlist.cache.db","rb") as words:
            chunksize = int.from_bytes(words.read(1), "big")
            num_words /= chunksize
            values  = sorted([random.randint(0,(num_words-1)) for i in range(3)])
            output = ""
            for i in values:
                words.seek(i*chunksize+1)
                preout = (words.read(int.from_bytes(words.read(1), "big"))).decode("utf8")
                output += preout[0].upper()+preout[1:]
        return output

    except FileNotFoundError:
        with open("common/wordlist.txt", "r") as words:
            maxval = 0
            structured_data = []
            for i in words.read().encode("utf8").split(b"\n"):
                structured_data.append(bytes([len(i)])+i)
                if len(i)+1 > maxval:
                    maxval = len(i)+1
        with open("datastore/wordlist.cache.db","wb") as structured_data_file:
            structured_data_file.write(bytes([maxval]))
            for i in structured_data:
                structured_data_file.write(i+bytes(maxval-len(i)))

        return generate_infractionid()