i#!/usr/bin/python3

# create ipset from aibots.prefixes to block with iptables
# for this to work, the pyroute2 module has to be installed
# either using pip or the debian package (python3-pyroute2)

# dj0Nz jul 25

import os, sys, ipaddress, pyroute2

# function to check if input is a valid ipv4 address or network
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

# just a name...
ipset = pyroute2.IPSet()
ipset_name = 'aibots'
# this one will be provided by the create script
infile = '/tmp/aibots.prefixes'
# query the state file with your monitoring tool
state_file = '/var/run/aidrop.state'
aibotlist = []
is_valid_ip = False

# check if aibot list file exists
if os.path.isfile(infile):
    with open(infile, 'r') as file:
        aibotlist = [line.rstrip('\n') for line in file]
else:
    with open(state_file, 'w') as state:
        state.write('No input file.\n')
    sys.exit(1)

# check if ipset is already there...
ipset_present = ipset.list(ipset_name)
if ipset_present:
    # ...and reset it
    ipset.flush(ipset_name)
else:
    ipset.create(ipset_name, stype='hash:net')

for bot in aibotlist:
    if is_ipv4(bot):
        # add entries to ipset
        ipset.add(ipset_name, bot, etype = 'net')
        # list is "okay" if at least one valid entry is in it
        is_valid_ip = True

# finally write state file 
with open(state_file, 'w') as state:
    if is_valid_ip:
        state.write('Ok\n')
    else:
        state.write('Ipset empty.\n')
