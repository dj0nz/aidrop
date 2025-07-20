#!/usr/bin/python3

# crawl ips of ai crwalers and create ipset for blocking with iptables
#
# this is the first part: it runs on a management system (an ansible host would be perfect) 
# and downloads json from a bunch of sources. then it creates a plain list with ipv4 
# prefixes and uploads that to its subscribers (webservers etc.). instead of uploading
# and processing by the second script, you may use ansible or any other automation tool.
#
# the second part, running on the subscriber itself, updates an ipset if
# there is an updated prefix list
#
# dj0Nz jul 2025

import json, ipaddress, requests, os, subprocess, time, paramiko
from syslog import syslog

# check if input is a valid ipv4 address or network
def is_ipv4(input_address):
    try:
        valid_addr = ipaddress.IPv4Address(input_address)
        return True
    except:
        try:
            valid_net = ipaddress.IPv4Network(input_address)
            return True
        except:
            return False

# download json from given url
def download_json(download_url,download_file):
    try:
        response = requests.get(download_url)
    except:
        syslog('Cant connect to service. Check url.' + download_url)
        return('failed')
    resp_json = response.json()
    with open(download_file,'w') as output:
        json.dump(resp_json,output,indent=2)

# the aibot prefixes list - at least the ones that provide a json in common format:
# {
#   "prefixes": [
#     {
#       "ipv4Prefix": "net.work.ip.address/mask-length"
#     }
#   ]
# }
# as usual, amazon is the "extra sausage" xD
aibotlist = [
    { 'name' : 'openai-searchbot', 'url': 'https://openai.com/searchbot.json' },
    { 'name' : 'openai-gptbot', 'url': 'https://openai.com/gptbot.json' },
    { 'name' : 'openai-chatgpt', 'url': 'https://openai.com/chatgpt-user.json' },
    { 'name' : 'perplexity-pxbot', 'url': 'https://www.perplexity.com/perplexitybot.json' },
    { 'name' : 'perplexity-user', 'url': 'https://www.perplexity.com/perplexity-user.json' },
    { 'name' : 'google-bot', 'url': 'https://developers.google.com/search/apis/ipranges/googlebot.json' },
    { 'name' : 'google-user-triggered', 'url': 'https://developers.google.com/static/search/apis/ipranges/user-triggered-fetchers.json' },
    { 'name' : 'applebot', 'url': 'https://search.developer.apple.com/applebot.json' },
    { 'name' : 'bingbot', 'url': 'https://www.bing.com/toolbox/bingbot.json' }
]

# the prefix list
iplist = []
# current time
now = time.time()
# max age of the json files
max_age = 43200
# the output file to transfer to subcribers
output_file = '/tmp/aibots.prefixes'
# target systems get extracted prefix list.
# pubkey auth should be working or provide password or both
subscribers = ( 'webserver', 'nextcloud' )

# the main part: loop through aibotlist and extract ipv4prefixes
for aibot in aibotlist:
    # see download_json
    download_result = 'successful'
    # get variable name and url from list
    aibot_name = aibot.get('name')
    aibot_url = aibot.get('url')
    # construct file names
    json_file = '/tmp/' + aibot_name + '.json'

    if not os.path.isfile(json_file):
        download_result = download_json(aibot_url,json_file)
    elif os.stat(json_file).st_mtime < now - max_age:
        download_result = download_json(aibot_url,json_file)

    # skip the rest of this loop if download not successful
    if download_result == 'failed':
        continue

    with open(json_file,'r') as input:
        resp_json = json.load(input)

    # extract ipv4 prefixes
    prefixes = []
    for prefix in resp_json['prefixes']:
        try:
            if is_ipv4(prefix['ipv4Prefix']):
                prefixes.append(prefix['ipv4Prefix'])
        except:
            continue
    for prefixes_entry in prefixes:
        iplist.append(prefixes_entry)

with open(output_file, 'w') as output:
    for entry in iplist:
        output.write(entry + '\n')

ssh = paramiko.SSHClient()
ssh.load_system_host_keys()
for target in subscribers:
    ssh.connect(target, username='scpuser', password='', key_filename='/home/scpuser/.ssh/id_ed25519')
    ssh.open_sftp().put(output_file,output_file)
    ssh.close
