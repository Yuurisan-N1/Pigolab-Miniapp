import os
import sys
import json
import random
import asyncio
import signal
import aiohttp
from urllib.parse import parse_qs, unquote
from utils.banner import show_banner

MY_PROJECT = "PigoLab Miniapp"
BASE_URL = "https://app.pigolab.com/api"
REF_CODE = "ref_6004380466"

RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"

HEADERS_BASE = {
    "accept": "application/json, text/plain, */*",
    "content-type": "application/json",
    "origin": "https://app.pigolab.com",
    "referer": "https://app.pigolab.com/",
    "user-agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36",
}

TASK_DWELL = 9

PENDING_GAPS = {}


def log_green(msg):
    print(f"{GREEN}{BOLD}{msg}{RESET}", flush=True)


def log_yellow(msg):
    print(f"{YELLOW}{BOLD}{msg}{RESET}", flush=True)


def log_red(msg):
    print(f"{RED}{BOLD}{msg}{RESET}", flush=True)


def signal_handler(sig, frame):
    print(flush=True)
    log_red("Script stopped by user")
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def clean_text(value, fallback):
    if value is None:
        return str(fallback)
    text = str(value)
    for symbol in "[]|#!@$%^&*()-+=~`,:;'\"<>?/\\":
        text = text.replace(symbol, " ")
    text = "".join(char for char in text if ord(char) < 128)
    text = " ".join(text.split())
    return text if text else str(fallback)


def shorten(value, fallback, limit):
    text = clean_text(value, fallback)
    if len(text) <= limit:
        return text
    cut = text[: limit + 1]
    space = cut.rfind(" ")
    return cut[:space].rstrip() if space > 0 else text[:limit].rstrip()


def format_amount(value):
    try:
        number = float(value)
    except Exception:
        return "0"
    if number != number or number == 0:
        return "0"
    text = f"{number:.4f}" if abs(number) >= 1 else f"{number:.8f}"
    text = text.rstrip("0").rstrip(".")
    return text or "0"


def format_duration(seconds):
    total = int(max(seconds, 0))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def display_name(account):
    for value in (account.get("username"), account.get("firstName")):
        name = clean_text(value, "")
        if name:
            return name
    return "Unknown"


def plural(count, word):
    return word if int(count) == 1 else f"{word}s"


def load_config():
    defaults = {"settings": {"sleep_seconds": 3600}}
    if not os.path.exists("config.json"):
        return defaults
    try:
        with open("config.json") as handle:
            loaded = json.load(handle)
    except Exception:
        return defaults
    settings = loaded.get("settings")
    if not isinstance(settings, dict):
        return defaults
    merged = dict(defaults["settings"])
    merged.update(settings)
    return {"settings": merged}


def load_lines(filename, required):
    if not os.path.exists(filename):
        if required:
            log_red(f"File {clean_text(filename, 'data.txt')} was not found")
            sys.exit(1)
        return []
    lines = [line.strip() for line in open(filename).readlines() if line.strip()]
    if required and not lines:
        log_red("File data.txt is empty and holds no initData string")
        sys.exit(1)
    return lines


def parse_init_data(line):
    value = line.strip()
    if "tgWebAppData=" in value:
        value = value.split("tgWebAppData=", 1)[1]
        value = value.split("&tgWebAppVersion")[0]
        value = value.split("&tgWebAppPlatform")[0]
        value = unquote(value)
    fields = parse_qs(value, keep_blank_values=True)
    raw_user = (fields.get("user") or [""])[0]
    if not raw_user:
        return None
    try:
        profile = json.loads(raw_user)
    except Exception:
        try:
            profile = json.loads(unquote(raw_user))
        except Exception:
            return None
    if not isinstance(profile, dict) or not profile.get("id"):
        return None
    return {
        "initData": value,
        "id": str(profile.get("id")),
        "username": str(profile.get("username") or ""),
        "firstName": str(profile.get("first_name") or ""),
        "startParam": str((fields.get("start_param") or [""])[0] or ""),
        "plab": 0.0,
        "usdt": 0.0,
        "spins": 0,
        "rank": 0,
        "mining": {},
        "gap": 0,
    }


def referrer_code_of(account):
    value = clean_text(account.get("startParam") or REF_CODE, "")
    return value.replace(" ", "") or str(REF_CODE)


def device_line(telegram_id):
    seed = int("".join(char for char in str(telegram_id) if char.isdigit()) or 0)
    engine = random.Random(seed)
    width = engine.choice([360, 384, 392, 412, 432])
    height = engine.choice([640, 740, 780, 800, 915])
    depth = engine.choice([24, 30])
    ratio = engine.choice(["1", "1.5", "2", "2.625", "3"])
    platform = engine.choice(["Linux aarch64", "Linux armv8l"])
    cores = engine.choice([4, 6, 8])
    memory = engine.choice([4, 6, 8])
    touch = engine.choice([5, 10])
    return "|".join([
        str(width), str(height), str(depth), ratio, "Asia/Jakarta", "en-US",
        platform, str(cores), str(memory), str(touch),
    ])


def normalize_proxy(proxy_line):
    if not proxy_line:
        return None
    value = proxy_line.strip()
    if "://" in value:
        return value
    parts = value.split(":")
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    if len(parts) == 3:
        host, port, user = parts
        return f"http://{user}@{host}:{port}"
    return f"http://{value}"


def mask_proxy(proxy_url):
    try:
        value = proxy_url.split("://")[-1]
        after_at = value.split("@")[-1]
        host_part = after_at.split(":")[0]
        port_part = after_at.split(":")[1] if ":" in after_at else ""
        octets = host_part.split(".")
        if len(octets) == 4:
            masked_host = f"{octets[0]}*****{octets[3]}"
        elif len(host_part) > 4:
            masked_host = f"{host_part[:2]}*****{host_part[-2:]}"
        else:
            masked_host = "***"
        suffix = f":{port_part}" if port_part else ""
        return f"http://user:pass@{masked_host}{suffix}"
    except Exception:
        return "http://user:pass@***:***"


def busy_error(status, payload):
    if status in (429, 500, 502, 503, 504):
        return True
    message = ""
    if isinstance(payload, dict):
        for key in ("message", "error"):
            if payload.get(key):
                message = str(payload[key])
                break
    return "busy" in message.lower() or "timeout" in message.lower()


def error_message(payload):
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return ""


def number_float(mapping, key, fallback=0.0):
    if not isinstance(mapping, dict):
        return fallback
    value = mapping.get(key)
    if value is None or value == "":
        return fallback
    try:
        return float(value)
    except Exception:
        return fallback


def number_of(mapping, key, fallback=0):
    return int(number_float(mapping, key, fallback))


def text_of(mapping, key, fallback):
    if not isinstance(mapping, dict):
        return str(fallback)
    value = mapping.get(key)
    if value is None:
        return str(fallback)
    return str(value)


async def countdown(seconds, label):
    left = int(max(seconds, 0))
    if left < 1:
        return
    text = clean_text(label, "Next cycle")
    while left > 0:
        print(
            f"\r{YELLOW}{BOLD}{text} {format_duration(left)}{RESET}",
            end="",
            flush=True,
        )
        await asyncio.sleep(1)
        left -= 1
    print(f"\r{' ' * 70}\r", end="", flush=True)


def device_of(account):
    device = account.get("device")
    if device:
        return device
    account["device"] = device_line(account["id"])
    return account["device"]


async def api_call(session, account, path, body=None, proxy=None, method="POST"):
    url = f"{BASE_URL}{path}"
    seed = account.get("seed")
    if seed is None:
        seed = account.get("startParam") or REF_CODE
        account["seed"] = seed
    headers = dict(HEADERS_BASE)
    headers["x-init-data"] = account["initData"]
    headers["x-device"] = device_of(account)
    payload = None
    if method == "POST":
        payload = {"startParam": seed}
        if body:
            payload.update(body)
    last_status = 0
    last_payload = None
    for attempt in range(1, 4):
        try:
            request = session.request(
                method,
                url,
                headers=headers,
                json=payload,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=40),
            )
            async with request as response:
                last_status = response.status
                text = await response.text()
                try:
                    last_payload = json.loads(text)
                except Exception:
                    last_payload = None
                if response.status < 400 or not busy_error(response.status, last_payload):
                    return last_status, last_payload
        except Exception:
            last_status = 0
            last_payload = None
        if attempt < 3:
            await asyncio.sleep(4 * attempt)
    return last_status, last_payload


def store_user(account, payload):
    user = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user, dict):
        user = payload if isinstance(payload, dict) and payload.get("id") else None
    if not isinstance(user, dict):
        return {}
    account["plab"] = number_float(user, "plab")
    account["usdt"] = number_float(user, "usdt")
    account["spins"] = number_of(user, "spins")
    mining = user.get("mining")
    if isinstance(mining, dict):
        account["mining"] = mining
        account["gap"] = rig_gap(mining)
    return user


def rig_gap(mining):
    if not isinstance(mining, dict) or not mining.get("active"):
        return 0
    ends = number_float(mining, "endsAt")
    now = number_float(mining, "serverNow")
    if ends <= 0 or now <= 0:
        return 0
    return max(int((ends - now) / 1000) + 2, 0)


async def run_session(session, account, proxy):
    status, payload = await api_call(session, account, "/session", None, proxy)
    if status == 200 and isinstance(payload, dict) and payload.get("user"):
        store_user(account, payload)
        return payload.get("config") if isinstance(payload.get("config"), dict) else {}
    return {}


async def run_tasks(session, account, proxy):
    status, payload = await api_call(session, account, "/tasks", None, proxy, "GET")
    if status != 200 or not isinstance(payload, dict) or not payload.get("tasks"):
        log_yellow("The task list was not returned by the server")
        return 0
    earned = 0.0
    done = 0
    joined = 0
    for task in payload.get("tasks"):
        if not isinstance(task, dict):
            continue
        title = shorten(task.get("title"), "task", 20)
        if task.get("status") == "claimed":
            continue
        kind = text_of(task, "type", "")
        if kind == "referral":
            done += 1
            continue
        status, started = await api_call(session, account, "/tasks/start", {"id": task.get("id")}, proxy)
        if status != 200:
            log_yellow(f"Task {clean_text(title, 'task')} could not be started")
            continue
        if kind == "telegram":
            status, claimed = await api_call(
                session, account, "/tasks/claim", {"id": task.get("id")}, proxy
            )
            if status == 200 and isinstance(claimed, dict) and claimed.get("status") == "claimed":
                earned += number_float(claimed, "reward")
                store_user(account, claimed)
                log_green(
                    f"Task {clean_text(title, 'task')} verified "
                    f"{clean_text(format_amount(claimed.get('reward')), 0)} PIGO"
                )
            else:
                joined += 1
                log_yellow(f"Task {clean_text(title, 'task')} waits for a real channel join")
            continue
        await countdown(TASK_DWELL, "Next task in")
        status, claimed = await api_call(
            session, account, "/tasks/claim", {"id": task.get("id")}, proxy
        )
        if status == 200 and isinstance(claimed, dict) and claimed.get("status") == "claimed":
            reward = number_float(claimed, "reward")
            earned += reward
            store_user(account, claimed)
            log_green(
                f"Task {clean_text(title, 'task')} verified "
                f"{clean_text(format_amount(reward), 0)} PIGO"
            )
        else:
            log_yellow(f"Task {clean_text(title, 'task')} was refused by the server")
    if done:
        log_yellow(f"{clean_text(done, 0)} {clean_text(plural(done, 'task'), 'tasks')} still needs real friends")
    if joined:
        log_yellow(f"{clean_text(joined, 0)} {clean_text(plural(joined, 'task'), 'tasks')} need a real channel join")
    return earned


async def run_mining(session, account, proxy):
    mining = account.get("mining") if isinstance(account.get("mining"), dict) else {}
    if mining.get("active"):
        status, payload = await api_call(session, account, "/mining/claim", {}, proxy)
        if status == 200 and isinstance(payload, dict) and payload.get("plab") is not None:
            mined = number_float(payload, "mined")
            store_user(account, payload)
            log_green(f"Mining cycle credited {clean_text(format_amount(mined), 0)} PIGO")
        else:
            left = account.get("gap", 0)
            log_yellow(f"The mining cycle is still running and returns in {format_duration(left)}")
            return 0.0
    status, payload = await api_call(session, account, "/mining/start", {}, proxy)
    if status == 200 and isinstance(payload, dict) and payload.get("mining"):
        account["mining"] = payload["mining"]
        account["gap"] = rig_gap(payload["mining"])
        log_green(
            "Mining rig started and the next claim returns in "
            f"{format_duration(account['gap'])}"
        )
        return 0.0
    log_yellow("The mining rig was refused with no reason")
    return 0.0


async def run_leaderboard(session, account, proxy):
    status, payload = await api_call(session, account, "/leaderboard", None, proxy, "GET")
    if status != 200 or not isinstance(payload, dict) or not payload.get("top"):
        log_yellow("The leaderboard was not returned by the server")
        return
    for position, entry in enumerate(payload["top"], 1):
        if isinstance(entry, dict) and str(entry.get("id")) == account["id"]:
            account["rank"] = position
            log_green(f"Leaderboard position {clean_text(position, 0)} of {clean_text(len(payload['top']), 0)} miners")
            return
    log_yellow("This account is not ranked on the leaderboard yet")


async def process_account(line, proxy, index):
    account = parse_init_data(line)
    if not account:
        log_red(f"Credential line {clean_text(index, 1)} is not valid initData")
        return

    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        config = await run_session(session, account, proxy)
        if not config:
            log_red(f"Sign in failed for account number {clean_text(index, 1)}")
            return

        name = display_name(account)
        log_green(
            f"Signed in {clean_text(shorten(name, 'account', 18), 'account')} with "
            f"{clean_text(format_amount(account['plab']), 0)} PIGO and "
            f"{clean_text(format_amount(account['usdt']), 0)} USDT"
        )

        await run_tasks(session, account, proxy)
        await run_mining(session, account, proxy)
        await run_leaderboard(session, account, proxy)

        if account.get("gap", 0) > 0:
            PENDING_GAPS[index] = account["gap"]

        log_green(
            f"Cycle closed with {clean_text(format_amount(account['plab']), 0)} PIGO and "
            f"{clean_text(format_amount(account['usdt']), 0)} USDT"
        )


async def main_async(accounts, proxies, sleep_secs):
    cycle = 1
    while True:
        log_yellow(f"Starting automation cycle number {clean_text(cycle, 0)}")

        for index, line in enumerate(accounts):
            if index > 0:
                print()
            proxy_line = proxies[index % len(proxies)] if proxies else None
            proxy_url = normalize_proxy(proxy_line) if proxy_line else None
            if proxy_url:
                log_yellow(f"Using proxy {mask_proxy(proxy_url)}")
            await process_account(line, proxy_url, index + 1)

        log_yellow(f"Automation cycle number {clean_text(cycle, 0)} is complete")
        cycle += 1
        wait_secs = int(sleep_secs)
        gaps = [value for value in PENDING_GAPS.values() if value > 0]
        PENDING_GAPS.clear()
        if gaps:
            wait_secs = min(int(min(gaps)) + 2, wait_secs)
        await countdown(wait_secs, "Next cycle starts in")
        show_banner(MY_PROJECT)


def main():
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass

    show_banner(MY_PROJECT)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    settings = load_config().get("settings", {})
    accounts = load_lines("data.txt", True)
    proxies = load_lines("proxy.txt", False)
    try:
        asyncio.run(main_async(accounts, proxies, settings["sleep_seconds"]))
    except KeyboardInterrupt:
        print(flush=True)
        log_red("Script stopped by user")
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)


if __name__ == "__main__":
    main()
