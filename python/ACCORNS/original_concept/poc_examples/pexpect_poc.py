#!/usr/bin/python
import pexpect


### BEGIN DEFINITIONS ###
# attempt initial login 
def ssh_login(ch, userID, passWD):
	try:
		ch.expect(['password:', 'Password:'], timeout=10)
	except:
		print "unexpected login prompt!"
		exit(1)

	bytes_written = ch.sendline(passWD)

	# login should succeed, or exit with error
	try: 
		ch.expect(['[\$]'], timeout=5)
	except:
		print "login failed, bad password?"
		exit(1)
	return bytes_written


# logout remote session
def ssh_logout(ch, logout_cmd):
	bytes_written = ch.sendline(logout_cmd)
	return bytes_written


# print all output from commands
def get_output(ch): 
	prev_timeout = ch.timeout
	ch.timeout = 3
	lines = ""
	while(1): 
		try:
			# should throw timeout exeption
			lines += ch.readline(size=255)
		except:
			break
	ch.timeout = prev_timeout
	return lines

# execute remote command
def run_cmd(ch, cmd): 
	bytes_written = 0
	try:
		bytes_written = ch.sendline(cmd)
	except:
		print "command execution failed. dropped connection?"
		if( ch.isalive() ):
			return -1
		else:
			print "child process died. exiting."
			exit(1)
	return bytes_written
### END DEFINITIONS ###


#### BEGIN EXECUTION ####
ssh_path = '/usr/bin/ssh'
host = 'localhost'
args = '-p 22'
username = 'testuser'
password = 'foobarbaz'
savefile = 'remote_output.txt'
login_cmd = ssh_path + ' ' + username + '@' + host + ' ' + args
cmd_list = ['ls -al', 'ps', 'w']


# begin remote session
child = pexpect.spawn(login_cmd)

fptr = file('session.log', 'w')
child.logfile = fptr
outfile = open(savefile, 'w') 

ssh_login(child, username, password)

for i in range(0,len(cmd_list)):
	run_cmd(child, cmd_list[i])
	outfile.write( get_output( child ) )

outfile.close()
ssh_logout(child, "exit")

# cleanup
if( child.isalive() ):
	child.kill(9)

exit(0)

