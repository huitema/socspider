# socspider

This toy python program is demonstrating how to build a "social spider" using the public API of Mastodon.
The program will start by reading toots in the public timeline of a "start" instance, by default
`mastodon.social`. It analyzes the toots to find names of instances and handles of users in the Fediverse,
and an approximation of the social graph, by recording for each discovered user the handles of the
users by which it is seen.

The program is not fast. It takes 2 to 3 minutes on a laptop to learn the profiles of 100 users. It could
take 6 months to process 10 million Mastodon users. But then, the program is not optimized at
all. A lot of time is spent waiting for responses of remote servers. This could be reduced
by running several queries in parallel, in multiple threads. Running on a big 256 core server,
the 10 million accounts mentioned above could be parsed in about 18 hours. Running on a cluster
of machines would be faster still.

The point here is not speed. The point is to demonstrate the power of public API like
"reading the public timeline", "reading the data of a toot", "reading a thread starting
with a toot" or "reading the public messages sent by an account". In the Mastodon
implementation, these APIs are public. (The same API appear to be access controlled in 
servers running Pleroma.)

The power could be used for good or for bad. For example, the spider could be augmented to
also collect hash-tags read by users, or assign weights to the relations between users.
On the good side, this would enable building catalog of servers or dictionaries of users,
or to add a search function to the Fediverse. On the bad side, this is exactly the kind
of data required for "serving better ads", or to find targets of harassment.

## Using the spider

To use the spider, you need to clone this depot, then run:
```
python3 socspider.py <name-of-afile> [start-instance-url]
```
The spidering will start at the designated instance, and will troll the fediverse
until it has learned at least 100 new user handles. The data will be saved in
JSON format in the designated file. 

You can run the program several time. If the data file already exists when the program
is launched, it will be loaded in memory, and the results of the spidering added to
the existing data.

## Participating

If you want to improve this code or otherwise comment on it, feel free to open
an issue of propose a PR here. Or, contact "huitema@social.secret-wg.org" on Mastodon.





