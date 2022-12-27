#!/usr/bin/python
# coding=utf-8
#
# Explore getting data from Mastodon, using only the public API
#
# With the public API, we can:
#
# - With an instance name, get a list of toots from the public timeline of an instance.
# - With a full tooth ID, get the "context" of a toot. If the toot is part of
#   a thread, this provides information on all the "response" toots, including
#   the full account ID of everyone who posted in the thread. 
# - Can also get the "boosted by" information.
# - With an account ID, get the list of ID that that this one "follows"
#   or is "following". Apart from yielding more user ID for further exploration,
#   this also provides a view of the 'social graph'
# - With an account ID, get the "last statuses", i.e., the last toots sent
#   by that user. This can then be used to build a database of toots, or
#   with the "status context" API to analyse other toots part of the same
#   thread.
#
# This demo program will start from a URL: instance, toot or account. It
# will then accumulate a desired number of user ID, and toot ID. The main
# goal is to visually demonstrate that mastodon's public information
# is public. And maybe get us thinking about possible protections.
# 
import requests
import json
import sys

def readTootIdContext(host_instance, toot_id):
    url = host_instance + '/api/v1/statuses/' + toot_id + "/context"
    response = requests.get(url= url)
    success = response.status_code == 200
    if success:
        jresp = json.loads(response.text)
    else:
        print("Error: " + str(response.status_code))
        jresp = json.loads("{}")
    return success,jresp

def readProfileId(host_instance, m_id):
    print("Host_instance: " + host_instance)
    url = "" + host_instance + '/api/v1/accounts/' + m_id 
    response = requests.get(url= url)
    success = response.status_code == 200
    if success:
        jresp = json.loads(response.text)
    else:
        print("Error: " + str(response.status_code))
        jresp = json.loads("{}")
    return success,jresp

def statusSummaryFromJson(jresp):
    display_name = ""
    acct = "???"
    created_at = "???"
    content = "???"
    m_id = "???"
    if "account" in jresp:
        account = jresp["account"]
        if "display_name" in account:
            display_name = account["display_name"]
        if "acct" in account:
            acct = account["acct"]
        if "id" in account:
            m_id = account["id"]
    if "created_at" in jresp:
        created_at = jresp["created_at"]
    if "content" in jresp:
        content = jresp["content"]
    display = display_name + " (" + m_id + ", " + acct + "), " + created_at + ":\n" + content + "\n"
    return display


def followingViaJason(host_instance, m_id):
    url = host_instance + '/api/v1/accounts/' + m_id + "/statuses"
    response = requests.get(url= url)
    success = response.status_code == 200
    if success:
        print(response.text)
        jresp = json.loads(response.text)
    else:
        print("Error: " + str(response.status_code))
        jresp = json.loads("{}")
    return success,jresp

def getPublicToots(host_instance, limit=20):
    url = host_instance + "/api/v1/timelines/public?limit=" + str(limit)
    response = requests.get(url= url)
    success = response.status_code == 200
    if success:
        print(response.text)
        jresp = json.loads(response.text)
    else:
        print("Error: " + str(response.status_code))
        jresp = json.loads("{}")
    return success,jresp

def mastodon_url(url):
    ok = False
    host_instance = ""
    user = ""
    id = ""
    m_id = ""
    if url.startswith("https://"):
        url1 = url[8:]
        parts = url1.split("/")
        if len(parts) == 3:
            host_instance = "https://" + parts[0]
            user = parts[1]
            m_id = parts[2]
            ok = True
        else:
            print("Only " + str(len(parts)) + " parts in " + url1)
    else:
        print("url " + url + " does not start with https://")
    return ok, host_instance, user, m_id


    


# main

testing_read_toot_id = False
testing_read_follow = False
testing_read_profile_id = False
testing_read_public_time_line = False
testing_usage = False
url = "https://mastodon.gougere.fr/@bortzmeyer/109332158592316612"
# url = https://ioc.exchange/@matthew_d_green/109334061497431084
# url = https://social.secret-wg.org/@huitema/108204235195635098

if len(sys.argv) > 1:
    testing = sys.argv[1]
    if testing == "id":
        testing_read_toot_id = True
    elif testing == "profile":
        testing_read_profile_id = True
    elif testing == "follow":
        testing_read_follow = True
    elif testing == "public":
        testing_read_public_time_line = True
    else:
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
    print("Usage: " + sys.argv[0] + " {id|profile|follow} [url]")
    exit(1)

ok, host_instance, user, m_id = mastodon_url(url)
if not ok:
    print("Could not parse: {}", url)
    exit(1)
else:
    print("Host: " + host_instance + ", user: " + user + ", id: " + m_id);

if testing_read_toot_id:
    success, jresp = readTootIdContext(host_instance, m_id)
    print("Success: " + str(success))
    with open("last_id.json", "wt", encoding="UTF-8") as F:
        F.write(str(jresp))
    if success:
        if "descendants" in jresp:
            for resp in jresp["descendants"]:
                display_response = statusSummaryFromJson(resp)
                print(display_response)

if testing_read_follow:
    # id = "369"
    print("testing read_follow")
    success, jresp = followingViaJason(host_instance, m_id)
    print("Success: " + str(success))

if testing_read_profile_id:
    print("testing read_profile_ID")
    success, jresp = readProfileId(host_instance, m_id)
    print("Success: " + str(success))
    if success:
        print(str(jresp))

if testing_read_public_time_line:
    print("testing public time line")
    success, jresp = getPublicToots(host_instance)
    print("Success: " + str(success))
    if success:
        print(str(jresp))