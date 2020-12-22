# Administration commands.
# bredo, 2020

import discord, os
from datetime import datetime
import json, gzip, io, time

from sonnet_cfg import GLOBAL_PREFIX
from lib_mdb_handler import db_handler, db_error
from lib_parsers import parse_boolean, update_log_channel
from lib_loaders import load_message_config
from lib_ramfs import ram_filesystem


async def recreate_db(message, args, client, stats, cmds):
    
    with db_handler() as db:
        db.make_new_table(f"{message.guild.id}_config",[["property", tuple, 1], ["value", str]])
        db.make_new_table(f"{message.guild.id}_infractions", [
        ["infractionID", tuple, 1],
        ["userID", str],
        ["moderatorID", str],
        ["type", str],
        ["reason", str],
        ["timestamp", int(64)]
        ])
        db.make_new_table(f"{message.guild.id}_starboard", [["messageID", tuple, 1]])
        db.make_new_table(f"{message.guild.id}_mutes", [["infractionID", tuple, 1],["userID", str],["endMute",int(64)]])
    await message.channel.send("done (unless something broke)")


async def inflog_change(message, args, client, stats, cmds):
    try:
        await update_log_channel(message, args, client, "infraction-log")
    except RuntimeError:
        return


async def joinlog_change(message, args, client, stats, cmds):
    try:
        await update_log_channel(message, args, client, "join-log")
    except RuntimeError:
        return


async def msglog_change(message, args, client, stats, cmds):
    try:
        await update_log_channel(message, args, client, "message-log")
    except RuntimeError:
        return


class gdpr_functions:

    async def delete(message, guild_id):

        with db_handler() as database:
            for i in ["_config","_infractions","_mutes","_starboard"]:
                database.delete_table(f"{guild_id}{i}")

        await message.channel.send(f"Deleted database for guild {message.guild.id}")

    async def download(message, guild_id):

        timestart = time.time()
        dbdict = {
            "config":[["property","value"]],
            "infractions":[["infractionID","userID","moderatorID","type","reason","timestamp"]],
            "mutes":[["infractionID","userID","endMute"]],
            "starboard":[["messageID"]]
            }

        with db_handler() as database:
            for i in ["config","infractions"]:
                try:
                    dbdict[i].extend(database.fetch_table(f"{guild_id}_{i}"))
                except db_error.OperationalError:
                    await message.channel.send(f"Could not grab {i}, it may not exist")

        # Convert to compressed json
        file_to_upload = io.BytesIO()
        with gzip.GzipFile(filename=f"{guild_id}.db.json.gz", mode="wb", fileobj=file_to_upload) as txt:
            txt.write(json.dumps(dbdict, indent=4).encode("utf8"))
        file_to_upload.seek(0)
        # Finalize discord file obj
        fileobj = discord.File(file_to_upload, filename="database.gz")

        await message.channel.send(f"Grabbing DB took: {round((time.time()-timestart)*100000)/100}ms", file=fileobj)


async def gdpr_database(message, args, client, stats, cmds):

    if len(args) >= 2:
        command = args[0]
        confirmation = args[1]
    elif len(args) >= 1:
        command = args[0]
        confirmation = None
    else:
        command = None

    tempramfs = ram_filesystem()
    PREFIX = load_message_config(message.guild.id, tempramfs)["prefix"]
    del tempramfs

    commands_dict = {"delete": gdpr_functions.delete, "download": gdpr_functions.download}
    if command and command in commands_dict.keys():
        if confirmation and confirmation == str(message.guild.id):
            await commands_dict[command](message, message.guild.id)
        else:
            await message.channel.send(f"Please provide the guildid to confirm\nEx: `{PREFIX}gdpr {command} {message.guild.id}`")
    else:
        message_embed = discord.Embed(title="GDPR COMMANDS", color=0xADD8E6)
        message_embed.add_field(name=f"{PREFIX}gdpr download <guildid>", value="Download the infraction and config databases of this guild", inline=False)
        message_embed.add_field(name=f"{PREFIX}gdpr delete <guildid>", value="Delete the infraction and config databases of this guild and clear cache", inline=False)
        await message.channel.send(embed=message_embed)


async def set_view_infractions(message, args, client, stats, cmds):

    if args:
        gate = parse_boolean(args[0])
    else:
        gate = False

    with db_handler() as database:
        database.add_to_table(f"{message.guild.id}_config",[["property", "member-view-infractions"],["value", int(gate)]])

    await message.channel.send(f"Member View Own Infractions set to {gate}")


async def set_prefix(message, args, client, stats, cmds):

    if args:
        prefix = args[0]
    else:
        prefix = GLOBAL_PREFIX

    with db_handler() as database:
        database.add_to_table(f"{message.guild.id}_config", [["property","prefix"],["value",prefix]])

    await message.channel.send(f"Updated prefix to `{prefix}`")


category_info = {
    'name': 'administration',
    'pretty_name': 'Administration',
    'description': 'Administration commands.'
}


commands = {
    'recreate-db': {
        'pretty_name': 'recreate-db',
        'description': 'Recreate the database if it doesn\'t exist',
        'permission':'administrator',
        'cache':'keep',
        'execute': recreate_db
    },
    'message-log': {
        'pretty_name': 'message-log',
        'description': 'Change message log for this guild.',
        'permission':'administrator',
        'cache':'keep',
        'execute': msglog_change
    },
    'infraction-log': {
        'pretty_name': 'infraction-log',
        'description': 'Change infraction log for this guild.',
        'permission':'administrator',
        'cache':'keep',
        'execute': inflog_change
    },
    'join-log': {
        'pretty_name': 'join-log',
        'description': 'Change join log for this guild.',
        'permission':'administrator',
        'cache':'keep',
        'execute': joinlog_change
    },
    'gdpr': {
        'pretty_name': 'gdpr',
        'description': 'Enforce your GDPR rights, Server Owner only',
        'permission':'owner',
        'cache':'purge',
        'execute': gdpr_database
    },
    'member-view-infractions': {
        'pretty_name': 'member-view-infractions',
        'description': 'Set whether members of the guild can view their own infraction count',
        'permission':'administrator',
        'cache':'keep',
        'execute': set_view_infractions
    },
    'set-prefix': {
        'pretty_name': 'set-prefix',
        'description': 'Set the Guild prefix',
        'permission':'administrator',
        'cache':'regenerate',
        'execute': set_prefix
    }
}
