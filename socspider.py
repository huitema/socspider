#!/usr/bin/python
# coding=utf-8
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
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
# - With a toot ID, get the list of who boosted it, and who favorited it.
#   This is not implemented yet. The API URL are defines as:
#   url = instance_url + '/api/v1/statuses/' + toot_id + "/reblogged_by"
#   url = instance_url + '/api/v1/statuses/' + toot_id + "/favourited_by"
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
#
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

import requests
import json
import sys
import os
import traceback
import random


# Helper function for processing Rest API
# TODO: may want to somehow add a timer.
def restApi(url, timeout=5):
    success = False
    try:
        response = requests.get(url=url, timeout=timeout)
        if response.status_code == 200:
            success = True
            jresp = json.loads(response.text)
        else:
            print("Error for " + url + ": " + str(response.status_code))
            jresp = json.loads("{}")
    except Exception as e:
        print("Cannot process: " + url + ", exception: " + str(e))
        jresp = json.loads("{}")

    return success,jresp

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
        self.seen_by = set()

    def add_seen_by(self, instance_url, acct):
        added = 0
        key = instance_url + "/" + acct
        if not key in self.seen_by:
            self.seen_by.add(key)
            added = 1
        return added

    def save(self, F):
        F.write("{ \"instance\": \"" + self.instance_url + "\"")
        F.write(", \"acct\": \"" + self.acct + "\"")
        if self.acct_id != "":
            F.write(", \"acct_id\": \"" + self.acct_id + "\"")
        if len(self.seen_by) > 0:
            F.write(", \"seen_by\": [")
            is_first = True
            for key in self.seen_by:
                if not is_first:
                    F.write(",")
                is_first = False
                F.write("\n             \"" + key + "\"")
            F.write("]")
        F.write("}")

    def from_json(jusr):
        try:
            instance_url = jusr["instance"]
            acct = jusr["acct"]
            acct_id = ""
            if "acct_id" in jusr:
                acct_id = jusr["acct_id"]
            usr = socUser(instance_url, acct, acct_id)
            if "seen_by" in jusr:
                for key in jusr["seen_by"]:
                    usr.seen_by.add(key)
            return(usr)
        except Exception as e:
            print("Cannot load user Json.")
            traceback.print_exc()
            print("\nException: " + str(e))
        return(None)

class socToot:
    def __init__(self, instance_url, toot_id, acct, source_id):
        self.instance_url = instance_url
        self.toot_id = toot_id
        self.source_id = source_id
        self.acct = acct

    def save(self, F):
        F.write("{ \"instance\": \"" + self.instance_url + "\"")
        F.write(", \"acct\": \"" + self.acct + "\"")
        F.write(", \"toot_id\": \"" + self.toot_id + "\"")
        if self.source_id != "":
            F.write(", \"source_id\": \"" + self.source_id + "\"")
        F.write("}")

    def from_json(jusr):
        try:
            instance_url = jusr["instance"]
            acct = jusr["acct"]
            toot_id = jusr["toot_id"]
            source_id = ""
            if "source_id" in jusr:
                source_id = jusr["source_id"]
            toot = socToot(instance_url,toot_id, acct, source_id)
            return(toot)
        except Exception as e:
            print("Cannot load toot Json.")
            traceback.print_exc()
            print("\nException: " + str(e))
        return(None)

class socSpider:
    def __init__(self):
        # instance list: set of instances that have already been explored
        self.instance_list = set()
        # user list: list of users that we know about and have explored.
        self.user_list = dict()
        # toot_seen: set of toots that have already been processed
        self.toot_list = dict()
        # toot_todo: list of toots that should be processed.
        self.toot_todo = []
        self.nb_seen_by = 0
        self.nb_user_full = 0

    def learnInstance(self, instance_url):
        if not instance_url in self.instance_list:
            self.instance_list.add(instance_url)

    def learnAccount(self, instance_url, acct, acct_id):
        key = instance_url+"/"+acct
        if key in self.user_list:
            usr = self.user_list[key]
        else:
            usr = socUser(instance_url, acct, acct_id)
            self.user_list[key]=usr
            self.learnInstance(instance_url)
        if acct_id != "" and usr.acct_id == "":
            usr.acct_id = acct_id
            self.nb_user_full += 1
        return usr

    def learnSeenBy(self, instance_url, acct, seen_by_instance, seen_by_acct):
        usr = self.learnAccount(instance_url, acct, "")
        self.nb_seen_by += usr.add_seen_by(seen_by_instance, seen_by_acct)

    def learnToot(self, instance_url, toot_id, acct):
        key = instance_url+"/"+toot_id
        if not key in self.toot_list:
            toot = socToot(instance_url, toot_id, acct, "")
            self.toot_list[key]=toot
            self.toot_todo.append(key)
            self.learnInstance(instance_url)

    def findTootOrigin(self, tjsn, current_instance, same_instance):
        ok = False
        usr = None

        if "account" in tjsn:
            acct_data = tjsn["account"]
            if 'acct' in acct_data:
                ok = True
                acct_parts = acct_data['acct'].split('@')
                acct = '@' + acct_parts[0]
                acct_id = ""
                if len(acct_parts) == 2:
                    instance_url = "https://" + acct_parts[1]
                    if instance_url != current_instance:
                        same_instance = False
                else:
                    instance_url = current_instance
                if same_instance and "id" in acct_data:
                    acct_id = acct_data["id"]
                usr = self.learnAccount(instance_url, acct, acct_id)
        return ok, usr

    def processTootListEntry(self, tjsn, local_instance, local_acct, is_same_instance):
        is_reblog = False
        toot_id = ""
        instance_url = ""
        toot_uri = ""
        usr = None
        ok = False
        # First, retrieve the source instance and the unique identifier of the toot,
        # from the URI component.
        if 'uri' in tjsn:
            toot_uri = tjsn["uri"]
            if toot_uri.startswith("https://"):
                parts = toot_uri[8:].split('/')
                if len(parts) > 2:
                    instance_url = "https://" + parts[0]
                    toot_id = parts[-1]
                    ok = True
                    if instance_url != local_instance:
                        is_same_instance = False
        # Then, identify the origin of the toot
        if ok:
            # TODO: consider same instance if instance_url == local_instance
            ok, usr = self.findTootOrigin(tjsn, local_instance, is_same_instance)
            if not ok:
                print("Cannot find origin for toot: " + toot_uri)
        # Process the toot
        if ok:
            if toot_id == "activity":
                # This happens if this is a "reblog"
                if 'reblog' in tjsn:
                    is_reblog = True
                    if local_acct != "" and local_instance != "":
                        self.learnSeenBy(usr.instance_url, usr.acct, local_instance, local_acct)
                    is_same_instance_reblog = is_same_instance
                    if usr.instance_url != local_instance:
                        is_same_instance_reblog = False
                    self.processTootListEntry(tjsn['reblog'], usr.instance_url, usr.acct, is_same_instance_reblog)
            else:
                # This is a regular toot.
                # TODO: record whether the toot comes from a Pleroma server?
                self.learnToot(instance_url, toot_id, usr.acct)
                if local_acct != "" and local_instance != "":
                    self.learnSeenBy(usr.instance_url, usr.acct, local_instance, local_acct)

    def processTootList(self, jresp, local_instance, local_acct, is_same_instance):
        for tjsn in jresp:
            self.processTootListEntry(tjsn, local_instance, local_acct, is_same_instance)

    def processTootId(self, key):
        # first get the toot itself, and process it
        toot = self.toot_list[key]
        ok = False
        usr = None
        acct_key = toot.instance_url + '/' + toot.acct
        if not toot.toot_id.isdigit():
            # Mastodon servers use numeric IDs. Servers running Pleroma
            # use a 128 bit identifier, including hex digits and hyphens.
            # These servers require authentication, which will cause the
            # Rest API call to fail. We fail quickly instead.
            ok = False
        elif toot.source_id == "" or not acct_key in self.user_list:
            # Need to find out the actual ID of the toot's origin.
            # The syntax of the statuses API differs for Mastodon
            # and Pleroma. If the toot_id looks like an integer, we should
            # use the Mastodon syntax, if it contains at least one hyphen,
            # the pleroma syntax.
            # TODO: check whether even querying Pleroma servers is useful.
            api_key = toot.instance_url + '/api/v1/statuses/'
            if toot.toot_id.isdigit():
                api_key += toot.toot_id
            else:
                api_key += "?" + toot.toot_id
            ok,jresp = restApi(api_key)
            if ok:
                # if we did get a clean copy, retrieve the origin ID, etc.
                origin_ok, usr = self.findTootOrigin(jresp, toot.instance_url, True)
                if origin_ok :
                    # attach source to toot
                    toot.source_id = usr.acct_id
                else:
                    print("Cannot find account for " + api_key)
                    ok = False
        else:
            # The origin is already known. Just keep the corresponding data
            ok = True
            usr = self.user_list[acct_key]

        if ok:
            # TODO: process the boost and favor lists
            # then get the toot context
            url = toot.instance_url + '/api/v1/statuses/' + toot.toot_id + "/context"
            ctx_ok, ctx_js = restApi(url)
            if ctx_ok:
                if 'descendants' in ctx_js:
                    self.processTootList(ctx_js['descendants'], toot.instance_url, toot.acct, True)

    def processInstance(self, instance_url):
        url = instance_url + "/api/v1/timelines/public?limit=20"
        success,jresp = restApi(url)
        if success:
            self.processTootList(jresp, instance_url, "", True)

    def processAccount(self, usr):
        url = usr.instance_url + '/api/v1/accounts/' + usr.acct_id + '/statuses?limit=20'
        success,jresp = restApi(url)
        if success:
            self.processTootList(jresp, usr.instance_url, usr.acct, True)

    def processPendingToots(self):
        if len(self.toot_todo) > 100:
            current_list = self.toot_todo[:100]
            self.toot_todo = self.toot_todo[100:]
        else:
            current_list = self.toot_todo
            self.toot_todo = []
        for key in current_list:
            self.processTootId(key)

    def processRandomAccount(self):
        success = False
        for i in range(0,10):
            acct_key = random.choice(list(self.user_list))
            usr = self.user_list[acct_key]
            if usr.acct_id != "":
                success = True
                print("Found " + acct_key + " after " + str(i+1) + " random picks.")
                self.processAccount(self.user_list[acct_key])
                break
        if not success:
            print("Cannot find a suitable account after 10 trials")
        return(success)

    def processRandomInstance(self):
        instance_url = random.choice(list(self.instance_list))
        self.processInstance(instance_url)

    def loop(self, start='https://mastodon.social/', new_users=100, new_toots=1000, loops_max=100):
        nb_loops = 0
        user_max= len(self.user_list) + new_users
        toot_max= len(self.toot_list) + new_toots
        self.learnInstance(start)
        while (len(self.user_list) < user_max or len(self.toot_list) < toot_max) and nb_loops < loops_max:
            nb_loops += 1
            if len(self.toot_todo) > 0:
                print("Processing at most 100 of " + str(len(self.toot_todo)) + " toots.")
                self.processPendingToots()
            else:
                acct_success = False
                if len(self.user_list) > 0:
                    print("Trying to process a random account.")
                    acct_success = self.processRandomAccount()
                if not acct_success:
                    print("Processing a random instance.")
                    self.processRandomInstance()
            print("\nFound " + str(len(self.instance_list)) + " instances, " + \
                str(len(self.user_list)) + " users (" + str(self.nb_user_full) + "), " +  \
                str(self.nb_seen_by) + " seen_by, " + \
                str(len(self.toot_list)) + " toots (" + str(len(self.toot_todo)) + ").")

    def save_instances(self, F):
        is_first = True
        F.write("    \"instances\":[\n")
        for instance_url in self.instance_list:
            if not is_first:
                F.write(",\n")
            is_first = False
            F.write("        \"" + instance_url + "\"")
        F.write("]");

    def save_toots(self, F):
        is_first = True
        F.write("    \"toots\":[\n")
        for key in self.toot_list:
            if not is_first:
                F.write(",\n")
            is_first = False
            F.write("        ")
            self.toot_list[key].save(F)
        F.write("]");

    def save_toots_todo(self, F):
        is_first = True
        F.write("    \"toots_todo\":[")
        for key in self.toot_todo:
            if not is_first:
                F.write(",")
            is_first = False
            F.write("\n        \"" + key + "\"")
        F.write("]");

    def save_users(self, F):
        is_first = True
        F.write("    \"users\":[\n")
        for key in self.user_list:
            if not is_first:
                F.write(",\n")
            is_first = False
            F.write("        ")
            self.user_list[key].save(F)
        F.write("]");

    def save(self, spider_data_file):
        try:
            with open(spider_data_file, "wt",  encoding='utf-8') as F:
                F.write("{")
                self.save_instances(F)
                F.write(",\n")
                self.save_users(F)
                F.write(",\n")
                self.save_toots(F)
                F.write(",\n")
                self.save_toots_todo(F)
                F.write("}\n")
        except Exception as e:
            print("Cannot open: " + spider_data_file)
            traceback.print_exc()
            print("\nException: " + str(e))

    def load(self, spider_data_file):
        try:
            file_contents = ""
            with open(spider_data_file, "rt",  encoding='utf-8') as F:
                file_contents = F.read()
            print("Loaded " + str(len(file_contents)) + " bytes from " + spider_data_file)
            jfile = json.loads(file_contents)
            if "instances" in jfile:
                for key in jfile["instances"]:
                    self.instance_list.add(key)
            if "users" in jfile:
                for jusr in jfile["users"]:
                    usr = socUser.from_json(jusr)
                    if usr != None:
                        key = usr.instance_url + "/" + usr.acct
                        self.user_list[key] = usr
                        self.nb_seen_by += len(usr.seen_by)
                        if usr.acct_id != "":
                            self.nb_user_full += 1
            if "toots" in jfile:
                for jtoot in jfile["toots"]:
                    toot = socToot.from_json(jtoot)
                    if toot != None:
                        key = toot.instance_url + "/" + toot.toot_id
                        self.toot_list[key] = toot
            if "toots_todo" in jfile:
                for key in jfile["toots_todo"]:
                    self.toot_todo.append(key)
        except Exception as e:
            print("Cannot open: " + spider_data_file)
            traceback.print_exc()
            print("\nException: " + str(e))
        print("\nLoaded " + str(len(self.instance_list)) + " instances, " + \
                str(len(self.user_list)) + " users (" + str(self.nb_user_full) + "), " +  \
                str(self.nb_seen_by) + " seen_by, " + \
                str(len(self.toot_list)) + " toots (" + str(len(self.toot_todo)) + ").")
        if len(self.instance_list) == 0:
            print("The JSON file includes the following keys:")
            for key in jfile:
                print(key)
            exit(1)

# main

url = "https://mastodon.social"
if len(sys.argv) > 3 or len(sys.argv) < 2:
    print("Usage: " + sys.argv[0] + "<json data file> [instance url]")
    exit(1)
elif len(sys.argv) == 3:
    url = sys.argv[2]
spider_data_file = sys.argv[1]
spider = socSpider()
if os.path.isfile(spider_data_file):
    spider.load(spider_data_file)
spider.loop(start=url)
spider.save(spider_data_file)


