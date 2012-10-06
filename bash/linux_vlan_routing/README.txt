This configuration is for setting up vlan-based routing on a Debian/Ubuntu Linux system.

First, install the pre-requisite packages:

	apt-get install vlan iproute

Then, you need to create named routing tables, so edit /etc/iproute2/rt_tables.
Add a line like "N  vlanN" for each vlan you need.

Next, you need to setup /etc/network/interfaces to create vlan and bridge interfaces.
Here's a short example:

	#########################################################
	# The loopback network interface
	auto lo
	iface lo inet loopback
	
	auto eth0
	iface eth0 inet manual
	        post-up iptables-restore < /etc/iptables.up.rules
	
	# underlying VLAN interface config
	auto vlan2
	iface vlan2 inet manual
	        vlan_raw_device eth0
	
	# VLAN bridge interface config 
	auto vlan2-br
	iface vlan2-br inet static
	        address 192.168.1.4
	        network 192.168.1.0
	        netmask 255.255.255.0
	        broadcast 192.168.1.255
	        gateway 192.168.1.1
	        bridge_ports vlan2
	        bridge_stp off
	        post-up /usr/local/sbin/setup_routing.sh
	#########################################################

Then, you need to configure routes and routing policy rules for each vlan interface.
Edit "routing_setup.sh" to include some rules and policies for your desired vlans.
Use the contained examples as a starting point. This script is called by the post-up
configuration stanza within interfaces(5), and several environment variables are
set when it's called. See interfaces(5) for more details.

Finally, edit your iptables configuration as deemed appropriate, and reboot to test.

You should now have vlans configured, with appropriate routing policies in place. Enjoy!

Author: Devin Cherry <youshoulduseunix@gmail.com>
