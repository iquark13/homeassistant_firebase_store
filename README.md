# homeassistant_firebase_store
Firebase component for the homeassistant

Forked to try and get google assistant working with HASS without opening up local network.

Using homeassistant_firebase_store custom component as a base, and then will be creating the node.js work to connect google actions.



Step 1:

- Create a firestore project throught the firebase console: console.firebase.google.com/ -> Build -> Cloud Firestore
    No need to setup a billing plan, you should stay within the Spark free tier.

Step 2:

- Generate a private key:
    * Project overview -> project settings
    * Service Accounts -> firebase admin SDK -> select python -> generate new private key. Save this file! This will be critical to running the custom component.

Step 3:

- Clone repo.

Step 4:

- Generate bearer token from Home Assistant -> Profile (bottom left) -> scroll down to long lived access token.
    *Save this string in the 'homeassistant_access_token.txt' in the git folder.