#
# Module of classes & types for ACCORNS
#


#
# A query object to be run on remote system
#
class RSystemQuery:
	cmd = ""
	outFile = ""
	rawOutput = ""

	def __init__(self, c, f):
		self.cmd = c
		self.outFile = f

	def setCMD(self, c): self.cmd = c
	def setOutfile(self, f): self.outFile = f
	def setOutput(self, o): self.rawOutput = o
	def getCMD(self): return self.cmd
	def getOutfile(self): return self.outFile
	def getOutput(self): return self.rawOutput


#
# holds credentials for accessing remote system
#
class Credentials:
	username = ""
	password = ""

	def __init__(self, u, p):
		self.username = u
		self.password = p

	def setPass(self, p): self.password = p
	def setUser(self, u): self.username = u
	def getPass(self): return self.password
	def getUser(self): return self.username

# 
# a contact object, holding methods of contact, and desired schedule
# TODO: create schedule functionality; also, add error checking for 
#       some set() functions
#
class Contact:
	username = ""
	fullname = ""
	email1 = ""
	email2 = ""
	email3 = ""
	phone1 = ""
	phone2 = ""
	phone3 = ""

	def __init__(self, n, e, p):
		self.name = n
		self.email1 = e
		self.phone1 = p

	def setName(self, n): self.fullname = n
	def setUsername(self, n): self.username = n
	def setEmail1(self, e): self.email1 = e
	def setEmail2(self, e): self.email2 = e
	def setEmail3(self, e): self.email3 = e
	def setPhone1(self, p): self.phone1 = p
	def setPhone2(self, p): self.phone2 = p
	def setPhone3(self, p): self.phone3 = p

	def getName(self): return self.name
	def getEmail1(self): return self.email1
	def getEmail2(self): return self.email2
	def getEmail3(self): return self.email3
	def getPhone1(self): return self.phone1
	def getPhone2(self): return self.phone2
	def getPhone3(self): return self.phone3

#
# the remote system to connect to and run queries on
#
class RSystem:
	ipAddress = ""
	credentials = None
	queryList = [None]

	def __init__(self, i, c, q):
		self.ipAddress = i
		self.credentials = c
		self.queryList = q

	def setIP(self, i): self.ipAddress = i
	def setCreds(self, c): self.credentials = c
	def setQueries(self, q): self.queryList = q
	def getIP(self): return self.ipAddress
	def getCreds(self): return self.credentials
	def getQueries(self): return self.queryList
	def getNumQueries(self): return len( self.queryList )

