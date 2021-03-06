import os, logging

# Server Configuration
HOST = '0.0.0.0'
PORT = '5000'
DEBUG = False
DATABASE_HOST = os.environ.get('MONGO_PORT_27017_TCP_ADDR','192.168.99.100')
DATABASE_PORT = os.environ.get('MONGO_PORT_27017_TCP_PORT','32768')
BASIC_AUTH_USERNAME = 'some'
BASIC_AUTH_PASSWORD = 'secret'
BASIC_AUTH_FORCE = False
LOG_LEVEL = logging.DEBUG
JSONIFY_PRETTYPRINT_REGULAR = True
STATS_COLLECTION = 'stats'
K_MEANS_COLLECTION = 'kmeans'
PLAYER_PROFILES = ['killer','collector','achiever']