# Socspider Algorithm

## The Data

The spider maintains three lists:

* discovered instances, each identified by a URL such as `https://example.social`

* discovered users, each identified by a handle such as `https://example.social/@example`

* discovered toots, each identified by the toot's URI, such as `https://example.social/users/example/statuses/12345678901234567`.
  Different server implementations use different syntaxes for that URI, but they must all guarantee that the URI is unique to that toot.

The spider tries to discover for each user the unique `acct_id` allocated by that user's server,
and required for using the `account` API on the user's Mastodon server. This is found in
the "acct_id" property of the "account" element in the toot's data, but there is a catch.
On most server, the value of that element is set to the identifier of the account in the
local cache. To get the correct value, the spider needs to read the description of the

The spider will also try to discover all the accounts by which another user is seen. That
property is derived from data available in the "context" variant of "statuses" API, which
provides all the replies to a particular toot. Anyone is guaranteed to have seen the
original toot, which most likely indicates that the replier somehow "follows" the original
poster. We can also derive that information from the "last toots" variants of the
"account" API, which lists toots found in a user's feed -- if they are found there,
it means that the account owner somehow followed their publisher.

## Discovering and processing toots

The spider discover toots in three ways:

* by looking at the "last toots" on a server, using the "last toots" variant of the
  server API,
* by looking at the "last toots" on an account, using the "last toots" variant of the
  account API. (That API can only be used on that account's server)
* by looking at the thread to which a toot belongs, using the "context" variant of the
  "statuses" API. That API can be invoked on any server that has a cached copy of
  the thread.

Toots that have been discovered but are not yet "processed" are placed in a "todo" list.
The server may try to download the "reference" version of the toot if the account ID
of the sender is not yet known -- this will enable later use of the account API. The
server will then try to use the "context" variant of the statuses API to get all the
toots in the thread.
TODO: consider using the "favourited" and "boosted" APIs
TODO: consider sorting the pending toots by instance, so a presistent TCP/TLS
connection can be used for a series of requests.

When all discovered toots have been processed, the server picks one of the discovered
accounts at random, and reads the last toots received by that account. If no account
is available, the server picks one of the discovered instances at random, and reads
the last toots received by that instance.

## Handling unresponsive servers

Servers can fail to respond to query for a variety of reasons. For the spider, the
worst error happens when the server is overloaded and the query times out. This blocks
the discovery thread. In theory, the python API allows us to set a 5 second limit, which
limits the amount of disruption, but even that is not ideal. Besides, if a server
is indeed overloaded, the nice thing to do is avoid loading it more.