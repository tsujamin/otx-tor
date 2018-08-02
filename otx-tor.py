from stem.descriptor.remote import get_consensus
from OTXv2 import OTXv2
from os import getenv
from datetime import datetime, timedelta
import pickle
# relay_format:
""

# initialise OTX vars
OTX_SERVER = getenv("OTX_SERVER", default="https://otx.alienvault.com/")
OTX_API_KEY = getenv("OTX_API_KEY", default=None)
OTX_FEED_NAME = getenv("OTX_FEED_NAME", default="TOR-Relay-Nodes")
OTX_FEED_PUBLIC = bool(getenv("OTX_FEED_PUBLIC", default=False))
OTX_FEED_OWNER = getenv("OTX_FEED_OWNER", default=None)
OTX_FEED_EXPIRE = bool(getenv("OTX_FEED_EXPIRE", default=True))
OTX_INDICATOR_FILE = getenv("OTX_INDICATOR_FILE", default="./onion-otx-feed-storage.pickle")
FILTER_INDICATOR_FIELD = ["published", "expires", "role"]

if OTX_API_KEY is None:
    print("environmental variable OTX_API_KEY must be set, exiting...")
    exit(1)

# Conenct to OTX
otx = OTXv2(OTX_API_KEY, server=OTX_SERVER)
if otx is None:
    print("failed to connect to OTX")

# search for existing pulse
feed_id = None
feed_results = otx.search_pulses(OTX_FEED_NAME)
for feed_result in feed_results["results"]:
    if feed_result["author_name"] == OTX_FEED_OWNER:
        feed_id = feed_result["id"]

if feed_id is None:
    # create feed
    new_feed = otx.create_pulse(name=OTX_FEED_NAME,
                     public=OTX_FEED_PUBLIC,
                     tlp="white",
                     tags=["tor", "relay", "onion"],
                     references=["torproject.org"],
                     indicators=[])
    print("created feed")
    feed_id = new_feed["id"]

print("using feed %s" % (feed_id))

# get_existing_indicators
try:
    with open(OTX_INDICATOR_FILE, "rb") as r:
        indicators = pickle.load(r)
except:
    indicators = {}
print ("%d existing indicators retrieved" % (len(indicators)))

# Load tor consensus
tor_relays = get_consensus().run()
print("%d active relays found" % (len(tor_relays)))

for relay in tor_relays:
    title = "tor relay %s:%s" % (relay.address, relay.or_port)
    description = "%s:%s (%s, %s) last_published: %s" % (relay.address,
                                                       relay.or_port,
                                                       relay.nickname,
                                                       relay.fingerprint,
                                                       relay.published)
    indicators[(relay.address, relay.or_port)] = {
        "type": "IP",
        "indicator": relay.address,
        "role": "tor_relay",
        "description": description,
        "title": title,
        "published": relay.published #store for calculation in next step
    }

# Update the is_active and expires fields
for relay in indicators.values():
    relay["expires"] = (relay["published"] + timedelta(hours=19)) #one hour grace
    relay["is_active"] = (relay["published"]  + timedelta(hours=18)) > datetime.utcnow()

# Send indicators, filtering for ommited fields
print("sending indicators")
otx.replace_pulse_indicators(feed_id, [{k: str(v) for k,v in indicator.items() if k not in FILTER_INDICATOR_FIELD} for indicator in indicators.values()])

print("saving indicators")
with open(OTX_INDICATOR_FILE, "wb") as r:
    pickle.dump(indicators, r)
