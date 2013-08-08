#!/usr/bin/python
import getpass
import sys
import telnetlib

remote_host = raw_input("Enter hostname: ")
user = raw_input("Enter username: ")
passwd = getpass.getpass()

ts = telnetlib.Telnet(remote_host)

ts.read_until("login:", 3)
ts.write(user + "\n")
ts.read_until("Password:", 3)
ts.write(passwd + "\n")

ts.write("ls\n")
ts.write("exit\n")

print ts.read_all()

