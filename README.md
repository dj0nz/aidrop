## Drop AI crawlers

Tired of shitty AI bots crawling your website ignoring robots.txt?  
This one's for you. *zwinker*

### [aidrop.py](aidrop.py)  
Runs on a webserver or reverse proxy or whatever target system. It creates an ipset from a set of known crawler URLs.

### [aidrop.conf](aidrop.conf)  
An input chain configuraton snippet for a [ferm](https://github.com/MaxKellermann/ferm) ruleset.
