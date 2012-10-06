#!/bin/bash
#
# @brief simple script to manage routing rules for vlans
# 
# @details
# This script is intended to be run as a Debian post-{up/down}
# command from within /etc/network/interfaces stanzas. This
# will setup routing configurations on a per-interface basis,
# as determined by the environment variables provided by the
# interfaces(5) stanzas in the above-mentioned config file.
#
# Since Linux isn't smart about managing multiple default routes,
# each vlan bridge should be configured to delete its own
# "default" entry from the main table. If you don't do this,
# then your main routing table will end up with multiple default 
# route entries. Since the 2nd and subsequent entries will never be
# reached, they effectively "don't work". To fix this, a default 
# route entry must be added to the vLANs own routing table, 
# followed by routing policies which tell the vlan interface what 
# to do with traffic from networks that aren't locally connected.
#
# @author Devin Cherry <youshoulduseunix@gmail.com>
###############################################################


# IMPORTANT: Don't forget to add an undo section below, so
# your interface will deconfigure properly when given a "stop" $MODE!
if [ "$MODE" == "start" ] ; then
	if [ "$IFACE" == "vlan2-br" ] ; then
		# Since we want ONE default route to still exist in the main
		# routing table, we won't delete this vlan's entry. 

		# Populate per-vlan table with proper default routes.
		ip route add default via 192.168.1.1 dev vlan2-br table vlan2

		# Add routing policies for non-locally connected routes.
		ip rule add from 192.168.15.0/24 to 192.168.1.0/24 table vlan2
		ip rule add from 192.168.1.0/24 to 192.168.15.0/24 table vlan2
	fi
	if [ "$IFACE" == "vlan4-br" ] ; then
		# Delete bad default route entry from main table
		ip route del default via 192.168.4.1 table main

		# Populate per-vlan table with proper default routes.
		ip route add default via 192.168.4.1 dev vlan4-br table vlan4
	
		# Add routing policies for non-locally connected routes.
		ip rule add from 192.168.15.0/24 to 192.168.4.0/24 table vlan4
		ip rule add from 192.168.4.0/24 to 192.168.15.0/24 table vlan4
	fi
	if [ "$IFACE" == "vlan5-br" ] ; then
		# Delete bad default route entry from main table
		ip route del default via 192.168.5.1 table main

		# Populate per-vlan table with proper default routes.
		ip route add default via 192.168.5.1 dev vlan5-br table vlan5

		# Add routing policies for non-locally connected routes.
		ip rule add from 192.168.15.0/24 to 192.168.5.0/24 table vlan5
		ip rule add from 192.168.5.0/24 to 192.168.15.0/24 table vlan5
	fi
	if [ "$IFACE" == "vlan6-br" ] ; then
		# Delete bad default route entry from main table
		ip route del default via 192.168.6.1 table main

		# Populate per-vlan table with proper default routes.
		ip route add default via 192.168.6.1 dev vlan6-br table vlan6

		# Add routing policies for non-locally connected routes.
		ip rule add from 192.168.15.0/24 to 192.168.6.0/24 table vlan6
		ip rule add from 192.168.6.0/24 to 192.168.15.0/24 table vlan6
	fi
fi


# This section should undo any route/rule stuff 
# you do above for a given $IFACE...
if [ "$MODE" == "stop" ] ; then
	if [ "$IFACE" == "vlan2-br" ] ; then
		# Remove routing policies for non-locally connected routes.
		ip rule del from 192.168.15.0/24 to 192.168.1.0/24 table vlan2
		ip rule del from 192.168.1.0/24 to 192.168.15.0/24 table vlan2
	fi
	if [ "$IFACE" == "vlan4-br" ] ; then
		# De-populate per-vlan table of proper default routes.
		ip route del default via 192.168.4.1 dev vlan4-br table vlan4
	
		# Remove routing policies for non-locally connected routes.
		ip rule del from 192.168.15.0/24 to 192.168.4.0/24 table vlan4
		ip rule del from 192.168.4.0/24 to 192.168.15.0/24 table vlan4
	fi
	if [ "$IFACE" == "vlan5-br" ] ; then
		# De-populate per-vlan table of proper default routes.
		ip route del default via 192.168.5.1 dev vlan5-br table vlan5

		# Remove routing policies for non-locally connected routes.
		ip rule del from 192.168.15.0/24 to 192.168.5.0/24 table vlan5
		ip rule del from 192.168.5.0/24 to 192.168.15.0/24 table vlan5
	fi
	if [ "$IFACE" == "vlan6-br" ] ; then
		# De-populate per-vlan table of proper default routes.
		ip route del default via 192.168.6.1 dev vlan6-br table vlan6

		# Remove routing policies for non-locally connected routes.
		ip rule del from 192.168.15.0/24 to 192.168.6.0/24 table vlan6
		ip rule del from 192.168.6.0/24 to 192.168.15.0/24 table vlan6
	fi
fi


# do a flush of the routing cache so we're sane
ip route flush cache

