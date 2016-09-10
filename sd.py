#
# Copyright 2011 Alex Dementsov
#
# StationDigger - program which performs collection of information about stations
#                 in TuneIn radio service: http://inside.radiotime.com/developers/api/opml

import json
import time
import urllib2
import ConfigParser
from StringIO import StringIO
from gzip import GzipFile

ENDPOINT    = "http://opml.radiotime.com"
DESCRIBE    = "Describe.ashx"
BROWSE      = "Browse.ashx"
WAIT_TIME   = 240 # 4 min

class StationDigger(object):
    
    _stations   = {}
    _lang       = {}    # dictionary of languages
    _genres     = {}    # dictionary of genres
    _countries  = {}    # dictionary of countries
    _urls       = set()
    num         = 0
    numTotal    = None

    def __init__(self):
        pass


    def make_call(self, url):
        "Makes call and returns response in json format"
        if not url:
            return None
        nurl    = self._set_format(url)
        if nurl in self._urls:  # Avoid circular reference
            return None
        result  = -1    # to enter the loop

        while (result == -1):
            try:
                req         = urllib2.Request(nurl, headers=self._headers())
                response    = urllib2.urlopen(req)
                page        = self._decompress(response.read()) # decompress
                pdict       = json.loads(page)
                result      = pdict.get("body")    # interested in "body" section only: should be list
                self._urls.add(nurl)    # URL is processed
            except urllib2.HTTPError, e:
                if e.code == 403:
                    result = -1
                else:
                    result = None
            except:
                result = None

            if result == -1:
                print "Waiting %s --> %s" % (self.num, nurl)
                time.sleep(WAIT_TIME)
        return result


    def _headers(self):
        "Returns HTTP headers"
        #headers = {
        #    "User-Agent":       "python-util",
        #    "Accept-Encoding":  "gzip"
        #}
        
        # Browser headers
        headers = {
            "Connection":       "keep-alive",
            "Cache-Control":    "max-age=0",
            "User-Agent":       "Mozilla/5.0 (X11; Linux i686) AppleWebKit/534.24 (KHTML, like Gecko) Chrome/11.0.696.71 Safari/534.24",
            "Accept":           "application/xml,application/xhtml+xml,text/html;q=0.9,text/plain;q=0.8,image/png,*/*;q=0.5",
            "Accept-Encoding":  "gzip",
            "Accept-Language":  "en-US,en;q=0.8",
            "Accept-Charset":   "ISO-8859-1,utf-8;q=0.7,*;q=0.3"
        }
        return headers


    def _decompress(self, s):
        "Decompresses string"
        sio     = StringIO(s)
        file    = GzipFile(fileobj=sio)
        return file.read()

    def traverse(self, url):
        "Traverses tree of links and populates stations using DFS algorithm"
        if not url or (self.numTotal and self.numTotal<self.num):
            return
        print url
        items   = self.make_call(url=url)
        (audios, links) = self._separate(items)
        for item in audios:    # check audio links first: playable content
            print item
            if item.has_key("guide_id") and \
               not self._stations.has_key(item.get("guide_id")):  # ignore duplicates
                print (item) 
                self._stations[item.get("guide_id")]    = self.to_station(item) # set station
                self.num += 1
                print (self._stations)
                if self.numTotal and self.numTotal<self.num:
                    return
        
        for item in links:      # check links
            self.traverse(item.get("URL"))

    def traverseAlexa(self, url):
        "Traverses tree of links and populates stations using DFS algorithm"
        items   = self.make_call(url=url)
        (audios, links) = self._separate(items)
        for item in audios:    # check audio links first: playable content
            print item
            if item.has_key("guide_id"): 
                return item.get("url")

        for item in links:      # check links
            self.traverseAlexa(item.get("url"))

    def _separate(self, items):
        "Flattens children outline elements and returns audio and link outline separately"
        audios  = []
        links   = []
        self._traverse_outline(items, audios, links)
        return (audios, links)


    def _traverse_outline(self, items, audios, links):
        "Traverses children outline elements and populate audios and links lists"
        if not items:   # No items
            return
        
        for item in items:
            if item.has_key("children") and item.get("children"):
                self._traverse_outline(item.get("children"), audios, links)
            elif item.get("element") == "audio":
                audios.append(item)
            elif item.get("element") == "link":
                links.append(item)
        

    def _set_format(self, url):
        "Makes sure that the render parameter is set"
        return self._set_params(url, {"render": "json"})


    def _set_keys(self, url):
        "Sets partnerId and serial if available"
        try:
            config      = ConfigParser.ConfigParser()
            config.read("config.txt")
            params  = {
                "partnerId": config.get("general", "partnerId"),
                "serial":    config.get("general", "serial")
            }
            return self._set_params(url, params)
        except:
            return url  # No change


    def _set_params(self, url, params):
        "Adds parameters to url"
        # TODO: Update param if it already exists: use re module
        if not params or not isinstance(params, dict):
            return url  # original url

        newurl  = url
        for (k, v) in params.items():
            if not v:   # skip empty param
                continue
            r   = url.find("%s=" % k)
            if r != -1:     # parameter exists
                continue
            sep     = self._get_separator(newurl)
            newurl  += sep+"%s=%s" % (k, v)
        return newurl
    

    def _get_separator(self, url):
        "Returns ? or & to attach to url"
        rr  = url.find("?")
        if rr == -1:    # question mark not found
            return "?"
        return "&"


    def get_lang(self):
        "Returns list of languages: {<language code>: <language name>}"
        return self._get_items(self._lang, {"c": "languages"}, DESCRIBE)


    def get_genres(self):
        "Returns list of genres {<genre code>: <genre name>}"
        return self._get_items(self._genres, {"c": "genres"}, DESCRIBE)


    def get_countries(self):
        "Returns list of counties {<country code>: <country name>}"
        return self._get_items(self._countries, {"c": "countries"}, DESCRIBE)
        

    def _get_items(self, items, params, ext):
        url = self._get_url(params=params, ext=ext)
        result  = self.make_call(url=url)
        if not isinstance(items, dict) or not isinstance(result, list): # nothing to set
            return {}
        for item in result:
            items[item.get("guide_id")] = item.get("text")
        return items


    def dig_stations_lang(self, filename=None, lang_tuple=None):
        "Diggs for stations with language filters"
        if lang_tuple:
            filters = [lang_tuple]  # one language
        else:
            langjs  = self.get_lang() # all languages
            filters = self.sorted_tuple(langjs)
        self._dig_stations(filters, {"c": "lang"}, filename)


    def _dig_stations(self, filters, params, filename=None):
        url = self._get_url(params)
        stations    = {}
        for f in filters:     # Go over all filters
            if not len(f) == 2: # should have size = 2
                continue
            self.num    = 0
            self._stations  = {}
            furl = self._set_params(url, {"filter": f[0]}) # adds filter
            self.traverse(furl)
            stations[f[0]] = {"name": f[1], "stations": self._stations}
            print "Finished: %s, total: %s" % (f[1], self.num) # progress status
            
        self.dump_object(stations, filename)


    def _get_url(self, params, ext=BROWSE):
        # Example url: "http://opml.radiotime.com/Browse.ashx?partnerId=<partner_id>&serial=<serial>&c=lang"
        url = "%s/%s" % (ENDPOINT, ext)
        url = self._set_keys(url)
        return self._set_params(url, params)


    def stations(self):
        return self._stations


    def to_station(self, station):
        "Populates station values"
        if not isinstance(station, dict):   # Not dictionary
            return
        params  = {
            "name":     station.get("text"),
            "description":  station.get("subtext"),
            "url":      station.get("url"),
            "image":    station.get("image"),
            "genre":    station.get("genre_id")
        }
        return params


    def sorted_tuple(self, d):
        "Takes dictionary and creates list of tuples sorted by second element in the tuple"
        if not isinstance(d, dict):
            return None
        list_tuple  = d.items()
        return sorted(list_tuple, key=lambda item: item[1])


    def dump_object(self, obj, filename=None):
        "Dumps python object (dict) to json format"
        if filename and isinstance(filename, str):
            open(filename, "w").write(json.dumps(obj))
        else:
            print obj


def dig_station_lang(n):
    sd      = StationDigger()
    langjs  = json.load(open("generated/lang.json"))  # dict
    lang    = sd.sorted_tuple(langjs)
    lang_tuple  = lang[n]
    sd.dig_stations_lang("stations/lang%s.json" % n, lang_tuple=lang_tuple)


def dig_stations():
    "Collect stations from all languages"
    sd      = StationDigger()
    langjs  = json.load(open("generated/lang.json"))
    lang    = sd.sorted_tuple(langjs)
    for n in range(len(lang)):
        sd.dig_stations_lang("stations/lang%s.json" % n, lang_tuple=lang[n])


def dump_objects():
    "Generate language, genre and country dictionaries"
    sd      = StationDigger()
    lang    = sd.get_lang()     # lang
    sd.dump_object(lang, "lang.json")

    genres  = sd.get_genres()   # genres
    sd.dump_object(genres, "genres.json")

    countries = sd.get_countries()   # countries
    sd.dump_object(countries, "countries.json")


if __name__ == "__main__":
    dig_station_lang(4)

