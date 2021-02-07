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

url = 'http://localhost:8123/api/services/homeassistant/toggle'

#Set the watch collection:
WATCH_COLLECTION = u'exposed_devices'

def setup(hass: HomeAssistant, yaml_config: Dict[str, Any]):
    """Activate Google Firebase component."""

    config = yaml_config[DOMAIN]
    service_principal_path = os.path.join(
        hass.config.config_dir, config[CONF_SERVICE_PRINCIPAL]
    )
    
    token = config[CONF_WEB_TOKEN]
    #Create the API call header for the HTTP post. This is a long term key.
    hed = {'Authorization': 'Bearer ' + token,
            "content-type": "application/json"}

    if not os.path.isfile(service_principal_path):
        _LOGGER.error("Path to credentials file cannot be found")
        return False

    entities_filter = config[CONF_FILTER]

    cred = credentials.Certificate(service_principal_path)
    default_app = firebase_admin.initialize_app(cred)
    db = firestore.client()



    def send_to_pubsub(event: Event):
        """Send states to Firebase """
        state = event.data.get("new_state")
        if (
            state is None
            or state.state in (STATE_UNKNOWN, "", STATE_UNAVAILABLE)
            or not entities_filter(state.entity_id)
        ):
            return

        doc_ref = db.collection(u'homeassistant').document(state.entity_id)

        doc_ref.set(state.as_dict())

    hass.bus.listen(EVENT_STATE_CHANGED, send_to_pubsub)
    

    def fire_event(col_snapshot, changes, read_time):
        print(u'Callback received query snapshot.')
        print(u'Current triggers:')
        for change in changes:
            if change.type.name == 'MODIFIED':
                data = {"entity_id": "input_boolean." + u'{}'.format(change.document.id)}
                _LOGGER.debug("Firebase plugin token: " + token)
                response = requests.post(url, json=data, headers=hed)
                _LOGGER.debug("Firebase plugin fire: " + u'{}'.format(change.document.id))


#Helpful: https://github.com/GoogleCloudPlatform/python-docs-samples/blob/master/firestore/cloud-client/snippets.py
    def execute_google_command(col_snapshot, changes, read_time):
        print(u'Callback received on trigger snapshot.')
        deletion_queue = []
        for change in changes:
            if change.type.name in ['MODIFIED','ADDED']:
                data = {"entity_id": change.document.id}
                response = requests.post(url, json=data, headers=hed)
                deletion_queue.append(change.document.id)
        for entity in deletion_queue:
            delete_used_field(entity)
        return

    def delete_used_field(entity: str):
        entity_ref = col_query.document(entity)
        entity_ref.update({u'state':firestore.DELETE_FIELD})
        return


    col_query = db.collection(WATCH_COLLECTION)

    # Watch the collection query
    query_watch = col_query.on_snapshot(execute_google_command)

    return True

