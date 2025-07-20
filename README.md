## Drop AI crawlers

Tired of shitty AI bots crawling your website ignoring robots.txt?  
This one's for you. *zwinker*

### [create_ai_droplist.py](create_ai_droplist.py)  
Runs on an admin workstation oder automation system, crawls known AI crawler lists und transfers them to a list of "subscibers"

### [aidrop.py](aidrop.py)  
Runs on a webserver or reverse proxy or whatever target system. It creates an ipset from the list it got from the script above
