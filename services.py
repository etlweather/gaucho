#!/usr/bin/env python
import baker
import json
import requests
import sys
import time
import websocket
import base64
from BaseHTTPServer import HTTPServer

HOST = "http://rancher.local:8080/v1"
URL_SERVICE = "/services/"
USERNAME = "userid"
PASSWORD = "password"
kwargs = {}

# HTTP
def get(url):
   r = requests.get(url, auth=(username, password), **kwargs)
   r.raise_for_status()
   return r

def post(url, data=""):
   if data:
      r = requests.post(url, data=json.dumps(data), auth=(USERNAME, PASSWORD), **kwargs)
   else:
      r = requests.post(url, data="", auth=(USERNAME, PASSWORD), **kwargs)
   r.raise_for_status()
   return r.json()

# Websocket
def ws(url):
  webS = websocket.create_connection(url)
  resp = base64.b64decode( webS.recv() )
  webS.close()
  return resp

# Helper
def print_json(data):
   print json.dumps(data, sort_keys=True, indent=3, separators=(',', ': '))


#
# Query the service configuration.
#
@baker.command(default=True, params={"service_id": "The ID of the service to read (optional)"})
def query(service_id=""):
   """Retrieves the service information.

   If you don't specify an ID, data for all services
   will be retrieved.
   """

   r = get(HOST + URL_SERVICE + service_id)
   print_json(r.json())



#
# Converts a service name into an ID
#
@baker.command(params={"name": "The name of the service to lookup."})
def id_of (name=""):
   """Retrieves the ID of a service, given its name.
   """

   service = get(HOST + "/services?name=" + name).json()
   return service['data'][0]['id']

#
# Start containers within a service (e.g. for Start Once containers).
#
@baker.command(params={"service_id": "The ID of the service to start the containers of."})
def start_containers (service_id):
   """Starts the containers of a given service, typically a Start Once service.
   """
   start_service (service_id)

#
# Start containers within a service (e.g. for Start Once containers).
#
@baker.command(params={"service_id": "The ID of the service to start the containers of."})
def start_service (service_id):
   """Starts the containers of a given service, typically a Start Once service.
   """

   # Get the array of containers
   containers = get(HOST + URL_SERVICE + service_id + "/instances").json()['data']
   for container in containers:
      start_url = container['actions']['start']
      print "Starting container %s with url %s" % (container['name'], start_url)
      post(start_url, "")


#
# Stop containers within a service.
#
@baker.command(params={"service_id": "The ID of the service to stop the containers of."})
def stop_service (service_id):
   """Stop the containers of a given service.
   """

   # Get the array of containers
   containers = get(HOST + URL_SERVICE + service_id + "/instances").json()['data']
   for container in containers:
      stop_url = container['actions']['stop']
      print "Stopping container %s with url %s" % (container['name'], stop_url)
      post(stop_url, "")


#
# Restart containers within a service
#
@baker.command(params={"service_id": "The ID of the service to restart the containers of."})
def restart_service(service_id):
  """Restart the containers of a given service.
  """

  # Get the array of containers
  containers = get(HOST + URL_SERVICE + service_id + "/instances").json()['data']
  for container in containers:
      restart_url = container['actions']['restart']
      print "Restarting container: " + container['name']
      post(restart_url)


#
# Upgrades the service.
#
@baker.command(params={
                        "service_id": "The ID of the service to upgrade.",
                        "start_first": "Whether or not to start the new instance first before stopping the old one.",
                        "complete_previous": "If set and the service was previously upgraded but the upgrade wasn't completed, it will be first marked as Finished and then the upgrade will occur.",
                        "imageUuid": "If set the config will be overwritten to use new image. Don't forget Rancher Formatting 'docker:<Imagename>:tag'",
                        "auto_complete": "Set this to automatically 'finish upgrade' once upgrade is complete",
                        "replace_env_name": "The name of an environment variable to be changed in the launch config (requires replace_env_value).",
                        "replace_env_value": "The value of the environment variable to be replaced (requires replace_env_name).",
                        "timeout": "How many seconds to wait until an upgrade fails"
                       })
def upgrade(service_id, start_first=True, complete_previous=False, imageUuid=None, auto_complete=False,
            batch_size=1, interval_millis=10000, replace_env_name=None, replace_env_value=None, timeout=60):
   """Upgrades a service

   Performs a service upgrade, keeping the same configuration, but otherwise
   pulling new image as needed and starting new containers, dropping the old
   ones.
   """

   upgrade_strategy = json.loads('{"inServiceStrategy": {"batchSize": 1,"intervalMillis": 10000,"startFirst": true,"launchConfig": {},"secondaryLaunchConfigs": []}}')
   upgrade_strategy['inServiceStrategy']['batchSize'] = batch_size
   upgrade_strategy['inServiceStrategy']['intervalMillis'] = interval_millis
   if start_first:
      upgrade_strategy['inServiceStrategy']['startFirst'] = "true"
   else:
      upgrade_strategy['inServiceStrategy']['startFirst'] = "false"

   r = get(HOST + URL_SERVICE + service_id)
   current_service_config = r.json()

   # complete previous upgrade flag on
   if complete_previous and current_service_config['state'] == "upgraded":
      print "Previous service upgrade wasn't completed, completing it now..."
      post(HOST + URL_SERVICE + service_id + "?action=finishupgrade", "")
      r = get(HOST + URL_SERVICE + service_id)
      current_service_config = r.json()

      sleep_count = 0
      while current_service_config['state'] != "active" and sleep_count < timeout // 2:
         print "Waiting for upgrade to finish..."
         time.sleep (2)
         r = get(HOST + URL_SERVICE + service_id)
         current_service_config = r.json()
         sleep_count += 1

   # can't upgrade a service if it's not in active state
   if current_service_config['state'] != "active":
      print "Service cannot be updated due to its current state: %s" % current_service_config['state']
      sys.exit(1)

   # Stuff the current service launch config into the request for upgrade
   upgrade_strategy['inServiceStrategy']['launchConfig'] = current_service_config['launchConfig']


   # replace the environment variable specified (if one was)
   if replace_env_name != None and replace_env_value != None:
      print "Replacing environment variable %s from %s to %s" % (replace_env_name, upgrade_strategy['inServiceStrategy']['launchConfig']['environment'][replace_env_name], replace_env_value)
      upgrade_strategy['inServiceStrategy']['launchConfig']['environment'][replace_env_name] = replace_env_value


   if imageUuid != None:
      # place new image into config
      upgrade_strategy['inServiceStrategy']['launchConfig']['imageUuid'] = imageUuid
      print "New Image: %s" % upgrade_strategy['inServiceStrategy']['launchConfig']['imageUuid']

   # post the upgrade request
   post(current_service_config['actions']['upgrade'], upgrade_strategy)

   print "Upgrade of %s service started!" % current_service_config['name']

   r = get(HOST + URL_SERVICE + service_id)
   current_service_config = r.json()

   print "Service State '%s.'" % current_service_config['state']

   print "Waiting for upgrade to finish..."
   sleep_count = 0
   while current_service_config['state'] != "upgraded" and sleep_count < timeout // 2:
         print "."
         time.sleep (2)
         r = get(HOST + URL_SERVICE + service_id)
         current_service_config = r.json()
         sleep_count += 1

   if sleep_count >= timeout // 2:
      print "Upgrading take to much time! Check Rancher UI for more details."
      sys.exit(1)
   else:
      print "Upgraded"

   if auto_complete and current_service_config['state'] == "upgraded":
      post(HOST + URL_SERVICE + service_id + "?action=finishupgrade", "")
      r = get(HOST + URL_SERVICE + service_id)
      current_service_config = r.json()
      print "Auto Finishing Upgrade..."

      upgraded_sleep_count = 0
      while current_service_config['state'] != "active" and upgraded_sleep_count < timeout // 2:
         print "."
         time.sleep (2)
         r = get(HOST + URL_SERVICE + service_id)
         current_service_config = r.json()
         upgraded_sleep_count += 1

      if current_service_config['state'] == "active":
         print "DONE"

      else:
         print "Something has gone wrong!  Check Rancher UI for more details."
         sys.exit(1)


#
# Execute remote command on container.
#
@baker.command(params={
                        "service_id": "The ID of the service to execute on",
                        "command": "The command to execute"
                      })
def execute(service_id,command):
  """Execute remote command

  Executes a command on one container of the service you specified.
  """

  # Get the array of containers
  containers = get(HOST + URL_SERVICE + service_id + "/instances").json()['data']

  # guard we have at least one container available
  if len(containers) <= 0:
    print "No container available"
    sys.exit(1)

  # take the first (random) container to execute the command on
  execution_url = containers[0]['actions']['execute']
  print "Executing '%s' on container '%s'" % (command, containers[0]['name'])

  # prepare post payload
  payload = json.loads('{"attachStdin": true,"attachStdout": true,"command": ["/bin/sh","-c"],"tty": true}')
  payload['command'].append(command)

  # call execution action -> returns token and url for websocket access
  intermediate = post(execution_url,payload)

  ws_token = intermediate['token']
  ws_url = intermediate['url'] + "?token=" + ws_token

  # call websocket and print answer
  print "> \n%s" % ws(ws_url)

  print "DONE"



#
# Rollback the service.
#
@baker.command(params={
                        "service_id": "The ID of the service to rollback.",
                        "timeout": "How many seconds to wait until an rollback fails"
                       })
def rollback(service_id, timeout=60):
   """Performs a service rollback
   """

   r = get(HOST + URL_SERVICE + service_id)
   current_service_config = r.json()

   # can't rollback a service if it's not in upgraded state
   if current_service_config['state'] != "upgraded":
      print "Service cannot be updated due to its current state: %s" % current_service_config['state']
      sys.exit(1)

   # post the rollback request
   post(current_service_config['actions']['rollback'], "");

   print "Rollback of %s service started!" % current_service_config['name']

   r = get(HOST + URL_SERVICE + service_id)
   current_service_config = r.json()

   print "Service State '%s.'" % current_service_config['state']

   print "Waiting for rollback to finish..."
   sleep_count = 0
   while current_service_config['state'] != "active" and sleep_count < timeout // 2:
         print "."
         time.sleep (2)
         r = get(HOST + URL_SERVICE + service_id)
         current_service_config = r.json()
         sleep_count += 1

   if sleep_count >= timeout // 2:
      print "Rolling back take to much time! Check Rancher UI for more details."
      sys.exit(1)
   else:
      print "Rolled back"


#
# Activate a service.
#
@baker.command(params={"service_id": "The ID of the service to deactivate.",
                        "timeout": "How many seconds to wait until an upgrade fails"})
def activate (service_id, timeout=60):
   """Activate the containers of a given service.
   """

   r = get(HOST + URL_SERVICE + service_id)
   current_service_config = r.json()

   # can't deactivate a service if it's not in active state
   if current_service_config['state'] != "inactive":
      print "Service cannot be deactivated due to its current state: %s" % current_service_config['state']
      sys.exit(1)

   post(current_service_config['actions']['activate'], "");

   # Wait deactivation to finish
   sleep_count = 0
   while current_service_config['state'] != "active" and sleep_count < timeout // 2:
      print "Waiting for activation to finish..."
      time.sleep (2)
      r = get(HOST + URL_SERVICE + service_id)
      current_service_config = r.json()
      sleep_count += 1


#
# Deactivate a service.
#
@baker.command(params={"service_id": "The ID of the service to deactivate.",
                        "timeout": "How many seconds to wait until an upgrade fails"})
def deactivate (service_id, timeout=60):
   """Stops the containers of a given service. (e.g. for maintenance purposes)
   """

   r = get(HOST + URL_SERVICE + service_id)
   current_service_config = r.json()

   # can't deactivate a service if it's not in active state
   if current_service_config['state'] != "active":
      print "Service cannot be deactivated due to its current state: %s" % current_service_config['state']
      sys.exit(1)

   post(current_service_config['actions']['deactivate'], "");

   # Wait deactivation to finish
   sleep_count = 0
   while current_service_config['state'] != "inactive" and sleep_count < timeout // 2:
      print "Waiting for deactivation to finish..."
      time.sleep (2)
      r = get(HOST + URL_SERVICE + service_id)
      current_service_config = r.json()
      sleep_count += 1



#
# Get a service state
#
@baker.command(default=True, params={"service_id": "The ID of the service to read"})
def state(service_id=""):
   """Retrieves the service state information.
   """

   r = get(HOST + URL_SERVICE + service_id)
   print(r.json()["state"])


#
# Script's entry point, starts Baker to execute the commands.
# Attempts to read environment variables to configure the program.
#
if __name__ == '__main__':
   import os

   # support for new Rancher agent services
   # http://docs.rancher.com/rancher/latest/en/rancher-services/service-accounts/
   if 'CATTLE_ACCESS_KEY' in os.environ:
      USERNAME = os.environ['CATTLE_ACCESS_KEY']

   if 'CATTLE_SECRET_KEY' in os.environ:
      PASSWORD = os.environ['CATTLE_SECRET_KEY']

   if 'CATTLE_URL' in os.environ:
      HOST = os.environ['CATTLE_URL']

   if 'RANCHER_ACCESS_KEY' in os.environ:
      USERNAME = os.environ['RANCHER_ACCESS_KEY']

   if 'RANCHER_SECRET_KEY' in os.environ:
      PASSWORD = os.environ['RANCHER_SECRET_KEY']

   if 'RANCHER_URL' in os.environ:
      HOST = os.environ['RANCHER_URL']

   if 'SSL_VERIFY' in os.environ:
      if os.environ['SSL_VERIFY'].lower() == "false":
        kwargs['verify'] = False
      else:
        kwargs['verify'] = os.environ['SSL_VERIFY']

   # make sure host ends with v1 if it is not contained in host
   if '/v1' not in HOST:
      HOST = HOST + '/v1'

   baker.run()
