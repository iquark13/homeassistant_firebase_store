"""Support for Google Cloud Firebase"""
import datetime
import json
import logging
import os
import requests
from typing import Any, Dict

import firebase_admin
from firebase_admin import credentials, firestore
import voluptuous as vol

from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entityfilter import FILTER_SCHEMA

_LOGGER = logging.getLogger(__name__)

DOMAIN = "google_firebase_store"

CONF_SERVICE_PRINCIPAL = "credentials_json" #This will be your key created from firebase
CONF_WEB_TOKEN = "web_token"                #This will be your long term bearer token created from your profile (string, can be in !secret form)
CONF_FILTER = "filter"                      #This will be the list of entities to track using the HASS filter schema

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_SERVICE_PRINCIPAL): cv.string,
                vol.Optional(CONF_WEB_TOKEN): cv.string,
                vol.Optional(CONF_FILTER): FILTER_SCHEMA,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

url = 'http://localhost:8123/api/services/homeassistant/turn_on'


def setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Google Firebase component."""
    
    #The hass.config is passed into setup as the yaml_config - this pulls the settings from the component
        #like the filter values, or the token values, or the firebase auth file location.
    config = yaml_config[DOMAIN] 
    
    #This simply pulls together the path to the firebase private key file.
    service_principal_path = os.path.join(
        hass.config.config_dir, config[CONF_SERVICE_PRINCIPAL]
    )
    
    #Use the token that we provided in the !secret file -> store the request format in hed
    token = config[CONF_WEB_TOKEN]
    hed = {'Authorization': 'Bearer ' + token}

    #Check and make sure that the credentials exist.
    if not os.path.isfile(service_principal_path):
        _LOGGER.error("Path to credentials file cannot be found")
        return False

    #This uses the config[DOMAIN] from the hass.config passed to setup and the global filter name to
        #create a filter list of entity types. THe filter domains are passed as a python list from the config.yaml
    entities_filter = config[CONF_FILTER]

    #Use firebase credentials to store the firebase credentials into the cred variable
    cred = credentials.Certificate(service_principal_path)
    
    #Use the credentials to setup access to the firebase object
    default_app = firebase_admin.initialize_app(cred)

    #Setup a firestore (database/storage items) in the db variable.
    db = firestore.client()



    def send_to_pubsub(event: Event):
        '''Send states to Firebase
        
            Inputs: Receives an event from the hass.bus.listener

            Actions: Checks if state exists, is unknown/unavailable (useless statusses), or if it isn't in the domain from the filter

            If: it isn't for our stuff, then jump out.

            Else: store it in the database on firestore.
        
        '''
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not entities_filter(state.entity_id)
        ):
            return
        
        #Goes into the collection (top level) and grabs a specific database entry (document)
            #Note - the 'u' before the collection name signifies that this is a unicode string
        doc_ref = db.collection(u'homeassistant').document(state.entity_id)

        #Sets the previously grabbed document (database entry) to the state of the item that fired the event.
        doc_ref.set(state.as_dict())

    hass.bus.listen(EVENT_STATE_CHANGED, send_to_pubsub) #This seems like it is calling the private bus component of the class maybe change to eventbus?
    

    #Now deal with actually setting things!

    #Useful background on the firestore callback: https://firebase.google.com/docs/firestore/query-data/listen#python_4

    def fire_event(col_snapshot, changes, read_time):
        print(u'Callback received query snapshot.')
        print(u'Current triggers:')
        for change in changes:
            if change.type.name == 'MODIFIED':
                data = {"entity_id": "input_boolean." + u'{}'.format(change.document.id)}
                _LOGGER.debug("Firebase plugin token: " + token)
                response = requests.post(url, json=data, headers=hed)
                _LOGGER.debug("Firebase plugin fire: " + u'{}'.format(change.document.id))

    col_query = db.collection(u'triggers')

    # Watch the collection query in a background thread, and call back to the function listed
    query_watch = col_query.on_snapshot(fire_event)

    return True

