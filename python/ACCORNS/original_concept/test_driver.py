#!/usr/bin/python
import ACCORNTypes
import ACCORNHandlers

creds = ACCORNTypes.Credentials("bob", "password")
qry = ACCORNTypes.RSystemQuery("ls", "ls_output.txt")
qry2 = ACCORNTypes.RSystemQuery("pwd", "pwd_output.txt")
system = ACCORNTypes.RSystem("192.168.0.1", creds, [qry, qry2])
sys_t = ACCORNHandlers.RSystemThread(system)
parser = ACCORNHandlers.ConfigParser()


# test Credentials class
print "Testing Credentials class..."
print "post-instantiation values: " + creds.getUser() + ", " + creds.getPass()
print "Finished testing Credentials class...\n"

# test RSystemQuery class
print "Testing RSystemQuery class..."
print "post-instantiation values: " + qry.getCMD() + ", " + qry.getOutfile() \
	+ ", " + qry.getOutput()
print "Finished testing RSystemQuery class...\n"

# test RSystem class
print "Testing RSystem class..."
print "post-instantiation values: " + system.getIP()
system_creds = system.getCreds()
print system_creds.getUser() + ", " + system_creds.getPass()
print "Finished testing RSystem class...\n"

# test RSystemThread class
print "Testing RSystemThread class..."
print "post-instantiation values: ", sys_t.isRunning()
sys_t.processData()
print "Finished testing RSystemThread class...\n"

# test config parser
print "Testing config parser..."
parser.readConfig("config.txt")
print "finished testing config parser.\n"
