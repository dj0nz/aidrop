#!/usr/bin/python3

# Fetch the published IP ranges of AI crawlers / bots and load them
# into an ipset ("aibots") that is referenced by a DROP rule in ferm.
#
# Requirements (Debian): python3-requests, python3-pyroute2
#
# Behaviour:
# - each source is downloaded. on failure the last good copy from the cache dir is used
# - the new set is built under a temporary name and swapped in atomically
# - if no prefixes at all were found, the live set is left untouched
#
# dj0Nz jul 2025 
# Revised nov 2026

import ipaddress
import json
import os
import sys
from syslog import syslog

import pyroute2
import requests

# Sources - all of them use the same json format:
# { "prefixes": [ { "ipv4Prefix": "a.b.c.d/nn" }, { "ipv6Prefix": "..." } ] }
SOURCES = [
    {'name': 'openai-searchbot',      'url': 'https://openai.com/searchbot.json'},
    {'name': 'openai-gptbot',         'url': 'https://openai.com/gptbot.json'},
    {'name': 'openai-chatgpt',        'url': 'https://openai.com/chatgpt-user.json'},
    {'name': 'perplexity-pxbot',      'url': 'https://www.perplexity.com/perplexitybot.json'},
    {'name': 'perplexity-user',       'url': 'https://www.perplexity.com/perplexity-user.json'},
    {'name': 'google-bot',            'url': 'https://developers.google.com/static/crawling/ipranges/common-crawlers.json'},
    {'name': 'google-user-triggered', 'url': 'https://developers.google.com/static/crawling/ipranges/user-triggered-fetchers.json'},
    {'name': 'applebot',              'url': 'https://search.developer.apple.com/applebot.json'},
    {'name': 'bingbot',               'url': 'https://www.bing.com/toolbox/bingbot.json'},
]

# name used in the ferm rule
IPSET_NAME = 'aibots'
# temporary set for the atomic swap
IPSET_TMP = 'aibots-tmp'          
# last good copy of each json
CACHE_DIR = '/var/cache/aibots'   
# State file queried by a local CheckMK check
STATE_FILE = '/var/run/aidrop.state'  
# http timeout in seconds
TIMEOUT = 30                      

# function for writing log messages
def log(message):
    syslog('aidrop: ' + message)

# function for writing state file
def write_state(message):
    with open(STATE_FILE, 'w') as state:
        state.write(message + '\n')

# this one fetches Json from given URL
def fetch_json(name, url):
    """Download json, fall back to cached copy if download fails."""
    cache_file = os.path.join(CACHE_DIR, name + '.json')
    try:
        response = requests.get(url, timeout=TIMEOUT)
        response.raise_for_status()
        data = response.json()
        if 'prefixes' not in data:
            raise ValueError('no "prefixes" key in json')
        # download is good - update cache
        with open(cache_file, 'w') as f:
            json.dump(data, f, indent=2)
        return data
    except Exception as error:
        log('download failed for ' + name + ': ' + str(error))

    if os.path.isfile(cache_file):
        log('using cached copy for ' + name)
        with open(cache_file, 'r') as f:
            return json.load(f)

    log('no cached copy for ' + name + ', skipping')
    return None


# --- collect prefixes ---

os.makedirs(CACHE_DIR, exist_ok=True)
networks = []

# get all 
for source in SOURCES:
    data = fetch_json(source['name'], source['url'])
    if data is None:
        continue
    for entry in data['prefixes']:
        prefix = entry.get('ipv4Prefix')
        if prefix is None:
            # ipv6 entry - ignored
            continue
        try:
            networks.append(ipaddress.IPv4Network(prefix, strict=False))
        except ValueError:
            log('invalid prefix from ' + source['name'] + ': ' + str(prefix))

# remove duplicates and merge overlapping / adjacent networks
networks = list(ipaddress.collapse_addresses(networks))

if not networks:
    # keep the existing set as it is
    log('no prefixes found, ipset not changed')
    write_state('No prefixes found.')
    sys.exit(1)

# --- build ipset ---

ipset = pyroute2.IPSet()

# remove leftover temp set from an aborted run
# (never call destroy() without a name - that would remove ALL sets)
try:
    ipset.destroy(IPSET_TMP)
except Exception:
    pass

ipset.create(IPSET_TMP, stype='hash:net')
for net in networks:
    try:
        ipset.add(IPSET_TMP, str(net), etype='net')
    except Exception as error:
        log('entry not added: ' + str(net) + ': ' + str(error))

# first run: live set does not exist yet
try:
    ipset.list(IPSET_NAME)
except Exception:
    ipset.create(IPSET_NAME, stype='hash:net')

# atomic replace: live set gets the new content, temp set the old one
ipset.swap(IPSET_NAME, IPSET_TMP)
ipset.destroy(IPSET_TMP)
ipset.close()

log('ipset updated with ' + str(len(networks)) + ' prefixes')
write_state('Ok')
