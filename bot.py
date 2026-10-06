import os
import sys
import json
import time
import signal
import hashlib
import asyncio
import aiohttp

from urllib.parse import parse_qs, unquote

from utils.banner import show_banner

RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"

MY_PROJECT = "PigoLab Miniapp"
BASE_URL   = "https://app.pigolab.com"
REF_CODE   = "ref_6004380466"


def log_green(msg):
    print(f"{GREEN}{BOLD}{msg}{RESET}", flush=True)


def log_yellow(msg):
    print(f"{YELLOW}{BOLD}{msg}{RESET}", flush=True)


def log_red(msg):
    print(f"{RED}{BOLD}{msg}{RESET}", flush=True)


def signal_handler(sig, frame):
    print()
    log_red("Script stopped by user")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def clean_text(value, fallback="unknown"):
    text = str(value if value is not None else "").strip()
    for ch in "[]|#!@$%^&*()-":
        text = text.replace(ch, " ")
    text = " ".join(text.split())
    return text[:120] if text else fallback


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
        after_at = proxy_url.split("@")[-1]
        host_part = after_at.split(":")[0]
        port_part = after_at.split(":")[1] if ":" in after_at else ""
        octets = host_part.split(".")
        if len(octets) == 4:
            masked_host = f"{octets[0]}*****{octets[3]}"
        else:
            masked_host = "***"
        suffix = f":{port_part}" if port_part else ""
        return f"http://user:pass@{masked_host}{suffix}"
    except Exception:
        return "http://user:pass@***:***"


def countdown(seconds, label):
    start = time.time()
    while True:
        remaining = seconds - (time.time() - start)
        if remaining <= 0:
            print(f"\r{' ' * 70}\r", end="", flush=True)
            break
        h = int(remaining // 3600)
        m = int((remaining % 3600) // 60)
        s = int(remaining % 60)
        print(f"\r{YELLOW}{BOLD}{label} {h:02d}:{m:02d}:{s:02d}{RESET}", end="", flush=True)
        time.sleep(1)


def load_config():
    defaults = {"settings": {"sleep_seconds": 3600}}
    if not os.path.exists("config.json"):
        return defaults
    try:
        with open("config.json") as f:
            return json.load(f)
    except Exception:
        return defaults


def load_accounts():
    if not os.path.exists("data.txt"):
        log_red("File data.txt was not found.")
        sys.exit(1)
    lines = [l.strip() for l in open("data.txt").readlines() if l.strip()]
    if not lines:
        log_red("File data.txt is empty.")
        sys.exit(1)
    return lines


def load_proxies():
    if not os.path.exists("proxy.txt"):
        return []
    try:
        return [l.strip() for l in open("proxy.txt").readlines() if l.strip()]
    except Exception:
        return []


def get_proxy(proxies, idx):
    if not proxies:
        return None
    return proxies[idx % len(proxies)]


def parse_init_data(line):
    value = line.strip()
    if "tgWebAppData=" in value:
        value = value.split("tgWebAppData=", 1)[1]
        value = value.split("&tgWebAppVersion")[0].split("&tgWebAppPlatform")[0]
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
        "mining": {},
        "gap": 0,
    }


def device_line(account):
    digest = hashlib.sha256(account["initData"].encode("utf-8")).hexdigest()
    number = int(digest[:16], 16)
    widths = (360, 384, 392, 412, 432)
    heights = (640, 740, 780, 800, 915)
    ratios = ("1", "1.5", "2", "2.625", "3")
    platforms = ("Linux aarch64", "Linux armv8l")
    depth = (24, 30)[number % 2]
    cores = (4, 6, 8)[number % 3]
    memory = (4, 6, 8)[(number // 3) % 3]
    touch = (5, 10)[(number // 9) % 2]
    return "|".join([
        str(widths[number % len(widths)]),
        str(heights[(number // 5) % len(heights)]),
        str(depth),
        ratios[(number // 7) % len(ratios)],
        "Asia/Jakarta",
        "en-US",
        platforms[(number // 11) % len(platforms)],
        str(cores),
        str(memory),
        str(touch),
    ])


def build_headers(account):
    return {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL + "/",
        "user-agent": "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Mobile Safari/537.36",
        "x-init-data": account["initData"],
        "x-device": account["device"],
    }


def error_text(data):
    if isinstance(data, dict):
        return str(data.get("error") or data.get("message") or "")
    return ""


def mining_gap(mining):
    if not isinstance(mining, dict) or not mining.get("active"):
        return 0
    try:
        now = float(mining.get("serverNow") or 0)
        ends = float(mining.get("endsAt") or 0)
        if ends <= 0:
            ends = float(mining.get("startedAt") or 0) + float(mining.get("cycleMs") or 0)
    except Exception:
        return 0
    if now <= 0 or ends <= 0:
        return 0
    return max(int((ends - now) / 1000) + 2, 0)


async def api_call(session, account, path, body=None, proxy=None, method="POST"):
    url = f"{BASE_URL}/api/{path}"
    payload = None
    if method == "POST":
        payload = {"startParam": account.get("startParam") or REF_CODE}
        if body:
            payload.update(body)
    status = 0
    data = None
    for attempt in range(1, 4):
        try:
            async with session.request(
                method,
                url,
                headers=build_headers(account),
                json=payload,
                proxy=proxy,
                timeout=aiohttp.ClientTimeout(total=40),
            ) as response:
                status = response.status
                try:
                    data = json.loads(await response.text())
                except Exception:
                    data = None
                if status not in (429, 500, 502, 503, 504):
                    return status, data
        except Exception:
            status = 0
            data = None
        if attempt < 3:
            countdown(4 * attempt, "Retry in")
    return status, data


def store_user(account, payload):
    user = payload.get("user") if isinstance(payload, dict) else None
    if not isinstance(user, dict) and isinstance(payload, dict) and payload.get("id"):
        user = payload
    if not isinstance(user, dict):
        return {}
    try:
        account["plab"] = float(user.get("plab") or 0)
    except Exception:
        account["plab"] = 0.0
    try:
        account["usdt"] = float(user.get("usdt") or 0)
    except Exception:
        account["usdt"] = 0.0
    try:
        account["spins"] = int(float(user.get("spins") or 0))
    except Exception:
        account["spins"] = 0
    mining = user.get("mining")
    if isinstance(mining, dict):
        account["mining"] = mining
        account["gap"] = mining_gap(mining)
    return user


async def run_session(session, account, proxy):
    status, data = await api_call(session, account, "session", None, proxy)
    if status != 200 or not isinstance(data, dict) or not data.get("user"):
        return None
    store_user(account, data)
    config = data.get("config")
    return config if isinstance(config, dict) else {}


async def run_tasks(session, account, proxy):
    status, data = await api_call(session, account, "tasks", None, proxy, "GET")
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if status != 200 or not isinstance(tasks, list) or not tasks:
        log_yellow("The task list was not returned by the server")
        return
    waiting = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        name = clean_text(task.get("title") or task.get("id"), "task")
        if str(task.get("status") or "") == "claimed":
            continue
        if str(task.get("type") or "") == "referral":
            waiting += 1
            continue
        status, data = await api_call(session, account, "tasks/start", {"id": task.get("id")}, proxy)
        if status != 200:
            reason = error_text(data).lower()
            if "already" in reason:
                log_yellow(f"Task {name} was already claimed on this account")
            elif "join" in reason or "member" in reason:
                log_yellow(f"Task {name} needs a manual channel join first")
            else:
                log_red(f"Task {name} could not be started by the server")
            continue
        countdown(9, "Next task in")
        status, data = await api_call(session, account, "tasks/claim", {"id": task.get("id")}, proxy)
        if status == 200 and isinstance(data, dict) and str(data.get("status") or "") == "claimed":
            reward = data.get("reward", 0)
            store_user(account, data)
            log_green(f"Task {name} was verified and credited {reward} PIGO")
            continue
        reason = error_text(data).lower()
        if "join" in reason or "member" in reason:
            log_yellow(f"Task {name} needs a manual channel join first")
        elif "already" in reason:
            log_yellow(f"Task {name} was already claimed on this account")
        else:
            log_red(f"Task {name} could not be claimed on this run")
    if waiting:
        log_yellow(f"{waiting} referral tasks still need real invited friends")


async def run_mining(session, account, proxy):
    mining = account.get("mining") if isinstance(account.get("mining"), dict) else {}
    if mining.get("active"):
        gap = account.get("gap", 0)
        if not mining.get("complete") and gap > 0:
            h = gap // 3600
            m = (gap % 3600) // 60
            s = gap % 60
            log_yellow(f"The mining cycle is still running and returns in {h:02d}:{m:02d}:{s:02d}")
            return
        status, data = await api_call(session, account, "mining/claim", {}, proxy)
        if status == 200 and isinstance(data, dict) and data.get("mining") is not None:
            mined = data.get("mined", 0)
            store_user(account, data)
            log_green(f"Mining cycle credited {mined} PIGO to this account")
        else:
            log_red("Mining cycle claim was refused by the server")
    status, data = await api_call(session, account, "mining/start", {}, proxy)
    if status == 200 and isinstance(data, dict) and data.get("mining"):
        account["mining"] = data["mining"]
        account["gap"] = mining_gap(data["mining"])
        gap = account["gap"]
        h = gap // 3600
        m = (gap % 3600) // 60
        s = gap % 60
        log_green(f"Mining rig started and the next claim returns in {h:02d}:{m:02d}:{s:02d}")
        return
    log_red("Mining rig start was refused by the server")


async def run_spin(session, account, proxy):
    if account.get("spins", 0) < 1:
        log_yellow("Spin wheel has no spins left on this account")
        return
    status, data = await api_call(session, account, "spin", {}, proxy)
    if status == 200 and isinstance(data, dict):
        store_user(account, data)
        kind = str(data.get("kind") or "plab").lower()
        reward = data.get("reward", 0)
        if kind == "usdt":
            log_green(f"Spin wheel credited {reward} USDT to this account")
        else:
            log_green(f"Spin wheel credited {reward} PIGO to this account")
        return
    reason = error_text(data).lower()
    if "already" in reason:
        log_yellow("Spin wheel was already used on this account")
    elif "spin" in reason or "not_enough" in reason:
        log_yellow("Spin wheel has no spins left on this account")
    else:
        log_red("Spin wheel request was refused by the server")


async def run_leaderboard(session, account, proxy):
    status, data = await api_call(session, account, "leaderboard", None, proxy, "GET")
    top = data.get("top") if isinstance(data, dict) else None
    if status != 200 or not isinstance(top, list) or not top:
        log_yellow("The leaderboard was not returned by the server")
        return
    total = len(top)
    for position, entry in enumerate(top, 1):
        if isinstance(entry, dict) and str(entry.get("id")) == account["id"]:
            log_green(f"Leaderboard position {position} of {total} ranked miners")
            return
    log_yellow("This account is not ranked on the leaderboard yet")


async def process_account(line, proxy, index):
    account = parse_init_data(line)
    if not account:
        log_red(f"Credential line {index} is not valid initData")
        return 0

    account["device"] = device_line(account)
    connector = aiohttp.TCPConnector(ssl=False)

    async with aiohttp.ClientSession(connector=connector) as session:
        config = await run_session(session, account, proxy)
        if config is None:
            log_red(f"Sign in failed for credential line {index}")
            return 0

        name = clean_text(account.get("username") or account.get("firstName"), "Unknown")
        plab = account.get("plab", 0)
        usdt = account.get("usdt", 0)
        log_green(f"Signed in {name} with {plab} PIGO and {usdt} USDT")

        await run_tasks(session, account, proxy)
        await run_mining(session, account, proxy)
        await run_spin(session, account, proxy)
        await run_leaderboard(session, account, proxy)

    return account.get("gap", 0)


async def main_async(accounts, proxies, sleep_secs):
    cycle = 1
    while True:
        log_yellow(f"Starting automation cycle number {cycle}.")
        gaps = []
        for idx, line in enumerate(accounts):
            if idx > 0:
                print()
            proxy_url = normalize_proxy(get_proxy(proxies, idx))
            if proxy_url:
                log_yellow(f"Using proxy {mask_proxy(proxy_url)}.")
            gap = await process_account(line, proxy_url, idx + 1)
            if gap:
                gaps.append(gap)
        log_yellow(f"All accounts processed for cycle number {cycle}.")
        wait_secs = int(sleep_secs)
        if gaps:
            wait_secs = min(min(gaps) + 2, wait_secs)
        countdown(wait_secs, "Next cycle starts in")
        cycle += 1
        show_banner(MY_PROJECT)


def main():
    show_banner(MY_PROJECT)

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    config = load_config()
    sleep_secs = config.get("settings", {}).get("sleep_seconds", 3600)
    accounts = load_accounts()
    proxies = load_proxies()
    asyncio.run(main_async(accounts, proxies, sleep_secs))


if __name__ == "__main__":
    main()
