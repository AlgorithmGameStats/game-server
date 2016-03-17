# All the imports
import os, json, datetime, pymongo
from flask import Flask, jsonify, request, abort, current_app, make_response, render_template, g
from flask_jsonschema import JsonSchema, ValidationError
from werkzeug.exceptions import BadRequest
from functools import wraps

# Configuration
HOST = '0.0.0.0'
PORT = '5000'
DEBUG = False
DATABASE_HOST = '192.168.99.100'
DATABASE_PORT = '32769'

# Flask light-weight web server.
app = Flask(__name__)
app.config.from_object(__name__)
app.config['JSONSCHEMA_DIR'] = os.path.join(app.root_path, 'schemas')
jsonschema = JsonSchema(app)
api = '/api/1.0'


##############################
#### VALIDATION FUNCTIONS ####
##############################

def validate_json(f):
  @wraps(f)
  def wrapper(*args, **kw):
    try:
      request.get_json()
    except BadRequest, e:
      msg = "request must be a valid json"
      return jsonify({"error": msg}), 400
    return f(*args, **kw)
  return wrapper

@app.errorhandler(ValidationError)
def on_validation_error(e):
  return make_response(jsonify({"error": e.message}), 400)

@app.before_request
def before_request():
  g.db = connect_db()

@app.teardown_request
def teardown_request(exception):
  db = getattr(g, 'db', None)
  if db is not None:
    db.client.close()

def connect_db():
  client = pymongo.MongoClient(
    host=app.config.get('DATABASE_HOST', 'localhost'), 
    port=int(app.config.get('DATABASE_PORT', '27017'))
  )
  return client.game

##########################
#### SERVER FUNCTIONS ####
##########################

@app.route("{0}/stats".format(api), methods=['POST'])
@validate_json
@jsonschema.validate('stats')
def post_stats():
  """
  Receive new player statistics.
  Required Header: Content-Type: 'application/json'.
  Request is a JSON object.
  Schema: 'schemas/stats.json'.
  """
  
  # Get DB from context:
  stats_collection = g.db.stats

  # Get the Json order from the request
  new_stats = request.get_json()
  new_stats['timestamp'] = datetime.datetime.utcnow() # we add the submit date not the user...

  result = stats_collection.insert_one(new_stats) # Store in MongoDB
  new_stats['_id'] = str(result.inserted_id) # Update local copy with the id.

  # Calculate new k-means
  # Maybe create a response json with new difficulty?

  return jsonify(new_stats), 201


@app.route("{0}/stats".format(api), methods=['GET'])
def get_stats():
  """
  Get all stats from the DB.
  """
  # Get DB from context:
  stats_collection = g.db.stats

  ret_array = []
  for stat in stats_collection.find().sort([('date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]):
      stat['_id'] = str(stat['_id'])
      ret_array.append(stat)
  return jsonify({'stats': ret_array})

##########################
#### HELPER FUNCTIONS ####
##########################

# Helper: Converts string to Boolean
def parse_bool(s):
  if s is None:
    return False
  else:
    return str(s).lower() in ('1', 'true', 't', 'yes', 'y')

# Helper: respond method for 404 errors
@app.errorhandler(404)
def not_found(error):
  return make_response(jsonify({'error': 'Not found'}), 404)

if __name__ == '__main__':
  app.run(host=app.config['HOST'], port=int(app.config['PORT']), debug=parse_bool(app.config['DEBUG']))