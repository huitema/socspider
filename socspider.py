#!/usr/bin/python
# coding=utf-8
#
# Explore getting data from Mastodon, using only the public API
#
# With the public API, we can:
#
# - With an instance name, get a list of toots from the public timeline of an instance.
# - With a full toot ID, get the reference data for the toot. This will retrieve
#   the proper value for the "account" item inside the toot data, including
#   the account ID, and create account object and instance object if not
#   already created.
# - With a full toot ID, get the "context" of a toot. If the toot is part of
#   a thread, this provides information on all the "response" toots. There is
#   lots of data associated to each response, but the "account" data appears
#   to be specific to the local instance. For the toot itself, we are also seeing
#   some kind of local cache; only the "uri" property can be trusted. Each reply
#   in the list will thus only create a skeleton toot object, with the toot ID
#   derived from the URI, and an "in-reply-to" field. These objects are placed
#   in a "todo" list pending exploitation.
# - With a toot ID, get the list of who boosted it.
# - with a toot ID, get the list of who favorited it.
# - Most results provide the user ID in "logical" format, such as
#   "huitema@social.secret-wg.org". This can be used to
#   build the "social graph", but the account based API also needs the
#   numerical ID of the account in its server. One way to find that is to
#   get the reference data on a toot sent by the user. (There may be other
#   public API, but I have not found them.)
# - With an account ID, get the "last statuses", i.e., the last toots sent
#   by that user. This can then be used to build a database of toots, or
#   with the "status context" API to analyse other toots part of the same
#   threads.
# The following API are documented but do not appear to work without 
# credentials:
# - With an account ID, get the list of ID that that this one "follows"
#   or is "following".
# On servers using Pleroma, all the API appear to require some form of 
# authentication. This means users can only be discovered by looking
# at copies of toots made available by other servers.
#
# Protecting these API prevents from directly reading the social graph,
# but the graph can still be inferred from the metadata in the
# messages, such as message author, boosted by, or favorited by.
#
# This demo program will start from a URL: instance, toot or account. It
# will then accumulate a desired number of user ID, and toot ID. The main
# goal is to visually demonstrate that mastodon's public information
# is public. And maybe get us thinking about possible protections.
# 
from asyncio.windows_events import NULL
from xml.dom import UserDataHandler
import requests
import json
import sys

def restApi(url):
    success = False
    response = requests.get(url= url)
    if response.status_code == 200:
        success = True
        jresp = json.loads(response.text)
    else:
        print("Error for " + url + ": " + str(response.status_code))
        jresp = json.loads("{}")
    return success,jresp

def readTootId(instance_url, toot_id):
    url = instance_url + '/api/v1/statuses/' + toot_id
    return restApi(url)

def readTootIdContext(instance_url, toot_id):
    url = instance_url + '/api/v1/statuses/' + toot_id + "/context"
    return restApi(url)

def getTootBoost(instance_url, toot_id):
    url = instance_url + '/api/v1/statuses/' + toot_id + "/reblogged_by"
    return restApi(url)

def getTootFavor(instance_url, toot_id):
    url = instance_url + '/api/v1/statuses/' + toot_id + "/favourited_by"
    return restApi(url)

def readProfileId(instance_url, acct_id):
    print("instance_url: " + instance_url)
    url = "" + instance_url + '/api/v1/accounts/' + acct_id 
    return restApi(url)

def statusSummaryFromJson(jresp):
    display_name = ""
    account = "???"
    created_at = "???"
    content = "???"
    m_id = "???"
    if "account" in jresp:
        account = jresp["acct"]
        if "display_name" in acct:
            display_name = account["display_name"]
        if "acct" in acct:
            acct = account["acct"]
        if "id" in acct:
            m_id = account["id"]
    if "created_at" in jresp:
        created_at = jresp["created_at"]
    if "content" in jresp:
        content = jresp["content"]
    display = display_name + " (" + m_id + ", " + acct + "), " + created_at + ":\n" + content + "\n"
    return display

def getStatuses(instance_url, m_id):
    url = instance_url + '/api/v1/accounts/' + m_id + "/statuses"
    return restApi(url)

def getFollow(instance_url, m_id):
    url = instance_url + '/api/v1/accounts/' + m_id + "/follow"
    return restApi(url)

def getPublicToots(instance_url, limit=20):
    url = instance_url + "/api/v1/timelines/public?limit=" + str(limit)
    return restApi(url)

def mastodon_url(url):
    ok = False
    instance_url = ""
    user = ""
    m_id = ""
    if url.startswith("https://"):
        url1 = url[8:]
        parts = url1.split("/")
        if len(parts) == 3:
            instance_url = "https://" + parts[0]
            user = parts[1]
            m_id = parts[2]
            ok = True
        else:
            print("Only " + str(len(parts)) + " parts in " + url1)
    else:
        print("url " + url + " does not start with https://")
    return ok, instance_url, user, m_id


# User, toot and spider classes
#
# The purpose of this spider is to explore the social graph, using
# relations learned from tooth. The spider will store this relation
# in a dictionary of users, with a key user of <instance_url>"/"<acct_id>.
# Inside the user object we find the set of follower and a set of
# follow, in each each entry is represented by its key.

class socUser:
    def __init__(self, instance_url, acct, acct_id):
        self.instance_url = instance_url
        self.acct = acct
        self.acct_id = acct_id
        self.follow = set()
        self.follower = set()
    def add_follow(self, instance_url, acct):
        key = instance_url + "/" + acct
        if not key in self.follow:
            self.follow.add(key)
    def add_follower(self, instance_url, acct):
        key = instance_url + "/" + acct
        if not key in self.follower:
            self.follower.add(key)

class socToot:
    def __init__(self, instance_url, toot_id, acct, source_id):
        self.instance_url = instance_url
        self.toot_id = toot_id
        self.source_id = source_id
        self.acct = acct
        self.follow = set()

class socSpider:
    def __init__(self):
        # instance list: set of instances that have already been explored
        self.instance_list = set()
        # instance toto: set of instances that should be explored.
        self.instance_todo = []
        # user list: list of users that we know about and have explored.
        self.user_list = dict()
        # user_todo: list of users that we know about, but are not explored yet
        self.user_todo = []
        # toot_seen: set of toots that have already been processed
        self.toot_list = dict()
        # toot_todo: list of toots that should be processed.
        self.toot_todo = []

    def learnInstance(self, instance_url):
        if not instance_url in self.instance_list:
            print("Learning instance: " + instance_url)
            self.instance_list.add(instance_url)
            self.instance_todo.append(instance_url)

    def learnAccount(self, instance_url, account, acct_id):
        key = instance_url+"/"+account
        if key in self.user_list:
            usr = self.user_list[key]
        else:
            usr = socUser(instance_url, account, acct_id)
            self.user_list[key]=usr
            self.learnInstance(instance_url)
            print("Learning account: " + key)
        if acct_id != "" and usr.acct_id == "":
            usr.acct_id = acct_id
            if not key in self.user_todo:
                self.user_todo.append(key)
                print("Scheduled account " + key + " for processing.")
        return usr
            
    def learnToot(self, instance_url, acct, toot_id):
        key = instance_url+"/"+toot_id
        if not key in self.toot_list:
            toot = socToot(instance_url, toot_id, acct, "")
            self.toot_list[key]=toot
            self.toot_todo.append(key)
            self.learnInstance(instance_url)

    def processAccountData(self, jresp, same_instance):
        ok = False
        usr = None
        if "url" in jresp:
            # get host ID from url
            usr_url = jresp["url"]
            acct_id = ""
            if same_instance and "id" in jresp:
                acct_id = jresp["id"]

            if usr_url.startswith("https://"):
                parts = usr_url[8:].split('/')
                if len(parts) == 2:
                    instance_url = "https://" + parts[0]
                    acct = parts[1]
                    ok = True
                    usr = self.learnAccount(instance_url, acct, acct_id)
            if not ok:
                print("Cannot parse usr url: " + usr_url)
        return ok, usr

    def processTootId(self, key):
        # first get the toot itself, and process it
        toot = self.toot_list[key]
        ok = False
        usr = None
        acct_key = toot.instance_url + '/' + toot.acct
        if toot.source_id == "" or not acct_key in self.user_list:
            # The syntax of the statuses API differs for Mastodon
            # and Pleroma. If the toot_id looks like an integer, we should
            # use the Mastodon syntax, if it contains at least one hyphen,
            # the pleroma sntax.
            api_key = toot.instance_url + '/api/v1/statuses/'
            if toot.toot_id.isdigit():
                api_key += toot.toot_id
            else:
                api_key += "?" + toot.toot_id
            success,jresp = restApi(api_key)
            if success:
                if 'account' in jresp:
                    ok, usr = self.processAccountData(jresp['account'], True)
                    if ok:
                        # attach source to toot
                        toot.source_id = usr.acct_id
                if not ok:
                    print("Cannot find account for " + api_key)
        else:
            ok = True
            usr = self.user_list[acct_key]

        if ok:
            # process the boost and favor lists
            # then get the toot context
            url = toot.instance_url + '/api/v1/statuses/' + toot.toot_id + "/context"
            ctx_ok, ctx_js = restApi(url)
            if ctx_ok:
                self.processTootList(ctx_js)

    def processTootListEntry(self, tjsn):
        is_reblog = False
        if 'uri' in tjsn:
            toot_uri = tjsn["uri"]
            ok = False
            if toot_uri.startswith("https://"):
                parts = toot_uri[8:].split('/')
                if len(parts) > 2:
                    instance_url = "https://" + parts[0]
                    acct = ""
                    toot_id = parts[-1]
                    if toot_id == "activity":
                        if 'reblog' in tjsn:
                            is_reblog = True
                            self.processTootListEntry(tjsn['reblog'])
                    else:
                        if len(parts) > 4 and parts[-2] == "statuses":
                            acct = "@" + parts[-3]
                            ok = True
                        elif 'account' in tjsn:
                            # Special case of pleroma servers. We can only work
                            # with the reduced complexity list, because the APIs
                            # are not public.
                            acct_data = tjsn['account']
                            if 'acct' in acct_data:
                                acct_parts = acct_data['acct'].split('@')
                                acct = '@' + acct_parts[0]
                                ok = True
                        self.learnToot(instance_url, acct, toot_id)
                        if ok:
                            self.learnAccount(instance_url, acct, "")
            if not ok and not is_reblog:
                print("Cannot parse toot URI: " + toot_uri)

    def processTootList(self, jresp):
        for tjsn in jresp:
            self.processTootListEntry(tjsn)

    def processInstance(self, instance_url):
        url = instance_url + "/api/v1/timelines/public?limit=20"
        success,jresp = restApi(url)
        if success:
            self.processTootList(jresp)

    def processAccount(self, usr):
        url = usr.instance_url + '/api/v1/accounts/' + usr.acct_id + '/statuses?limit=20'
        success,jresp = restApi(url)
        if success:
            self.processTootList(jresp)

    def processPendingToots(self):
        current_list = self.toot_todo
        self.toot_todo = []
        for key in current_list:
            self.processTootId(key)

    def processPendingAccounts(self):
        current_list = self.user_todo
        self.user_todo = []
        for key in current_list:
            usr = self.user_list[key]
            self.processAccount(usr)

    def processPendingInstance(self):
        current_list = self.instance_todo.copy()
        for instance_url in current_list:
            # to do: get public toots
            self.instance_todo.remove(instance_url)

    def loop(self, start='https://mastodon.social/', user_max=200, toot_max=1000):
        self.processInstance(start)
        while len(self.user_list) < user_max or len(self.toot_list) < toot_max:
            spider.processPendingToots()
            spider.processPendingAccounts()
            print("\nFound " + str(len(spider.user_list)) + " users, " + str(len(spider.toot_list)) + " toots.\n")

# main

testing_instance = False
testing_toot_id = False
testing_toot_context = False
testing_statuses = False
testing_boost = False
testing_favor = False
testing_follow = False
testing_profile_id = False
testing_public_time_line = False
testing_usage = False

toot_url = "https://mastodon.gougere.fr/@bortzmeyer/109332158592316612"
user_url = "https://mastodon.gougere.fr/@bortzmeyer/369"
url = "https://mastodon.gougere.fr/@bortzmeyer/109332158592316612"

if len(sys.argv) > 1:
    testing = sys.argv[1]
    if testing == "id":
        testing_toot_id = True
        url = toot_url
    elif testing == "context":
        testing_toot_context = True
        url = toot_url
    elif testing == "profile":
        testing_profile_id = True
        url = user_url
    elif testing == "statuses":
        url = user_url
        testing_statuses = True
    elif testing == "boost":
        url = toot_url
        testing_boost = True
    elif testing == "favor":
        url = toot_url
        testing_favor = True
    elif testing == "follow":
        testing_follow = True
        url = user_url
    elif testing == "public":
        testing_public_time_line = True
        url = toot_url
    elif testing == "instance":
        testing_instance = True
        url = toot_url
    else:
        print("Unknown testing arg: " + testing)
        testing_usage = True
    if len(sys.argv) > 2:
        url = sys.argv[2]
    else:
        print("Using default URL: " + url)
    if len(sys.argv) > 3:
        testing_usage = True
else:
    testing_usage = True

if testing_usage:
    print("Usage: " + sys.argv[0] + " {id|context|profile|follow} [url]")
    exit(1)

ok, instance_url, user, m_id = mastodon_url(url)
if not ok:
    print("Could not parse: {}", url)
    exit(1)
else:
    print("Host: " + instance_url + ", user: " + user + ", id: " + m_id);

if testing_toot_id:
    success, jresp = readTootId(instance_url, m_id)
    print("Success: " + str(success))
    if success:
        print(str(jresp))

if testing_toot_context:
    success, jresp = readTootIdContext(instance_url, m_id)
    print("Success: " + str(success))
    if success:
        if "descendants" in jresp:
            for resp in jresp["descendants"]:
                display_response = statusSummaryFromJson(resp)
                print(display_response)

if testing_boost:
    print("testing boosted by")
    success, jresp = getTootBoost(instance_url, m_id)
    print("Success: " + str(success))
    # returns a list of accounts
    if success:
        print(str(jresp))

if testing_favor:
    print("testing favorited by")
    success, jresp = getTootFavor(instance_url, m_id)
    print("Success: " + str(success))
    # returns a list of accounts
    if success:
        print(str(jresp))

if testing_statuses:
    print("testing read_statuses")
    success, jresp = getStatuses(instance_url, m_id)
    print("Success: " + str(success))
    # return is a list of toots

if testing_follow:
    print("testing read_follow")
    success, jresp = getFollow(instance_url, m_id)
    print("Success: " + str(success))
    # does not succeed -- auth required.
    if success:
        print(str(jresp))

if testing_profile_id:
    print("testing read_profile_ID")
    success, jresp = readProfileId(instance_url, m_id)
    print("Success: " + str(success))
    if success:
        print(str(jresp))

if testing_public_time_line:
    print("testing public time line")
    success, jresp = getPublicToots(instance_url)
    print("Success: " + str(success))
    # return is a list of toots
    if success:
        print(str(jresp))

if testing_instance:
    spider = socSpider()
    spider.loop()
