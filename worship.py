# This Python file uses the following encoding: iso-8859-15
#
# worship.py -- tools to generate JSON specs for slides.py
#
import pprint
import inspect
import csv
import re
from lxml import etree
import io
from io import StringIO, BytesIO
import os
import argparse
import json
import glob
from datetime import datetime
import locale

from pathlib import Path
import requests
import urllib.parse
import time
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# https://www.blueletterbible.org/tools/MultiVerse.cfm
# t=&t=NKJV&mvText=matthew+26%3A27-29&refDelim=1&refFormat=2&numDelim=0&sqrbrkt=1

def load_json_safe(filepath):
	"""Load JSON file with UTF-8 and Windows-1252 encoding support"""
	try:
		with open(filepath, 'r', encoding='utf-8') as f:
			return json.load(f)
	except UnicodeDecodeError:
		with open(filepath, 'r', encoding='cp1252') as f:
			return json.load(f)

def update_passages(args):
	global s
	directory = None
	headers = {'user-agent': 'Mozilla/5.0 (Windows NT 6.1; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36' }
	payload = { 't': 'NKJV', 'mvText': 'Luke 24:5-7', 'refDelim': '1', 'refFormat': '2', 'numDelim': '0', 'sqrbrkt': '1' }

	try:
		s = requests.Session()
		s.headers.update(headers)

		# initial get to set cookies and session info
		print("getting")
		r = s.get('https://www.blueletterbible.org/tools/MultiVerse.cfm')
		time.sleep(2)

		# then post to request our verses
		print("posting")
		r = s.post('https://www.blueletterbible.org/tools/MultiVerse.cfm', data=payload)

		if r.status_code == 200:
			print("success!", r.encoding)
			with open("blueletter.html", 'wb') as file:
				file.write(r.content)

			parser = etree.HTMLParser()
			tree = etree.parse(StringIO(r.text), parser)
			result = tree.xpath('/html/body//div[@id="multiResults"]')
			print(result[0].text)

		else:
			print("status", r.status_code)
	except:
		print("exception")

	return


## 
## worship/templates/sunday-am-covid.json
## worship/templates/sunday-pm.json
## 
## worship/schedules/sunday-covid.json
## 
## worship/styles/default.json
## 
## worship/specs/2021/08/29/0815/20210829-0815-spec.json
## worship/specs/2021/08/29/0815/20210829-0815-songs.json
## worship/specs/2021/08/29/0815/20210829-0815-leaders.json
## worship/specs/2021/08/29/0815/20210829-0815-readings.json
## 
## worship/2021/20210829-0815.json
## worship/2021/20210829-0815.pptx
## 

#
# Globals
#

worshipRoot = "worship/"
schedulesRoot = worshipRoot + "schedules/"
templatesRoot = worshipRoot + "templates/"
stylesRoot = worshipRoot + "styles/"
specsRoot = worshipRoot + "specs/"

#
# Helper Functions
#

def get_spec_base(date, time):
	isodate = date + "T" + time
	wdiso = datetime.fromisoformat(isodate)
	specpath = specsRoot + wdiso.strftime("%Y/%m/%d/%H%M")
	specbase = specsRoot + wdiso.strftime("%Y/%m/%d/%H%M/%Y%m%d-%H%M")
	jsonbase = worshipRoot + wdiso.strftime("%Y/%Y%m%d-%H%M")
	return [specpath, specbase, jsonbase]

def load_template(template):
	items = None
	jsonfile = templatesRoot + template + ".json"
	items = load_json_safe(jsonfile)
	return items['order']

def load_spec(base):
	spec = load_json_safe(base[1] + "-spec.json")
	return spec

drwAuthKey = '36d46d79-f0f3-45f2-8737-e80d576c1924'

def update_status():
	ready = False
	headers = {'Authorization': drwAuthKey }
	url = 'https://api.embryhills.church/v1/update_status'

	try:
		r = requests.get(url, headers=headers)
		if r.status_code == 200:
			response = json.loads(r.text)
			if response['Success'] == True:
				data = response['Response']
				pprint.pprint(data)
				ready = (data['status'] == 'IDLE')
		else:
			print("response", r.status_code)
	except:
		print("exception")

	return ready


def update_data(args):
	headers = {'Authorization': drwAuthKey }
	url = 'https://api.embryhills.church/v1/update_data'

	try:
		r = requests.post(url, headers=headers)
		if r.status_code == 200:
			print("update requested")
			while update_status() == False:
				time.sleep(4)
		else:
			print("response", r.status_code)
	except:
		print("exception")


#
# fetch_leaders() - read leaders from the API
#
def fetch_leaders(wdate, wtime, service_type):
	leaders = dict()
	error = None
	warning = None
	headers = {'Authorization': drwAuthKey }
	url = 'https://api.embryhills.church/v1/worship_management/Assignments/' + urllib.parse.quote(service_type) + '/' + wdate

	try:
		try:
			r = requests.post(url, headers=headers, timeout=20)
		except requests.exceptions.SSLError:
			r = requests.post(url, headers=headers, timeout=20, verify=False)
			warning = "SSL verification failed; using insecure HTTPS fallback for assignments API"
		if r.status_code == 200:
			response = json.loads(r.text)
			if response['Success'] == True:
				data = response['Response']
				pprint.pprint(data)
				for role, leader in data.items():
					if ',' in leader:
						name = leader.split(', ')
						leaders[role] = name[1] + ' ' + name[0]
					else:
						leaders[role] = leader
			else:
				error = response.get('ErrorMessage', 'Assignments API returned Success=False')
		else:
			error = f"Assignments API response {r.status_code}: {r.text[:300]}"
	except Exception as e:
		error = f"Assignments API exception: {e}"

	result = { "leaders" : leaders }
	if error:
		result['_error'] = error
	if warning:
		result['_warning'] = warning
	return result

#
# Local scripture-reading schedule -- replaces the getScriptureReading API
# (being retired). Reads every assets/Scripture Reading*.csv: each is a
# year's worth of Sunday AM ("Morning Readings (Apostles)") and PM
# ("Evening Readings (Prophets)") reading assignments by date.
#

SPANISH_BOOK_NAMES = {
	"1 Corinthians": "1 Corintios",
	"1 John": "1 Juan",
	"1 Peter": "1 Pedro",
	"1 Thessalonians": "1 Tesalonicenses",
	"1 Timothy": "1 Timoteo",
	"2 Corinthians": "2 Corintios",
	"2 Samuel": "2 Samuel",
	"Colossians": "Colosenses",
	"Daniel": "Daniel",
	"Ephesians": "Efesios",
	"Exodus": "Éxodo",
	"Ezekial": "Ezequiel",		# typo in the source spreadsheet
	"Ezekiel": "Ezequiel",
	"Galatians": "Gálatas",
	"Genesis": "Génesis",
	"Haggai": "Hageo",
	"Hebrews": "Hebreos",
	"Isaiah": "Isaías",
	"James": "Santiago",
	"Jeremiah": "Jeremías",
	"Joel": "Joel",
	"John": "Juan",
	"Jude": "Judas",
	"Luke": "Lucas",
	"Malachi": "Malaquías",
	"Mark": "Marcos",
	"Matthew": "Mateo",
	"Micah": "Miqueas",
	"Philippians": "Filipenses",
	"Proverbs": "Proverbios",
	"Psalm": "Salmo",
	"Psalms": "Salmos",
	"Revelation": "Apocalipsis",
	"Romans": "Romanos",
	"Titus": "Tito",
	"Zechariah": "Zacarías",
	"Zehariah": "Zacarías",		# typo in the source spreadsheet
}


def translate_reference_to_spanish(reference):
	"""Split a book+chapter:verse reference into its parts and translate
	just the book name. Falls back to the original English book name for
	anything not in SPANISH_BOOK_NAMES, rather than failing the whole
	autofill over one unrecognized book."""
	match = re.match(r'^(.*?)\s+(\d.*)$', reference.strip())
	if not match:
		return reference
	book, rest = match.group(1), match.group(2)
	return SPANISH_BOOK_NAMES.get(book, book) + ' ' + rest


def load_local_scripture_schedule(folder=None):
	"""Read every "Scripture Reading*.csv" in folder (default: assetRoot,
	next to the other bundled reference data) into one
	{date: {"am": ref, "pm": ref}} dict, keyed by the "Date" column
	(YYYY-MM-DD, matching wdate's format). Later files (sorted by name) win
	on a date collision -- lets next year's file be dropped in alongside
	this one without deleting the old file."""
	if folder is None:
		folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
	schedule = dict()
	for csv_path in sorted(glob.glob(os.path.join(folder, 'Scripture Reading*.csv'))):
		with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
			for row in csv.DictReader(f):
				date = (row.get('Date') or '').strip()
				if not date:
					continue
				schedule[date] = {
					'am': (row.get('Morning Readings (Apostles)') or '').strip(),
					'pm': (row.get('Evening Readings (Prophets)') or '').strip(),
				}
	return schedule


#
# fetch_readings() - look up the reading for wdate in the local schedule
#
def fetch_readings(wdate, readings, service_type):
	"""Sun - AM uses the Apostles/morning reading, Sun - PM the Prophets/
	evening reading; other service types (Wed, Gospel Meeting) aren't
	covered by this schedule, so they simply get no reading -- the same as
	a date the schedule doesn't have."""
	if service_type == 'Sun - AM':
		column = 'am'
	elif service_type == 'Sun - PM':
		column = 'pm'
	else:
		column = None

	if column:
		schedule = load_local_scripture_schedule()
		eng_reference = schedule.get(wdate, {}).get(column)
		if eng_reference:
			esp_reference = translate_reference_to_spanish(eng_reference)
			readings['reading-1'] = {
				"lang": [
					{"passage": eng_reference},
					{"passage": esp_reference},
				]
			}

	return { "readings" : readings }


##
##	[service-id]-spec
##	  - date, time
##	  - language
##	  - select service-template
##	  - service type ("Sun AM") for Congregate lookup
##
def generate_worship_spec(wdate, wtime, template, language, service_type):
	spec = dict()
	spec['isodate'] = wdate + "T" + wtime
	spec['template'] = template
	spec['language'] = language
	spec['type'] = service_type
	return spec

##
##	[service-id]-songs
##	  - for each reference ("song-1"), provides song details
##
def generate_songs(items):
	songlist = dict()
	for item in items:
		if item['type'] in ['song', 'song-music']:
			song = {"book": "pftl", "song": "", "verses": [], "chorus": [], "coda": 0 }
			songlist[item['id']] = song
	return { "songs" : songlist }

##
## [service-id]-leaders
##   - fetched from api.embryhills.church OR manual
##   - for each leader position, lists leader name
##   - include preacher
##
def generate_leaders(items):
	leaderlist = dict()
	for item in items:
		if "position" in item:
			leaderlist[item['position']] = ""
	return { "leaders" : leaderlist }


##
## [service-id]-readings
##   - list scripture readings, LS readings, Collection readings?
##   - sermon topics
##
def generate_readings(items):
	readinglist = dict()
	for item in items:
		reading = None
		if item['type'] == 'reading':
			readinglist[item['id']]  = { "lang": [ {"passage": "", "pew": ""}, {"passage": ""}] }
		elif item['type'] == 'ls-am':
			readinglist[item['id']]  = { "reading": "" }
		elif item['type'] == 'sermon':
			readinglist[item['id']]  = { "title": "", "título": "" }
	return { "readings" : readinglist }



#
# Main Functions
#

def generate_worship(wdate, wtime, template, language, service_type):
	base = get_spec_base(wdate, wtime)
	Path(base[0]).mkdir(parents=True, exist_ok=True)

	items = load_template(template)

	# spec.json
	spec = generate_worship_spec(wdate, wtime, template, language, service_type)
	with open(base[1] + "-spec.json", 'w') as jsonfile:
		json.dump(spec, jsonfile, ensure_ascii=False, indent=4)

	# songs.json
	songs = generate_songs(items)
	with open(base[1] + "-songs.json", 'w') as jsonfile:
		json.dump(songs, jsonfile, ensure_ascii=False, indent=4)

	# leaders.json
	leaders = generate_leaders(items)
	with open(base[1] + "-leaders.json", 'w') as jsonfile:
		json.dump(leaders, jsonfile, ensure_ascii=False, indent=4)

	# readings.json
	readings = generate_readings(items)
	with open(base[1] + "-readings.json", 'w') as jsonfile:
		json.dump(readings, jsonfile, ensure_ascii=False, indent=4)


#
# generate_schedule
#
def generate_schedule(args):
	schedule = load_json_safe(schedulesRoot + args.schedule + ".json")
#		pprint.pprint(schedule)
	for service in schedule['schedule']:
		generate_worship(args.wdate, service['time'], service['template'], service['language'], service['service'])


##
##	worship.py -d date -t time -l 
##	 -- fetch worship leaders
##
def update_leaders(args):
	base = get_spec_base(args.wdate, args.wtime)
	spec = load_spec(base)
	leaders = fetch_leaders(args.wdate, args.wtime, spec['type'])
	with open(base[1] + "-leaders.json", 'w') as jsonfile:
		json.dump(leaders, jsonfile, ensure_ascii=False, indent=4)

##
##	worship.py -d date -t time -r
##	 -- fetch scripture readings
##
def update_readings(args):
	base = get_spec_base(args.wdate, args.wtime)
	spec = load_spec(base)
	readings = load_json_safe(base[1] + "-readings.json")['readings']
	readings = fetch_readings(args.wdate, readings, spec['type'])
	with open(base[1] + "-readings.json", 'w') as jsonfile:
		json.dump(readings, jsonfile, ensure_ascii=False, indent=4)





def generate_json(args):
	base = get_spec_base(args.wdate, args.wtime)
	spec = load_json_safe(base[1] + "-spec.json")
	songs = load_json_safe(base[1] + "-songs.json")['songs']
	leaders = load_json_safe(base[1] + "-leaders.json")['leaders']
	readings = load_json_safe(base[1] + "-readings.json")['readings']

	template = spec['template']
	items = load_template(template)

	if args.style is not None:
		style = load_json_safe(stylesRoot + args.style + ".json")

	if 'Song Leader' in leaders:
		spec['leader'] = leaders['Song Leader']

	order = list()
	for item in items:
		if 'position' in item:
			if item['position'] in leaders:
				item['leader'] = leaders[item['position']]
		if 'id' in item:
			if item['id'] in songs:
				item.update(songs[item['id']])
			if item['id'] in readings:
				item.update(readings[item['id']])
			if args.style is not None:
				if item['id'] in style:
					item.update(style[item['id']])
		order.append(item)

	spec['items'] = order

	with open(base[2] + ".json", 'w') as jsonfile:
		json.dump(spec, jsonfile, ensure_ascii=False, indent=4)


##############################################################################
##
## Main Processing
##
##############################################################################

##	worship.py -u
##	 -- update duty database
##
##	worship.py -d date -s schedule
##	 -- create initial worship files
##
##	worship.py -d date -t time -template template [-lang language] [-type "Sun AM"]
##	 -- create initial worship files
##
##	worship.py -d date -t time -l 
##	 -- fetch worship leaders
##
##	worship.py -d date -t time -j [-style style]
##	 -- generate worship JSON file


def main():
#	book_list = ['pftl', 'shs', 'phss', 'eh']
	schedule_list = ['sunday-covid', 'fifth-sunday-covid', 'fifth-sunday-1', 'fifth-sunday-2', 'fifth-sunday-3', 'fifth-sunday-six-songs', 'wednesday', 'meeting', 'sunday', 'meeting-3']
	template_list = ['sunday-am-covid', 'sunday-am']
	lang_list = ['eng', 'esp', 'bil']
	type_list = ['Sun - EarlyAM', 'Sun - AM', 'Sun - PM', 'Wed', 'Gospel Meeting']
	style_list = ['fall-1', 'fall-2', 'fall-3', 'dec-1', 'jan-1', 'jan-2', 'jan-pm', 'mar-1', 'mar-pm', 'apr-1']
	parser = argparse.ArgumentParser(description="Worship Specifier Tool")
	parser.add_argument('-d', dest='wdate', help="Date for worship service (YYYY-MM-DD)", default=None, required=False)
	parser.add_argument('-t', dest='wtime', help="Time for worship service (HH:MM:SS)", default=None)
	parser.add_argument('-s', dest='schedule', help="Schedule to follow for Date", choices=schedule_list, default=None)
	parser.add_argument('-j', dest='json', help="Generate JSON worship file", action='store_true')
	parser.add_argument('-l', dest='leaders', help="Fetch leaders from database", action='store_true')
	parser.add_argument('-u', dest='update', help="Update duty database", action='store_true')
	parser.add_argument('-r', dest='readings', help="Update readings", action='store_true')
	parser.add_argument('-p', dest='passages', help="Update passages (LS/Coll)", action='store_true')
	parser.add_argument('-lang', dest='language', help="Output language", choices=lang_list, default=lang_list[0])
	parser.add_argument('-template', dest='template', help="Use template to create worship files", choices=template_list)
	parser.add_argument('-type', dest='type', help="Congregate Service Type", choices=type_list, default=type_list[0])
	parser.add_argument('-style', dest='style', help="Apply style to JSON file", choices=style_list, default=None)

	args = parser.parse_args()

	if args.update:
		update_data(args)
	elif args.schedule is not None:
		generate_schedule(args)
	elif args.wtime is not None and args.wdate is not None:
		if args.template is not None:
			generate_worship(args.wdate, args.wtime, args.template, args.language, args.type)
		elif args.leaders:
			update_leaders(args)
		elif args.passages:
			update_passages(args)
		elif args.readings:
			update_readings(args)
		elif args.json:
			generate_json(args)
		else:
			parser.print_usage()
	else:
		parser.print_usage()



if __name__ == '__main__':
	main()

