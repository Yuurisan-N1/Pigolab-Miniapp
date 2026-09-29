<div align="center">

<img width="100%" alt="header" src="https://capsule-render.vercel.app/api?type=waving&height=210&text=PigoLab%20Bot&fontAlign=50&fontAlignY=36&fontSize=56&desc=Rig%20Cycles%7CLink%20Tasks%7CChannel%20Joins%7CLeaderboard%7CCountdown"/>

<img alt="typing" src="https://readme-typing-svg.demolab.com?font=Inter&size=18&duration=3000&pause=650&center=true&vCenter=true&width=900&lines=Full%20daily%20cycle%20automation%20for%20the%20PigoLab%20Miniapp;The%20rig%20cycle%20is%20started%20and%20claimed%20when%20it%20finishes;Link%20tasks%20held%20for%20the%20server%20dwell%20time%20then%20claimed;Rewards%20only%20reported%20after%20the%20balance%20really%20moves;Multi%20account%20with%20proxy%20support%20and%20a%20live%20countdown%20between%20cycles"/>

<p>
  <img alt="python" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white"/>
  <img alt="platform" src="https://img.shields.io/badge/Platform-PigoLab%20Miniapp-111111"/>
  <img alt="multi-account" src="https://img.shields.io/badge/Multi--Account-Supported-111111"/>
  <img alt="proxy" src="https://img.shields.io/badge/Proxy-Supported-111111"/>
  <img alt="author" src="https://img.shields.io/badge/by-Yuurisandesu-111111"/>
</p>

<p>
  <b>PigoLab Bot</b> is a full automation bot for the PigoLab Telegram Miniapp.<br/>
  It handles the complete daily cycle: sign in with a stable per account device line, the mining rig cycle from start through claim, every link task held for the dwell time the server asks for, channel tasks reported when a real join is needed, the leaderboard position, all running automatically across multiple accounts with proxy support and a live countdown shown while the account waits for the next cycle.<br/>
  Built and distributed by <b>Yuurisandesu</b>.
</p>

</div>

---

## Table of Contents

- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Bot](#running-the-bot)
- [Features](#features)
- [File Structure](#file-structure)
- [Disclaimer](#disclaimer)

---

## Requirements

- Python `3.12+`
- Git

---

## Installation

**Clone the repository:**

```bash
git clone https://github.com/Yuurisan-N1/Pigolab-Miniapp.git
cd Pigolab-Miniapp
```

**Install dependencies:**

```bash
pip install aiohttp yuurisan
```

---

## Configuration

### 1. Accounts (data.txt)

Fill `data.txt` with Telegram WebApp `initData` for each account, one per line:

```
user=%7B%22id%22...&hash=abc123
user=%7B%22id%22...&hash=def456
```

> `initData` can be obtained from the browser DevTools when opening PigoLab on Telegram Web.

### 2. Proxy (proxy.txt)

Fill `proxy.txt` with proxies, one per line (optional, leave empty to run without proxy):

```
host:port
host:port:user:pass
http://user:pass@host:port
```

Proxies are assigned to accounts by index in round-robin order.

### 3. Bot Settings (config.json)

`sleep_seconds` controls how many seconds the bot waits between cycles. If `config.json` is missing, it is created automatically with a default of `3600` seconds.

---

## Running the Bot

```bash
python bot.py
```

Press `Ctrl+C` at any time to stop the bot cleanly.

---

## Features

### Sign In and Device Line

Every account signs in with its own credential plus a device line that is derived once per account from its Telegram id, so the same account always arrives with the same screen size, platform and memory values instead of a new phone on every run.

### Rig Cycle

The mining rig is started whenever no cycle is running, and the finished cycle is claimed once the server reports that the cycle has ended. A cycle that is still running is reported with the amount mined so far, and the bot wakes up early so the claim lands as soon as the cycle is over instead of waiting the whole sleep interval.

### Link Tasks

Link tasks are started, held for the dwell time the server asks for, and then claimed. Each claim is only reported after the server answers with the reward and the new balance, and a task the server refuses is summarised rather than retried in a loop.

### Channel Tasks

Tasks that need a real Telegram channel join are attempted once and then reported, so they are never counted as completed and never retried in a loop.

### Referral Tasks

Tasks that need real invited friends are summarised at the end of the task phase instead of being retried, since the bot cannot invent friends.

### Leaderboard Tracking

The current leaderboard position of the account is read and reported each cycle.

### Multi Account

All accounts in `data.txt` are processed at the same time within every cycle, and the cycle number is logged at the start of each round.

### Proxy Support

Proxies are loaded from `proxy.txt` and assigned to accounts by position in round-robin order. Proxy credentials are masked in log output. Running without proxies is fully supported.

### Cycle Waits

While an account waits for its next cycle the bot prints a running countdown line, so the remaining time is always visible in the log. Between cycles the bot waits the configured `sleep_seconds`, shortened when a rig cycle is about to end.

---

## File Structure

```text
PigoLab-Miniapp/
├── bot.py          # Main bot, full daily cycle automation
├── config.json     # Sleep duration between cycles
├── data.txt        # Account initData, one per line
├── proxy.txt       # Proxy list, one per line (optional)
├── LICENSE         # License file
└── utils/
    └── banner.py   # Banner using yuurisan module
```

---

## Disclaimer

This tool is built for educational and technical exploration purposes. Use it wisely and at your own responsibility.

---

<div align="center">
<img width="100%" alt="footer" src="https://capsule-render.vercel.app/api?type=waving&height=120&section=footer"/>
</div>
