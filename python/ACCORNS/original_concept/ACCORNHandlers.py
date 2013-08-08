#
# module of various data & connection handler types
#
import ACCORNTypes
import re
import string
import pexpect


#
# Processes data. (i.e. SVN commit, send alerts, etc...)
#
class DataProcessor():
	def __init__(self): pass

	def printQuery(self, qry):
		print "Query:\n", qry.getCMD(), "\n", qry.getOutfile(), "\n", qry.getOutput()
#
# handles commits & fetches of configs via CVS/SVN
#
class ConfigHandler():
	def __init__(self): pass

	def commitConfig(self, rsys, configText):
		# TODO: need commit routine here for SVN
		print "this will eventually commit config changes"


#
# handles sending of alerts for changes or commit diffs
#
class AlertHandler():
	def __init__(self): pass

	def sendAlert(self, person):
		# TODO: need to fetch contact info for specified person, then send alert(s)
		print "will eventually send an alert to the person specified"

	def getContactInfo(self, person, infoType):
		# TODO: need to return the contact info for the specified person, and
		# and of the desired type for alerting.
		print "will eventually return contact info object"

#
# handles a remote system connection
# inherits attributes/functions from RSystem
#
class RSystemThread(ACCORNTypes.RSystem):
	processor = DataProcessor()
	isRunning = False
	connection = None

	def __init__(self, rsys):
		self.setIP( rsys.getIP() )
		self.setCreds( rsys.getCreds() )
		self.setQueries( rsys.getQueries() )

	def getConnection(self): return self.connection
	def setConnection(self, c): self.connection = c

	# returns 'True' if running
	def isRunning(self): return self.isRunning

	# just print output, for now...
	def processData(self):
		print "num queries: ", self.getNumQueries() 

		queryList = self.getQueries()
		for i in range( 0, self.getNumQueries() ):
			self.processor.printQuery( queryList[i] )

	# don't do anything, for now...
	def run(self):
		self.isRunning = True
		print "Running connection process now..."
	
	# run a command line
	def runCMD(self):
		pass		

	# netgear cmd cuz I'm buzzed
	def routerLogin(self):
		foo = pexpect.spawn()
		print foo
		


#
# Handles parsing of config file
# Just an example for now. May change completely.
#
class ConfigParser():
	__cfg = None

	def __init__(self):
		pass

	def readConfig(self, cfg_file):
		self.__cfg = cfg_file
		f = open(self.__cfg)

		try:
			for line in f:
				# strip off leading whitespace to make consistent state 
				# for regex matching
				line = string.lstrip(line)

				# match an opening tag
				if ( re.match("^<\w", line) ):
					section = re.search("^<(\w+)>", line).groups()[0]
					print "begin section: " + section
					continue

				# will print what's between tags while line != closing tag
				# should use tokenizer in here 
				if (not re.match("^</", line) ):
					print "\t" + line, 
				else:    
					endsection = re.search("^</(\w+)>", line).groups()[0]
					print "end of section: " + endsection
		finally:
			f.close()

