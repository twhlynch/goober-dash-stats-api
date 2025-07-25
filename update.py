# update.py
# goober-dash-stats-api
# author(s): 
#   .index
#   Tank8k

import os
import sys
import json
import time
import requests
import websocket

# utils
def write_json(name: str, data):
    if type(data) == "str":
        data = json.loads(data)

    with open(f"v1/{name}.json", "w") as f:
        json.dump(data, f)

    print(f"Updated {name}")

current_cid = 0
def cid():
    global current_cid
    current_cid = current_cid + 1
    return str(current_cid)

# config
base_uri = "gooberdash-api.winterpixel.io"
rest_url = f"https://{base_uri}/v2/"

# token
access_token = None

def get_token():
    email = None
    password = None

    if os.path.isfile(".auth"):
        with open(".auth", "r") as f:
            email, password = f.readlines()
            email = email.strip()
            password = password.strip()
    elif len(sys.argv) > 2:
        email = sys.argv[1]
        password = sys.argv[2]

    if not email or not password:
        print("Token not refreshed")
        sys.exit(1)

    data = {
        "email": email,
        "password": password,
        "vars": { "client_version": "99999" }
    }
    auth_headers = { "authorization": "Basic OTAyaXViZGFmOWgyZTlocXBldzBmYjlhZWIzOTo=" }
    response = requests.post(
        f"{rest_url}account/authenticate/email?create=false",
        data=json.dumps(data),
        headers=auth_headers
    )
    global access_token
    access_token = json.loads(response.content)["token"]
    print("Token refreshed")

get_token()

# config
ws_url = f"wss://{base_uri}/ws?lang=en&status=true&token={access_token}"

# connection
ws = None
def init_ws():
    global ws
    ws = websocket.create_connection(ws_url)
init_ws()
headers = { "authorization": f"Bearer {access_token}" }

def get_config():
    player_fetch_data = {"rpc": {"id": "player_fetch_data", "payload": "{}"}}

    init_ws()
    ws.send(json.dumps(player_fetch_data).encode())
    _, msg = ws.recv(), ws.recv()
    ws.close()
    response = json.loads(json.loads(msg)["rpc"]["payload"])

    write_json("server_config", response["data"])
    return response["data"]
server_config = get_config()

user_ids = []
if os.path.isfile("v1/user_ids.json"):
    with open("v1/user_ids.json", "r") as f:
        user_ids = json.load(f)

blacklist = []
if os.path.isfile("v1/blacklist.json"):
    with open("v1/blacklist.json", "r") as f:
        blacklist = json.load(f)

user_ids = [id for id in user_ids if id not in blacklist]

def get_user(user_id: str = None, user_name: str = None):
    query_url = f"{rest_url}/user"
    if user_id != None:
        query_url += f"?ids={user_id}"
    elif user_name != None:
        query_url += f"?usernames={user_name}"

    response = requests.get(query_url, headers=headers)
    return response.json()

# season leaderboard
def current_season():
    timestamp = time.time()
    duration, start_number, start_time = [], [], []
    seasons = server_config["metadata"]["seasons"]["season_templates"]

    for season in seasons:
        duration.append(season["duration"])
        start_number.append(season["start_number"])
        start_time.append(season["start_time"])

    index = 0
    while index < len(start_time) and start_time[index] <= timestamp:
        index += 1

    accumulate_start_time = start_time[index - 1]
    count = 0
    while accumulate_start_time <= timestamp:
        accumulate_start_time += duration[index - 1]
        count += 1

    return start_number[index - 1] + count - 1

def get_season_leaderboard(season: int, leaderboard_id: str, limit: int, owner_ids: str, cursor: str = ""):
    query_url = f"{rest_url}leaderboard/"
    query_url += f"{leaderboard_id}.{season}"
    query_url += f"?limit={limit}"
    query_url += f"&owner_ids={owner_ids}"
    query_url += f"&cursor={cursor}" if cursor != "" else ""

    response = requests.get(query_url, headers=headers)
    return json.loads(response.content)

# time trials leaderboard
def get_levels():
    levels_query = {
        "cid": cid(),
        "rpc": {"id": "levels_query_curated", "payload": "{}"},
    }

    init_ws()
    ws.send(json.dumps(levels_query).encode())
    _, msg = ws.recv(), ws.recv()
    ws.close()
    response = json.loads(json.loads(msg)["rpc"]["payload"])

    return response["levels"]

def get_level_leaderboard(level_id: str):
    payload = { "level_id": level_id, "limit": 100 }
    query_leaderboard = {
        "cid": cid(),
        "rpc": {
            "id": "time_trial_query_leaderboard",
            "payload": json.dumps(payload),
        },
    }

    init_ws()
    ws.send(json.dumps(query_leaderboard).encode())
    _, msg = ws.recv(), ws.recv()
    ws.close()
    response = json.loads(json.loads(msg)["rpc"]["payload"])

    return response["records"]

def get_user_stats(user_id: str):
    payload = { "user_id": user_id }
    levels_query = {
        "cid": cid(),
        "rpc": {
            "id": "query_player_profile",
            "payload": json.dumps(payload)
        },
    }

    init_ws()
    ws.send(json.dumps(levels_query).encode())
    _, msg = ws.recv(), ws.recv()
    ws.close()
    response = json.loads(json.loads(msg).get("rpc", {}).get("payload", '{}'))

    return response

def main():
    global user_ids

    # levels
    levels = get_levels()
    write_json("levels", levels)

    levels_leaderboard = []

    for level in levels:
        author_id = level["author_id"]
        author_name = level["author_name"]

        found = False
        for item in levels_leaderboard:
            if item["id"] == author_id:
                item["levels"] += 1
                found = True
                break

        if not found:
            levels_leaderboard.append({
                "id": author_id,
                "username": author_name,
                "levels": 1
            })

        if author_id not in user_ids:
            user_ids.append(author_id)

    levels_leaderboard = sorted(levels_leaderboard, key=lambda x: x["levels"], reverse=True)[:500]
    write_json("levels_leaderboard", levels_leaderboard)

    # race levels
    race_levels = [level for level in levels if level["game_mode"] == "Race"]
    write_json("race_levels", race_levels)

    # leaderboards
    race_leaderboards = []
    for i, level in enumerate(race_levels):
        leaderboard = get_level_leaderboard(level["id"])
        race_leaderboards.append({
            "id": level["id"],
            "name": level["name"],
            "leaderboard": leaderboard,
        })
        print(f"Leaderboard: {i + 1} / {len(race_levels)}")
    write_json("race_leaderboards", race_leaderboards)

    # player records leaderboards
    records_leaderboard = []
    for level in race_leaderboards:
        leaderboard = level["leaderboard"]
        current = 0
        best_time = None
        while current < len(leaderboard):
            record = leaderboard[current]
            current = current + 1
            if record["owner_id"] in blacklist:
                continue
            record_time = record["score"]
            if best_time is not None and record_time != best_time:
                break
            best_time = record_time

            record_holder_id = record["owner_id"]
            record_holder_username = record["username"]["value"]

            found = False
            for record in records_leaderboard:
                if record["id"] == record_holder_id:
                    record["records"] += 1
                    found = True
                    break
            if not found:
                records_leaderboard.append({
                    "id": record_holder_id,
                    "username": record_holder_username,
                    "records": 1,
                })

            if record_holder_id not in user_ids:
                user_ids.append(record_holder_id)
    records_leaderboard.sort(key=lambda x: x["records"], reverse=True)
    write_json("records_leaderboard", records_leaderboard)

    # season leaderboards
    season = current_season()
    season_leaderboard = get_season_leaderboard(season, "global", 100, "00000000-0000-0000-0000-000000000001")
    write_json(f"season_leaderboard", season_leaderboard)
    for record in season_leaderboard["records"]:
        owner_id = record["owner_id"]
        if owner_id not in user_ids and owner_id not in blacklist:
            user_ids.append(owner_id)

    # user ids
    user_ids = [id for id in user_ids if id not in blacklist] # redundant
    write_json("user_ids", user_ids)

    # users
    users = []
    for i, id in enumerate(user_ids):
        user_stats = get_user_stats(id)
        if user_stats != {}:
            user_stats["id"] = id
            users.append(user_stats)
        print(f"User: {i + 1} / {len(user_ids)}")
    write_json("users", users)

    # stats leaderboards
    wins_leaderboard = []
    winstreak_leaderboard = []
    games_leaderboard = []
    deaths_leaderboard = []
    winrate_leaderboard = []

    for user in users:
        wins = user["stats"]["GamesWon"] if "GamesWon" in user["stats"] else 0
        winstreak = user["stats"]["Winstreak"] if "Winstreak" in user["stats"] else 0
        games = user["stats"]["GamesPlayed"] if "GamesPlayed" in user["stats"] else 0
        deaths = user["stats"]["Deaths"] if "Deaths" in user["stats"] else 0
        winrate = wins / games if games > 100 else 0

        if wins > 0:
            wins_leaderboard.append({
                "id": user["id"],
                "username": user["display_name"],
                "wins": wins,
            })
        if winstreak > 0:
            winstreak_leaderboard.append({
                "id": user["id"],
                "username": user["display_name"],
                "winstreak": winstreak,
            })
        if games > 0:
            games_leaderboard.append({
                "id": user["id"],
                "username": user["display_name"],
                "games": games,
            })
        if deaths > 0:
            deaths_leaderboard.append({
                "id": user["id"],
                "username": user["display_name"],
                "deaths": deaths,
            })
        if winrate > 0:
            winrate_leaderboard.append({
                "id": user["id"],
                "username": user["display_name"],
                "winrate": winrate,
            })

    wins_leaderboard = sorted(wins_leaderboard, key=lambda x: x["wins"], reverse=True)[:500]
    winstreak_leaderboard = sorted(winstreak_leaderboard, key=lambda x: x["winstreak"], reverse=True)[:500]
    games_leaderboard = sorted(games_leaderboard, key=lambda x: x["games"], reverse=True)[:500]
    deaths_leaderboard = sorted(deaths_leaderboard, key=lambda x: x["deaths"], reverse=True)[:500]
    winrate_leaderboard = sorted(winrate_leaderboard, key=lambda x: x["winrate"], reverse=True)[:500]

    write_json("wins_leaderboard", wins_leaderboard)
    write_json("winstreak_leaderboard", winstreak_leaderboard)
    write_json("games_leaderboard", games_leaderboard)
    write_json("deaths_leaderboard", deaths_leaderboard)
    write_json("winrate_leaderboard", winrate_leaderboard)

if __name__ == "__main__":
    main()