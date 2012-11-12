#!/usr/bin/env python
import curses
import logging
import threading
import time 
import subprocess

class DisplayRefresher(threading.Thread):
    '''A thread to handle periodic display updates'''
    def __init__(self, screen, seconds=1.1):
        threading.Thread.__init__(self)
        self.stdscr = screen
        self.refresh_delay = seconds
    
    def run(self):
        while 1:
            stdscr.addstr(0, 0, time.strftime("%a, %d %b %Y %H:%M:%S") )
            self.stdscr.refresh()
            time.sleep(self.refresh_delay)


# the global curses screen
stdscr = curses.initscr()

# set basic logging to stderr
logging.basicConfig(level=logging.DEBUG)

# start a thread to periodically update the screen
refresher_t = DisplayRefresher(stdscr, 1)

# set some coordinates for the common header location
headerY = 3
headerX = 0

def _eraseArea(startY, startX, endY, endX):
    for Y in range(startY, endY):
        for X in range(startX, endX):
            # this throws an exception if we write out of bounds of the actual terminal size.
            try:
                stdscr.addstr(Y, X, " ")
            except:
                # just ignore it, and keep clearing the area
                pass

def listUsers():
    _eraseArea(headerY, headerX, 50, 200)
    stdscr.addstr(headerY, headerX, "Current Users:", curses.A_BOLD)
    users = subprocess.check_output(["who"])
    stdscr.addstr(5, 0, users)

def listProcesses():
    _eraseArea(headerY, headerX, 50, 200)
    stdscr.addstr(headerY, headerX, "Current Processes:", curses.A_BOLD)
    procs = subprocess.check_output(["ps", "u"])
    stdscr.addstr(5, 0, procs)


########################################
#            Begin Execution           #
########################################

# wrap everything in a try block, so we can recover the terminal from our buggy code :)
try:
    curses.noecho()
    curses.curs_set(0)
    stdscr.keypad(1)

    stdscr.addstr(1, 0, "(u = users; p = processes; q = quit)")
    stdscr.refresh()

    refresher_t.daemon = True
    refresher_t.start()

    # enter loop, reacting to user key presses
    while 1:
        c = stdscr.getch()
        if c == ord('q'): break
        elif c == ord('u'): listUsers()
        elif c == ord('p'): listProcesses()

except Exception, e:
    logging.exception("Oh, my! A bug!")
finally:
    curses.endwin()
