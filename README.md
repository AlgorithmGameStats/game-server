# Game Server for Algorithms Class

This is a game server created in python for our Algorithms class.
It will receive game statistics and calculate K-Means for getting difficulty spikes.

## Set up:

* Have Python 2.7.x installed
* Have pip installed
* Install dependencies via pip: `pip install -r requirements.txt`
* Have a MongoDB up and running

## How to Run:
* Modify the `game-server.py` file to point to your MongoDB host and port:
```
DATABASE_HOST = '192.168.99.100'
DATABASE_PORT = '32768'
```
* Run: `python game-server.py`