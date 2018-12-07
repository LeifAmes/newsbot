# NewsBot - An IRC bot for reading RSS streams
# Written by Leif Ames  <leif@leifames.com>

import socket, ssl
import feedparser
import datetime, time
import feedparser
from HTMLParser import HTMLParser
import time, datetime
import unicodedata
import re
import random
import json
import os, sys
import hashlib


bot_number = 0
use_ssl = False

# IRC Server
if bot_number == 1:
	server = "irc.eversible.net"
elif bot_number == 2:
	server = "irc.inet.tele.dk"
else:
	server = "irc.efnet.net"

# Nick
if bot_number == 0:
	name = "NewsBot"
else:
	name = "NewsBot%i" % (bot_number)

# Port
if use_ssl:
	port = 6670
else:
	port = 6667

# Channel
channel = "#newsbot"

# Server password
password = ""


# Set up paths
base_path = os.path.join(os.environ['HOME'], "newsbot-v0.1")

feed_file = os.path.join(base_path, 'feeds.json')
user_file = os.path.join(base_path, 'users.json')
server_file = os.path.join(base_path, 'servers.json')


if not os.path.exists(base_path):
	os.makedirs(base_path)

def timestamp():
	return datetime.datetime.now().strftime("%Y%m%d-%H.%M.%S")

def read_timestamp(str):
	return datetime.datetime.strptime(str, ("%Y%m%d-%H.%M.%S"))

def remove_unicode(str):
	if not isinstance(str, unicode):
		return str
	return unicodedata.normalize('NFKD', str).encode('ascii','ignore')

logfile = open(os.path.join(base_path, "newsbot-%s.log" % timestamp()), 'w')

def log(msg):
	logfile.write(timestamp() + ": " + msg + "\n")
	logfile.flush()
	print(msg)

log("NewsBot starting")


def make_hash(msg):
	return hashlib.sha224(msg).hexdigest()

def add_user_to_list(username, re_list):
	re_list += [re.compile(username)]

def user_in_list(username, re_list):
	for re_entry in re_list:
		if re_entry.match(username):
			return True
	return False


# TODO:  Move RSS feed config info and state data about last seen and last checked to FILES
# TODO:  Add 'admin interface' for managing streams and user lists via privmsg


# RSS Feeds: Name, Color, URL, Update frequency (seconds), Random interval (seconds)
rss_feeds = []

if bot_number == 0:
	rss_feeds += [["BBC", "11,2", "http://feeds.bbci.co.uk/news/rss.xml", 10*60, 10*60]]
	rss_feeds += [["Reuters Top News", '4,1', "http://feeds.reuters.com/reuters/topNews", 20*60, 20*60]]
	rss_feeds += [["WIRED Top Stories", '8,14', "http://feeds.wired.com/wired/index", 20*60, 20*60]]

elif bot_number == 1:
	rss_feeds += [["Word", "11,2", "http://wordsmith.org/awad/rss1.xml", 4*60*60, 60*60]]
	rss_feeds += [["OED", "9,12", "http://www.oed.com/rss/wordoftheday", 4*60*60, 60*60]]
	rss_feeds += [["CD", "4,0", "https://www.mdbg.net/chinese/feed?feed=hsk_5", 1*60*60, 30*60]]

elif bot_number == 2:
	rss_feeds += [["Programming", "4,1", "https://old.reddit.com/r/programming/top/.rss", 30*60, 30*60]]
	rss_feeds += [["PyJob", "8,5", "https://sfbay.craigslist.org/search/scz/sof?query=python&format=rss", 120*60, 20*60]]
	rss_feeds += [["Robot", "10,1", "https://www.ebay.com/sch/i.html?_from=R40&_nkw=industrial%20robot%20arm&_sacat=0&rt=nc&_udlo=50&_udhi=20000&_rss=1", 60*60, 60*60]]


rss_next_check = [datetime.datetime.now() for i in range(len(rss_feeds))]
rss_last_seen = [["", ""] for i in range(len(rss_feeds))] # format: name, link

print(rss_feeds)
print(rss_next_check)

max_messagelength = 420 # must be no larger than messagelength - 3 for the added "..." - a few extra for text formatting codes



# set up user lists

authlist = []
add_user_to_list(r'ink!~ink@c-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.hsd1\.ca\.comcast\.net', authlist)
add_user_to_list(r'toner!~ink@c-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.hsd1\.ca\.comcast\.net', authlist)
#add_user_to_list(r'NewsBot[0-9]+!~NewsBot[0-9]+@c-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.hsd1\.ca\.comcast\.net', authlist)

botlist = []
add_user_to_list(r'NewsBot[0-9]+!~NewsBot[0-9]+@c-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.hsd1\.ca\.comcast\.net', botlist)

oplist = []
add_user_to_list(r'ink!~ink@c-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.hsd1\.ca\.comcast\.net', oplist)
add_user_to_list(r'toner!~ink@c-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.hsd1\.ca\.comcast\.net', oplist)
add_user_to_list(r'NewsBot[0-9]+!~NewsBot[0-9]+@c-[0-9]+-[0-9]+-[0-9]+-[0-9]+\.hsd1\.ca\.comcast\.net', oplist)




# how long to wait between messages   default: 3 seconds
output_flood_delay = datetime.timedelta(0, 3, 0)
last_spoke = datetime.datetime.now()


# connection timeouts
reconnect_timeout = 60
rsrc_not_available = 2
ping_timeout = 60*10


last_ping = datetime.datetime.now()

irc_output_buffer = []


def connect_to_irc():
	connected = False
	while not connected:
		try:
			irc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			if use_ssl:
				irc = ssl.wrap_socket(irc, ssl_version=ssl.PROTOCOL_TLSv1_2)
			irc.connect((server, port))
			irc.send("PASS " + password + "\n")
			irc.send("NICK " + name + "\n")
			irc.send("USER %s two three :four\n" % (name))
			irc.send("JOIN " + channel + "\n")
			irc.setblocking(0)
			connected = True
		except socket.error, (value,err_message):
			print("Connection exception, retrying...")
			print("%s [%i]" % (err_message, value))
			time.sleep(60)
	global last_ping
	last_ping = datetime.datetime.now()
	return irc

irc = connect_to_irc()



bold_code = '%c' % 2
underline_code = '%c' % 31
color_reset_code = '%c' % 15


def color_code(fg=15, bg=1):
	#if bg == 1 or bg == '1':
	#	return "%c%i" % (3, fg)
	return "%c%i,%i" % (3, fg, bg)


def set_color_state(bold_state, underline_state, color):
	buffer = ""
	if bold_state:
		buffer += bold_code
	if underline_state:
		buffer += underline_code
	if color.find(',') >= 0:
		(fg, bg) = color.split(',')
	else:
		(fg, bg) = (color, 1)
	buffer += color_code(int(fg), int(bg))
	return buffer


bold_re = re.compile('[%s]' % bold_code)
underline_re = re.compile('[%s]' % underline_code)
color_re = re.compile('[%c][0-9]+[,]*[0-9]*' % 3)
def scan_for_color_state(msg):
	(bold_state, underline_state, color) = (False, False, "15,1")
	# If there is a formatting reset code, start parsing after it
	last_reset_char = msg.rfind(color_reset_code)
	if last_reset_char < 0:
		last_reset_char = 0
	msg = msg[last_reset_char:]

	bolds = len(bold_re.findall(msg))
	underlines = len(underline_re.findall(msg))
	color = color_re.findall(msg)[-1][1:] # chop off first char as it is the color code char
	if bolds & 1: # odd number
		bold_state = True
	if underlines & 1: # odd number
		underline_state = True
	return (bold_state, underline_state, color)



def message(channel, msg):
	# if the message is too long, split it up into multiple messages
	(bold_state, underline_state, color) = (False, False, "15,1")
	is_continuation = False
	while len(msg) > 0:
		prefix = ""
		if is_continuation:
			prefix = "..."
		if len(msg) > max_messagelength:
			split_point = msg[:max_messagelength].rfind(' ')
			if split_point == -1:
				split_point = max_messagelength
			irc_output_buffer.insert(0, (channel, prefix + set_color_state(bold_state, underline_state, color) + msg[:split_point] + color_reset_code + "..."))
			(bold_state, underline_state, color) = scan_for_color_state(set_color_state(bold_state, underline_state, color) + msg[:split_point])
			msg = msg[split_point:]
			is_continuation = True
		else:
			irc_output_buffer.insert(0, (channel, prefix + set_color_state(bold_state, underline_state, color) + msg))
			msg = ""






class MyHTMLParser(HTMLParser):
	buffer = ""
	url = ""
	def handle_data(self, data):
		self.buffer += data.replace('\n', ' ')
	def handle_starttag(self, tag, attrs):
		if tag == 'a':
			self.url = ""
			for attr in attrs:
				if attr[0] == 'href':
					self.url = attr[1]
			#print("ATTRS", attrs)
			self.buffer += underline_code + color_code(11)
	def handle_endtag(self, tag):
		if tag == 'a':
			self.buffer += underline_code
			if self.url != "":
				self.buffer += " %s<%s>%s" % (color_code(12), self.url, color_code())
			self.url = ""
	def get_output(self):
			data = self.buffer
			self.buffer = ""
			return data
	def clear_output(self):
			self.buffer = ""

parser = MyHTMLParser()

def dump_rss_feed(chan, index):
#for url in feed_urls:

	log("Checking RSS Feed '%s'" % rss_feeds[index][0])
	(new_feed_articles, old_feed_articles, deleted_feed_articles) = (0, 0, 0)
	time_to_live = 60*60*48 # keep articles for 2 days after last seen
	url = rss_feeds[index][2]

	feed_filename = os.path.join(base_path, make_hash(url) + ".json")
	feed_data = {"articles":[], "last seen":[], "info":{}}
	if os.path.exists(feed_filename):
		feed_data = json.loads(open(feed_filename, 'r').read())
		log("Opened feed data for '%s'  %i articles read" % (rss_feeds[index][0], len(feed_data['articles'])))
	else:
		feed_data['info']['name'] = rss_feeds[index][0]
		feed_data['info']['url'] = rss_feeds[index][2]
		feed_data['info']['first checked'] = timestamp()
		log("Creating new feed file for '%s'" % rss_feeds[index][0])

	feed_data['info']['last checked'] = timestamp()


	feed = feedparser.parse(url)
	print(feed.keys())
	print("Processing:", rss_feeds[index])

	new_articles = []

	for item in feed['items']:
		#print("*  ", item)
		parser.feed(item['title'])
		title = remove_unicode(parser.get_output()).strip()
		parser.feed(item['summary'])
		summary = remove_unicode(parser.get_output()).strip()
		url = remove_unicode(item['links'][0]['href'])
		author = ""
		if item.has_key('author'):
			author = remove_unicode(item['author']).strip()
		article = [title, author, url]
		if article in feed_data['articles']:
			article_index = feed_data['articles'].index(article)
			feed_data['last seen'][article_index] = timestamp()
			old_feed_articles += 1

		else:
			# found a new article!
			feed_data['articles'].insert(0, article)
			feed_data['last seen'].insert(0, timestamp())
			new_articles += [article + [summary]]
			log("   New Article: '%s'" % title)
			new_feed_articles += 1

	for article in new_articles:
		fg = int(rss_feeds[index][1].split(',')[0])
		bg = int(rss_feeds[index][1].split(',')[1])
		output = "%s%s%s%s %s%s :: %s <%s%s%s>" % (bold_code, color_code(fg, bg), rss_feeds[index][0], color_code(15,1), article[0], bold_code, article[3], color_code(14), article[2], color_code())

		message(chan, output)



	# Scan the article list for old articles to remove
	for i in xrange(len(feed_data['articles'])-1, -1, -1): # count backwards so the index of earlier items remains consistent as we remove later items
		article_time = read_timestamp(feed_data['last seen'][i])
		if datetime.datetime.now() - article_time > datetime.timedelta(0, time_to_live, 0):
			article =  feed_data['articles'].pop(i)
			feed_data['last seen'].pop(i)
			log("   Article '%s' not seen for %s, removing..." % (article[0],  str(datetime.datetime.now() - article_time)))
			deleted_feed_articles += 1
				
		
	# Done processing RSS feed, now write the feed state file
	open(feed_filename, 'w').write(json.dumps(feed_data))

	log("Finished checking '%s': %i new, %i old, %i deleted." % (rss_feeds[index][0], new_feed_articles, old_feed_articles, deleted_feed_articles))




def process_rss_feeds():
	now = datetime.datetime.now()
	for index in range(len(rss_feeds)):
		if now > rss_next_check[index]:
			print("Processing RSS feed '%s'" % rss_feeds[index][0])
			rss_next_check[index] = datetime.datetime.now() + datetime.timedelta(0, rss_feeds[index][3] + random.random() * rss_feeds[index][4], 0)
			dump_rss_feed(channel, index)
			log("Next check for '%s': %s" % (rss_feeds[index][0], str(rss_next_check[index])))







irc_input_buffer = ""
irc_data = []

# Main loop
while True:

	got_input = False
	time_since_last_ping = datetime.datetime.now() - last_ping
	if time_since_last_ping.total_seconds() > ping_timeout:
		print("Ping timeout.  last server ping was", last_ping)
		irc = connect_to_irc()
	try:
		data = irc.recv(4096)
		#data = data.strip('\r\n')
		got_input = True
		if data == "":
			print('read ""  reconnecting in %i seconds' % reconnect_timeout)
			time.sleep(reconnect_timeout)
			irc = connect_to_irc()
			data = ""
	except socket.error, (value,err_message):
		#print("irc.recv exception:", err_message, value)
		if value == 2:
			print("No data, waiting...")
			time.sleep(1) # no data
			data = ""
		elif value == 11:
			time.sleep(rsrc_not_available)
			data = ""
		else:
			print("irc.recv exception:", err_message, value)
			print("reconnecting in %i seconds" % reconnect_timeout)
			time.sleep(reconnect_timeout)
			irc = connect_to_irc()
			data = ""
	irc_input_buffer += data

	# read from the socket and split into lines
	# keep a partial buffer to append to if it does not end with newline
	while '\n' in irc_input_buffer:
		split_buffer = irc_input_buffer.split('\n')
		irc_data += split_buffer[:-1]
		if split_buffer[-1].endswith('\n'):
			irc_data += split_buffer[-1]
			irc_input_buffer = ""
		else:
			irc_input_buffer = split_buffer[-1]

	# Process input

	# pull first line off the irc queue
	while len(irc_data) > 0:
		data = irc_data[0].strip('\r\n')
		irc_data = irc_data[1:]

		print(str(datetime.datetime.now()), "::", data)
		if data.startswith("PING"):
			irc.send("PONG\n")
			last_ping = datetime.datetime.now()
			print("sent PONG")
				
		elif data.startswith(':'):
			delim = data[1:].find(':')+1 # find the 2nd ':'
			header = data[1:delim]
			msg = data[delim+1:]
			print(header, "===", msg)
			split_header = header.split(' ')
			if len(split_header) > 1:
				if split_header[1] == 'PRIVMSG':
					chan = header.split(' ')[2]
					username = header.split(' ')[0]
					if msg.startswith(name + ':') or (not chan.startswith('#')): # being addressed
						command = ["",""]
						print("BEING ADDRESSED")
						if user_in_list(username, authlist):
							print("USER %s VALIDATED" % username)
							if msg.startswith(name + ':'):
								command = msg.split(' ')[1:]
							else:
								command = msg.split(' ')

						log(username + " ran " + repr(command))

						if command[0] == 'rss':
							message(chan, "Fetching RSS feed for %s" % command[1])
							dump_rss_feed(chan, command[1])

						elif command[0] == 'quit':
							if len(command) > 1:
								irc.send('QUIT :%s\n' % ' '.join(command[1:]))
							else:
								irc.send('QUIT :Goodbye\n')
								quit(0)

						elif command[0] == 'join':
							if len(command) == 2:
								irc.send('JOIN :%s\n' % command[1])
										
						elif command[0] == 'part':
							if len(command) > 2:
								irc.send('PART %s :%s\n' % (command[1], ' '.join(command[2:])))
							elif len(command) == 2:
								irc.send('PART %s :Goodbye\n' % command[1])

						elif command[0] == 'say':
							if len(command) > 2:
								irc.send('PRIVMSG %s :%s\n' % (command[1], ' '.join(command[2:])))


						elif command[0] == 'raw':
							if len(command) > 1:
								irc.send('%s\n' % (' '.join(command[1:])))


				if split_header[1] == "JOIN":
					username = split_header[0]
					chan = msg
					log("User '%s' joined chan '%s'" % (username, chan))
					if user_in_list(username, oplist) or user_in_list(username, botlist):
						log("Opping %s in %s" % (username, chan))
						irc.send('MODE %s +o :%s\n' % (chan, username.split('!')[0]))


	# Process output
	if len(irc_output_buffer) > 0:
		now = datetime.datetime.now()
		if now - last_spoke > output_flood_delay:
			(out_ch, out_msg) = irc_output_buffer.pop()
			irc.send("PRIVMSG " + out_ch + " :" + out_msg + "\n")
			last_spoke = now

	# Check the RSS feeds
	process_rss_feeds()

	# Polling loop delay if there was no input
	if not got_input:
		time.sleep(2)

