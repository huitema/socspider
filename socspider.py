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
#   This is not implemented yet. The API URL are defined as:
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
import datetime


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
        if instance_url != self.instance_url or acct != self.acct:
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
    def __init__(self, uri, toot_id, acct, source_id, local_instance, local_id, from_thread, favor, related):
        self.toot_id = toot_id
        self.source_id = source_id
        self.acct = acct
        self.uri = uri
        self.local_instance = local_instance
        self.local_id = local_id
        self.from_thread = from_thread
        self.favor = favor
        self.related = related

    def get_instance_url(self):
        url = ""
        if self.uri.startswith("https://"):
            parts = self.uri[8:].split("/")
            url = "https://" + parts[0]
        return(url)

    def save(self, F):
        F.write("{ \"uri\": \"" + self.uri + "\"")
        F.write(", \"acct\": \"" + self.acct + "\"")
        F.write(", \"toot_id\": \"" + self.toot_id + "\"")
        if self.source_id != "":
            F.write(", \"source_id\": \"" + self.source_id + "\"")
        if self.local_instance != "":
            F.write(", \"local_instance\": \"" + self.local_instance + "\"")
        if self.local_id != "":
            F.write(", \"local_id\": \"" + self.local_id + "\"")
        if self.from_thread:
            F.write(", \"from_thread\": \"" + "True" + "\"")
        if self.favor > 0:
            F.write(", \"favor\": \"" + str(self.favor) + "\"")
        if self.related > 0:
            F.write(", \"related\": \"" + str(self.related) + "\"")
        F.write("}")

    def from_json(jtoot):
        try:
            uri = jtoot["uri"]
            acct = jtoot["acct"]
            toot_id = jtoot["toot_id"]
            source_id = ""
            if "source_id" in jtoot:
                source_id = jtoot["source_id"]
            local_instance = ""
            if "local_instance" in jtoot:
                local_instance = jtoot["local_instance"]
            local_id = ""
            if "local_id" in jtoot:
                local_id = jtoot["local_id"]
            from_thread = False
            if "from_thread" in jtoot:
                from_thread = (jtoot["from_thread"] == "True")
            favor = 0
            if "favor" in jtoot:
                try:
                    favor = int(jtoot["favor"])
                except:
                    print("Loading toot: " + uri + ", bad favor: " + jtoot["favor"])
            related = 0
            if "related" in jtoot:
                try:
                    related = int(jtoot["related"])
                except:
                    print("Loading toot: " + uri + ", bad related: " + jtoot["related"])

            if "from_thread" in jtoot:
                from_thread = (jtoot["from_thread"] == "True")
            toot = socToot(uri, toot_id, acct, source_id, local_instance, local_id, from_thread, favor, related)
            return(toot)
        except Exception as e:
            print("Cannot load toot Json.")
            traceback.print_exc()
            print("\nException: " + str(e))
        return(None)

class socInstance:
    def __init__(self, url):
        self.url = url
        self.try_after = datetime.datetime(1900, 1, 1)
        self.got_back_on = True
        self.failures = 0
    def is_failing(self):
        return self.try_after > datetime.datetime.now()
    def just_failed(self):
        # We count the number of consecutive failures, or the
        # number of sucesses after a failure, so the time delta can be made
        self.got_back_on = False
        # progressively larger if failures persist
        self.failures += 1
        self.try_after = datetime.datetime.now() + datetime.timedelta(seconds=30*self.failures)
    def back_on(self):
        if not self.got_back_on:
            print(self.url + " back on after " + str(self.failures) + " failures.")
        self.got_back_on = True
        self.failures = 0

class socSpider:
    def __init__(self):
        # instance list: set of instances that have already been explored
        self.instance_list = dict()
        # user list: list of users that we know about and have explored.
        self.user_list = dict()
        # toot_seen: set of toots that have already been processed
        self.toot_list = dict()
        # toot_todo: list of toots that should be processed.
        self.toot_todo = []
        self.nb_seen_by = 0
        self.nb_user_full = 0
        # Journal classes: entries that have been touched in the current run
        # TODO: this is work in progress, to enable saving journals instead
        # of serving state. In 
        self.instance_touch = set()
        self.user_touch = set()
        self.toot_touch = set()

    def learnInstance(self, instance_url):
        if not instance_url in self.instance_list:
            instance = socInstance(instance_url)
            self.instance_list[instance_url] = instance
            self.instance_touch.add(instance_url)

    def learnAccount(self, instance_url, acct, acct_id):
        key = instance_url+"/"+acct
        if key in self.user_list:
            usr = self.user_list[key]
        else:
            usr = socUser(instance_url, acct, acct_id)
            self.user_list[key]=usr
            self.learnInstance(instance_url)
            self.user_touch.add(key)
        if acct_id != "" and usr.acct_id == "":
            usr.acct_id = acct_id
            self.nb_user_full += 1
            self.user_touch.add(key)
        return usr

    def learnSeenBy(self, instance_url, acct, seen_by_instance, seen_by_acct):
        usr = self.learnAccount(instance_url, acct, "")
        n = usr.add_seen_by(seen_by_instance, seen_by_acct)
        if n > 0:
            self.nb_seen_by += n
            self.user_touch.add(usr.instance_url+"/"+usr.acct)

    def learnToot(self, uri, toot_id, acct, local_instance, local_id, from_thread, favor, related):
        if not uri in self.toot_list:
            toot = socToot(uri, toot_id, acct, "", local_instance, local_id, from_thread, favor, related)
            self.toot_list[uri]=toot
            self.toot_touch.add(uri)
            self.toot_todo.append(uri)
            self.learnInstance(toot.get_instance_url())
        elif from_thread:
            self.from_thread = True

    def findAcctOrigin(self, acct_data, local_instance):
        ok = False
        usr = None
        if 'acct' in acct_data:
            ok = True
            acct_parts = acct_data['acct'].split('@')
            acct = '@' + acct_parts[0]
            acct_id = ""
            if len(acct_parts) == 2:
                instance_url = "https://" + acct_parts[1]
            else:
                instance_url = local_instance
            if  instance_url == local_instance and "id" in acct_data:
                acct_id = acct_data["id"]
            usr = self.learnAccount(instance_url, acct, acct_id)
        return ok, usr

    def findTootOrigin(self, tjsn, local_instance):
        ok = False
        usr = None
        if "account" in tjsn:
            ok, usr = self.findAcctOrigin(tjsn["account"], local_instance)
        return ok, usr

    def processTootListEntry(self, tjsn, local_instance, seen_by_instance, seen_by_acct, from_thread):
        is_reblog = False
        toot_id = ""
        toot_uri = ""
        usr = None
        ok = False
        # First, retrieve the source instance and the unique identifier of the toot,
        # from the URI component. This is the toot ID. Not having one is fatal.
        if 'uri' in tjsn:
            toot_uri = tjsn["uri"]
            if toot_uri.startswith("https://"):
                parts = toot_uri[8:].split('/')
                if len(parts) > 2:
                    toot_id = parts[-1]
                    ok = True
            # Then, identify the origin of the toot
            if ok:
                # TODO: consider same instance if instance_url == local_instance
                ok, usr = self.findTootOrigin(tjsn, local_instance)
                if not ok:
                    print("Cannot find origin for toot: " + toot_uri)
            # Process the toot
            if ok:
                if toot_id == "activity":
                    # This happens if this is a "reblog"
                    if 'reblog' in tjsn:
                        is_reblog = True
                        if seen_by_acct != "" and seen_by_instance != "":
                            self.learnSeenBy(usr.instance_url, usr.acct, seen_by_instance, seen_by_acct)
                        self.processTootListEntry(tjsn['reblog'], local_instance, usr.instance_url, usr.acct, False)
                else:
                    # This is a regular toot.
                    local_id = ""
                    if 'id' in tjsn:
                        local_id = tjsn['id']
                    favor = 0
                    if "favourited" in tjsn:
                        try:
                            favor = int(tjsn["favourited"])
                        except:
                            print("Bad format for " + toot_uri + ", favourited = " + tjsn["favourited"])
                            favor = 0
                    related = 0
                    if "replies_count" in tjsn:
                        try:
                            related = int(tjsn["replies_count"])
                        except:
                            print("Bad format for " + toot_uri + ", replies_count = " + tjsn["replies_count"])
                            related = 0
                    if related == 0 and "in_reply_to_id" in tjsn and tjsn["in_reply_to_id"] != None:
                        related += 1

                    # TODO: record whether the toot comes from a Pleroma server?
                    self.learnToot(toot_uri, toot_id, usr.acct, local_instance, local_id, from_thread, favor, related)
                    if seen_by_acct != "" and seen_by_instance != "":
                        self.learnSeenBy(usr.instance_url, usr.acct, seen_by_instance, seen_by_acct)

    def processTootList(self, jresp, local_instance, seen_by_instance, seen_by_acct, from_thread):
        for tjsn in jresp:
            self.processTootListEntry(tjsn, local_instance, seen_by_instance, seen_by_acct, from_thread)

    def processTootId(self, key):
        # first get the toot itself, and process it
        if not key in self.toot_list:
            print("Bad toot key: " + key)
            traceback.print_stack()
            exit(0)
        toot = self.toot_list[key]
        ok = False
        usr = None
        toot_instance = toot.get_instance_url()
        acct_key = toot_instance + '/' + toot.acct
        if toot_instance in self.instance_list and self.instance_list[toot_instance].is_failing():
            # Recent connection to this server broke, so do not retry it yet
            print("Wait before retrying: " + toot_instance)
            ok = False
        elif not toot.toot_id.isdigit():
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
            api_key = toot_instance + '/api/v1/statuses/'
            if toot.toot_id.isdigit():
                api_key += toot.toot_id
            else:
                api_key += "?" + toot.toot_id
            ok,jresp = restApi(api_key)
            if ok:
                # if we did get a clean copy, retrieve the origin ID, etc.
                origin_ok, usr = self.findTootOrigin(jresp, toot_instance)
                if origin_ok :
                    if toot_instance in self.instance_list:
                        self.instance_list[toot_instance].back_on()
                    # attach source to toot
                    toot.source_id = usr.acct_id
                else:
                    print("Cannot find account for " + api_key)
                    ok = False
            else:
                if toot_instance in self.instance_list:
                    self.instance_list[toot_instance].just_failed()
        else:
            # The origin is already known. Just keep the corresponding data
            ok = True
            usr = self.user_list[acct_key]

            
        # The previous test determined whether it is possible to directly
        # access the origin of a toot. If that is not possible, we shall instead 
        # try to access the cache copy at the instance that saw it first.
        local_instance = toot_instance
        local_id = toot.toot_id
        if not ok and toot.local_instance != "" and toot.local_instance != toot_instance and toot.local_id != "":
            local_instance = toot.local_instance
            local_id = toot.local_id
            if usr == None and acct_key in self.user_list:
                usr = self.user_list[acct_key]
                ok = usr != None

        # if the toot is marked has being favourited, run a query.
        if ok and not toot.favor > 0:
            #   url = instance_url + '/api/v1/statuses/' + toot_id + "/favourited_by"
            url = local_instance + '/api/v1/statuses/' + local_id + "/favourited_by"
            fav_ok, fav_js = restApi(url)
            if not fav_ok:
                if local_instance in self.instance_list:
                    self.instance_list[local_instance].just_failed()
                if local_instance == toot_instance and toot.local_instance != "" and toot.local_instance != toot_instance and toot.local_id != "":
                    # Switch to toot local instance to avoid repeated failure
                    local_instance = toot.local_instance
                    local_id = toot.local_id
                else:
                    ok = False
            else:
                if local_instance in self.instance_list:
                    self.instance_list[local_instance].back_on()
                # Process the list of accounts returned as favoriting
                for acct_js in fav_js:
                    one_fav_ok, favor_usr = self.findAcctOrigin(acct_js, local_instance)
                    if one_fav_ok:
                        self.learnSeenBy(toot_instance, toot.acct, favor_usr.instance_url, favor_usr.acct)
        # Access the context of the toot to obtain all the toots in the same thread,
        # but only do that if the toot was not discovered by downloading a thread.
        if ok and not toot.from_thread and toot.related > 0:
            # Get the toot's context
            # TODO: process the boost and favor lists
            url = local_instance + '/api/v1/statuses/' + local_id + "/context"
            original_usr = usr
            ctx_ok, ctx_js = restApi(url)
            if ctx_ok:
                if local_instance in self.instance_list:
                    self.instance_list[local_instance].back_on()
            else:
                if local_instance != toot_instance:
                    # Alarm for failures caused by a local retry
                    print("Failure after trying " + url + " for toot " + toot.uri)
                if local_instance in self.instance_list:
                    self.instance_list[local_instance].just_failed()
            if ctx_ok and 'ancestors' in ctx_js and len(ctx_js['ancestors']) > 0:
                # Retrieve the first ancestor, which is the original poster of the thread.
                ancestors = ctx_js['ancestors']
                ctx_ok, original_usr = self.findTootOrigin(ancestors[0], toot_instance)
                if (ctx_ok):
                    self.processTootListEntry(ancestors[0], local_instance, toot_instance, toot.acct, True)
                    if len(ancestors) > 1:
                        # Record all replies to the thread as seen by original poster
                        self.processTootList(ancestors[1:], local_instance, original_usr.instance_url, original_usr.acct, True)
                else:
                    print("Cannot find origin of ancestor" + toot.uri)
                    ctx_ok = False
            if ctx_ok and 'descendants' in ctx_js:
                # Record all replies to the thread as seen by original poster
                self.processTootList(ctx_js['descendants'], local_instance, original_usr.instance_url, original_usr.acct, True)

    def processInstance(self, instance_url):
        url = instance_url + "/api/v1/timelines/public?limit=20"
        success,jresp = restApi(url)
        if success:
            if instance_url in self.instance_list:
                self.instance_list[instance_url].back_on()
            self.processTootList(jresp, instance_url, instance_url, "", False)
        else:
            if instance_url in self.instance_list:
                self.instance_list[instance_url].just_failed()

    def processAccount(self, usr):
        url = usr.instance_url + '/api/v1/accounts/' + usr.acct_id + '/statuses?limit=20'
        success,jresp = restApi(url)
        if success:
            if usr.instance_url in self.instance_list:
                self.instance_list[usr.instance_url].back_on()
            self.processTootList(jresp, usr.instance_url, usr.instance_url, usr.acct, False)
        else:
            if usr.instance_url in self.instance_list:
                self.instance_list[usr.instance_url].just_failed()

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
            if usr.acct_id != "" and not self.instance_list[usr.instance_url].is_failing():
                success = True
                print("Found " + acct_key + " after " + str(i+1) + " random picks.")
                self.processAccount(self.user_list[acct_key])
                break
        if not success:
            print("Cannot find a suitable account after 10 trials")
        return(success)

    def processRandomInstance(self):
        success = False
        instance_url = ""
        for i in range(0,10):
            instance_url = random.choice(list(self.instance_list))
            if not self.instance_list[instance_url].is_failing():
                break
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
        F.write("    \"users\":[")
        for key in self.user_list:
            if not is_first:
                F.write(",")
            is_first = False
            F.write("\n        ")
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
                for instance_url in jfile["instances"]:
                    if not instance_url in self.instance_list:
                        self.instance_list[instance_url] = socInstance(instance_url)
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
                        key = toot.uri
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

    # Parallel processing.
    # If there are enough "todo toots" available, we can "split the load" by
    # splitting the toot_todo list in N buckets, then have each bucket resolved in a
    # parallel process. Once all buckets are done, we can merge the results. One
    # simple way would be to save each thread using the gloabl "save", gather all
    # the files, and load them all. That would work, but it is rather inefficient
    # because the whole files are megabytes, but the added content is just kilebytes.
    # Another option is to maintain a "journal" of changes, and only load that.
    # An even simpler option might be to keep the indices of the toots, users
    # and instances that were affected, and just save and load that.
    def save_touched_instances(self, F):
        F.write("    \"instances\": [")
        is_first = True
        for key in self.intance_touch:
            if not is_first:
                F.write(",")
            is_first = False
            F.write("\n        \"" + key + "\"")
        F.write("]")

    def save_touched_users(self, F):
        F.write("    \"users\": [")
        is_first = True
        for key in self.user_touch:
            if not is_first:
                F.write(",")
            is_first = False
            F.write("\n        ")
            self.user[key].save(F)
        F.write("]")

    def save_touched(self, delta_file):
        try:
            with open(delta_file, "wt",  encoding='utf-8') as F:
                F.write("{")
                self.save_touched_instances(F)
                F.write(",\n")
                self.save_touched_users(F)
                F.write(",\n")
                self.save_toots(F)
                F.write(",\n")
                self.save_toots_todo(F)
                F.write("}\n")
        except Exception as e:
            print("Cannot open: " + spider_data_file)
            traceback.print_exc()
            print("\nException: " + str(e))

    def parallel_loop(file_prefix):
        # Find the number of processors.
        # Assign todo ranges to each thread.
        # Start each thread.
        # When the thread start, replace the toot_todo list by the selected
        # subset for the thread.
        # Perform the loop in each thread.
        # Save the journal.
        # in the main thread, load the saved data on top of the existing data.
        pass 

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


