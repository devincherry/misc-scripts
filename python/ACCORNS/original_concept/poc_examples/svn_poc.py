#!/usr/bin/python
import os
import sys

args = ['svn', 'diff', 'pexpect_poc.py']

print "diff example:"
os.execl("/usr/bin/svn", *args)

