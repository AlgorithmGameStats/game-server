# All the imports
import os, json, datetime, pymongo, time, sys, logging, random
from flask import Flask, jsonify, request, abort, current_app, make_response, render_template, g
from flask.ext.basicauth import BasicAuth
from flask_jsonschema import JsonSchema, ValidationError
from werkzeug.exceptions import BadRequest
from functools import wraps
from kmeans.kmeans import KMeans

# Flask light-weight web server.
app = Flask(__name__)
app.config.from_object('settings')
app.config['JSONSCHEMA_DIR'] = os.path.join(app.root_path, 'schemas')
jsonschema = JsonSchema(app)
basic_auth = BasicAuth(app)
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
  start = time.clock()
  g.db = connect_db()
  app.logger.debug('Database connection time: {0}'.format( (time.clock() - start) ))

@app.teardown_request
def teardown_request(exception):
  start = time.clock()
  db = getattr(g, 'db', None)
  if db is not None:
    db.client.close()
  app.logger.debug('Database close time: {0}'.format( (time.clock() - start) ))

def connect_db():
  client = pymongo.MongoClient(
    host=app.config.get('DATABASE_HOST', 'localhost'), 
    port=int(app.config.get('DATABASE_PORT', '27017'))
  )
  return client.game


##########################
#### SERVER FUNCTIONS ####
##########################

@app.route("/health", methods=['GET'])
def health():
  """
  Used for Load Balancer Health Checks...
  """
  # Get DB from context, if we can, we assume we are healthy...
  return 'OK', 200


@app.route("/dump", methods=['GET'])
@basic_auth.required
def dump():
  """
  Used for Load Balancer Health Checks...
  """
  # Get DB from context, if we can, we assume we are healthy...
  configs = {}
  for item in app.config:
    configs[item] = str(app.config[item])
  return make_response(jsonify({"config": configs}), 200)


@app.route("{0}/stats".format(api), methods=['POST'])
@basic_auth.required
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
  db = getattr(g, 'db', None)
  colection = get_stats_collection()
  stats_collection = db[colection]
  colection = get_kmeans_collection()
  kmeans_collection = db[colection]

  # Get the Json order from the request
  new_stats = request.get_json()
  new_stats['timestamp'] = datetime.datetime.utcnow() # we add the submit date not the user...

  result = stats_collection.insert_one(new_stats) # Store in MongoDB
  stats_id = result.inserted_id # used later for updating the document with the class name and score
  new_stats['_id'] = str(result.inserted_id) # Update local copy with the id.

  # Get K_Means classes from DB
  profile_names = get_player_profiles()
  player_profiles = {}
  profile_scores = dict()
  player_item = [
    float(new_stats['time_used'] / new_stats['time_total']), 
    float(new_stats['coins_collected']/ new_stats['coins_total']), 
    float(new_stats['enemies_killed'] / new_stats['enemies_total'])
  ]
  for name in profile_names:
    app.logger.debug('Looking for "{0}"" cluster data.'.format(name))
    k = construct_kmeans_obj(kmeans_collection,name)
    if k is not None:
      # If the k_obj item exists on the db, let's calculate all we need
      app.logger.debug('Found KMeans cluster for "{0}", K: {1}'.format(name,k.k()))
      player_profiles[name] = k
      profile_scores[name] = get_player_profile_score(k_obj=k, player_item=player_item)
    else: 
      # if k_obj does not exist on the DB, let's just generate a random number for it.
      # We will give it a 'negative' number so it will always be lower than any k_obj found.
      app.logger.debug('Did not find KMeans cluster for "{0}", using random negative value'.format(name))
      profile_scores[name] = random.uniform(-1000, 0)

  # Get the name of the max score
  max_name, max_value = max(profile_scores.iteritems(), key=lambda p: p[1])
  app.logger.debug('Results for this request --> Class Name: "{0}", Class Score: "{1}"'.format(max_name,max_value))

  # Return the class_name & class_score back.
  ret_json = {'class_name': max_name, 'class_score': max_value}

  # Before returning, update the DB record with the class_name and class_score
  stats_collection.find_one_and_update({'_id': stats_id}, {'$set': ret_json})

  return jsonify(ret_json), 201


@app.route("{0}/stats".format(api), methods=['GET'])
@basic_auth.required
def get_stats():
  """
  Get all stats from the DB.
  """
  # Get DB from context:
  db = getattr(g, 'db', None)
  colection = get_stats_collection()
  stats_collection = db[colection]

  ret_array = []
  for stat in stats_collection.find().sort([('date', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]):
      stat['_id'] = str(stat['_id'])
      ret_array.append(stat)
  return jsonify({'stats': ret_array})


@app.route("{0}/clusters".format(api), methods=['POST'])
@basic_auth.required
@validate_json
@jsonschema.validate('clusters')
def post_clusters():
  """
  Get all of the KMeans Clusters Data from the DB
  """
  # Get DB from context:
  db = getattr(g, 'db', None)
  colection = get_kmeans_collection()
  kmeans_collection = db[colection]

  # Get the Json order from the request
  new_cluster = request.get_json()
  new_cluster['timestamp'] = datetime.datetime.utcnow() # we add the submit date not the user...


  result = kmeans_collection.find_one_and_update(
    {'class_name': new_cluster['class_name'], 'level': new_cluster['level']}, 
    {'$set': new_cluster}, 
    upsert=True
  )
  new_cluster['_id'] = str(result['_id']) # Update local copy with the id.
  
  return jsonify({'cluster': new_cluster}), 200


@app.route("{0}/clusters".format(api), methods=['GET'])
@basic_auth.required
def get_clusters():
  """
  Get all of the KMeans Clusters Data from the DB
  """
  # Get DB from context:
  db = getattr(g, 'db', None)
  colection = get_kmeans_collection()
  kmeans_collection = db[colection]

  ret_array = []
  for cluster in kmeans_collection.find().sort([('class_name', pymongo.DESCENDING), ('_id', pymongo.DESCENDING)]):
      cluster['_id'] = str(cluster['_id'])
      ret_array.append(cluster)
  return jsonify({'clusters': ret_array}),200

##########################
#### HELPER FUNCTIONS ####
##########################

# Helper: Converts string to Boolean
def parse_bool(s):
  """
  Parse a string to boolean value
  """
  if s is None:
    return False
  else:
    return str(s).lower() in ('1', 'true', 't', 'yes', 'y')

def get_stats_collection():
  """
  Get the Stats Collection Name for the db
  """
  return app.config.get('STATS_COLLECTION', 'stats')

def get_kmeans_collection():
  """
  Get the KMeans collection name from the DB
  """
  return app.config.get('K_MEANS_COLLECTION', 'kmeans')

def get_player_profiles():
  """
  Get Player profile's names from the config file
  """
  return app.config.get('PLAYER_PROFILES',['killer','collector','achiever'])

def construct_kmeans_obj(collection, class_name):
  """
  Grabs the kmeans data from the db
  Re-creates the KMeans object
  Data: 
  {
    'class_name': 'killer/achiever/collector',
    'k': 2,
    'centroids': [ [] [] ],
    'clusters': [ [] [] ],
  }
  """
  k = None
  class_name = class_name.lower()
  k_data = collection.find_one({'class_name': class_name})
  if k_data is not None:
    k = KMeans(k=k_data['k'], class_name=class_name)
    k.centroids = k_data['centroids']
    k.clusters = k_data['clusters']
  return k

def get_player_profile_score(k_obj, player_item):
  """
  Calculate the dot_product of the player given a specific KMeans object.
  If the KMeans object is of K>1 it will sum all dot_product values together.
  player_item: [time, coins_%, murders]
  """
  return sum(dot_product(k_obj, player_item))


def dot_product(k_obj, player_item):
  """
  calculate the dot product of a player item to all centroids in a kmeans object
  player_item: [time, coins_%, murders]
  """
  return k_obj.dot_product(player_item)


# Helper: respond method for 404 errors
@app.errorhandler(404)
def not_found(error):
  return make_response(jsonify({'error': 'Not found'}), 404)


##########################
########## Main ##########
##########################
if __name__ == '__main__':
  
  # Set logging
  handler = logging.StreamHandler()
  handler.setLevel(app.config.get('LOG_LEVEL', logging.INFO))
  formatter = logging.Formatter( "%(asctime)s | %(pathname)s:%(lineno)d | %(funcName)s | %(levelname)s | %(message)s ")
  handler.setFormatter(formatter)
  app.logger.addHandler(handler)
  app.logger.setLevel(app.config.get('LOG_LEVEL', logging.INFO))

  # Start Server
  app.run(threaded=True, host=app.config.get('HOST', 'localhost'), 
    port=int(app.config.get('PORT', '5000')), 
    debug=parse_bool(app.config.get('DEBUG', 'false')))