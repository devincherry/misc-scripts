#!/usr/bin/env python
#
# To patch a server, we
#   A) for each server to patch
#     1) identify all ELBs the server is registered in (write this to a state file in case of run
#        failure)
#     2) de-register the server from each ELB
#     3) update & reboot
#     4) re-register the server in each ELB it was registered in before
#
# Author: Devin Cherry <devincherry@gmail.com>
##################################################################################################
import os
import subprocess
import json
import inspect
import logging

from argparse import ArgumentParser
from time import sleep

import boto3


def debug_log(msg):
    """log the calling function's details along with the debug message."""
    # Get the previous frame in the stack
    calling_frame = inspect.currentframe().f_back
    func = calling_frame.f_code

    # Log the message along with the calling function's details
    logging.debug("%s  [in %s:%i]", msg, func.co_name, calling_frame.f_lineno)


def remove_instance_from_elb(load_balancer_name, instance_id):
    """Removes an instance from an ELB, and blocks until success or error."""
    elb = boto3.client("elb")

    resp = elb.describe_load_balancer_attributes(LoadBalancerName=load_balancer_name)
    timeout = 0
    if resp['LoadBalancerAttributes']['ConnectionDraining']['Enabled']:
        timeout = resp['LoadBalancerAttributes']['ConnectionDraining']['Timeout']

    logging.info("Removing instance [%s] from ELB [%s]...", instance_id, load_balancer_name)
    resp = elb.deregister_instances_from_load_balancer(
        LoadBalancerName=load_balancer_name,
        Instances=[
            {
                'InstanceId': instance_id
            },
        ]
    )
    debug_log("response was: %s" % (resp))

    resp = elb.describe_instance_health(
        LoadBalancerName=load_balancer_name,
        Instances=[
            {
                'InstanceId': instance_id
            },
        ]
    )
    debug_log("response was: %s" % (resp))
    elb_instance_state = resp['InstanceStates'][0]['State']

    # wait for connection draining to complete, if necessary
    if timeout > 0 and elb_instance_state != 'OutOfService':
        logging.info("Waiting [%i] seconds for connection draining to complete...", timeout)

        while timeout > 0:
            sleep(1)
            timeout -= 1

        sleep(5)
        resp = elb.describe_instance_health(
            LoadBalancerName=load_balancer_name,
            Instances=[
                {
                    'InstanceId': instance_id
                },
            ]
        )
        debug_log("response was: %s" % (resp))

        if resp['InstanceStates'][0]['State'] != 'OutOfService':
            logging.error("Instance [%s] State is [%s]! Continuing",
                          resp['InstanceStates'][0]['InstanceId'],
                          resp['InstanceStates'][0]['State'])
        else:
            logging.info("Instance [%s] has been deregistered from ELB [%s]", instance_id, load_balancer_name)


def add_instance_to_elb(load_balancer_name, instance_id):
    """Registers an instance in an ELB, and blocks until healthy or error."""
    # max time to wait for instance to become healthy
    max_wait = 300

    # pause time between checks
    check_delay = 5.0
    loop_count = max_wait/check_delay

    elb = boto3.client("elb")

    logging.info("Registering instance [%s] in ELB [%s]...", instance_id, load_balancer_name)
    resp = elb.register_instances_with_load_balancer(
        LoadBalancerName=load_balancer_name,
        Instances=[
            {
                'InstanceId': instance_id
            },
        ]
    )
    debug_log("response was: %s" % (resp))

    healthy = False
    while not healthy:
        sleep(check_delay)
        resp = elb.describe_instance_health(
            LoadBalancerName=load_balancer_name,
            Instances=[
                {
                    'InstanceId': instance_id
                },
            ]
        )

        debug_log("response was: %s" % (resp))

        if resp['InstanceStates'][0]['State'] == 'InService':
            healthy = True
            logging.info("Instance [%s] is now [%s]", instance_id, resp['InstanceStates'][0]['State'])
        else:
            loop_count -= 1
            if loop_count <= 0:
                logging.critical("Instance [%s] failed to become healthy within [%i] seconds!", instance_id, max_wait)
                raise Exception("Instance Not Healthy")


def add_to_state_file(instance_id, elb_list, state_filename):
    """Add an instance and its ELB list to the state file in case of error."""
    with open(state_filename, 'w+') as fp:
        try:
            records = json.load(fp)
        except ValueError:
            records = {}
        records[instance_id] = elb_list
        json.dump(records, fp, indent=0)
        debug_log("Added record to state file: %s = %s" % (instance_id, elb_list))


def remove_from_state_file(instance_id, state_filename):
    """Remove an instance from the state file, if it exists."""
    with open(state_filename, 'w+') as fp:
        try:
            records = json.load(fp)
            del records[instance_id]
            debug_log("Removed instance [%s] from state file" % (instance_id))
            json.dump(records, fp, indent=0)
        except ValueError:
            debug_log("ValueError (empty state file?)")
        except KeyError:
            debug_log("KeyError (state file has records, but none for this instance?)")


def get_elbs_from_state_file(instance_id, state_filename):
    """Gets the list of ELBs for the specified instance from the state file."""
    debug_log("state file = %s" % (state_filename))
    if os.path.isfile(state_filename):
        fp = open(state_filename, 'r')
        try:
            records = json.load(fp)
            logging.info("ELBs containing [%s] from prior failed run(s) = %s",
                         instance_id,
                         repr(records[instance_id]))
            return records[instance_id]
        except ValueError:
            debug_log("ValueError (empty state file?)")
            return []
        except KeyError:
            debug_log("KeyError (state file has records, but none for this instance?)")
            return []
    debug_log("No state file found")
    return []


def run_ssh_command(host, cmd):
    """Runs a command over ssh on the specified host, and returns stdout/err as a string."""
    opts = ('-o BatchMode=yes -o ConnectionAttempts=3 -o ConnectTimeout=30',
            '-o LogLevel=ERROR -o StrictHostKeyChecking=no')
    output = subprocess.check_output(
        [os.environ['SHELL'], '-c', 'ssh {0} {1} {2}'.format(' '.join(opts), host, cmd)],
        stderr=subprocess.STDOUT
    ).strip()
    return output


def install_updates_and_reboot(host):
    """Determines OS flavor, runs the corresponding update commands, then reboots the host."""
    logging.info("Installing updates on host [%s]...", host)
    commands = []
    reboot_delay_min = 0

    os_flavor = run_ssh_command(host, 'lsb_release -si')
    if os_flavor == "Ubuntu":
        logging.info("Ubuntu system detected. Updating via apt...")
        commands = [
            'sudo apt-get -y -q update',
            'sudo apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" -y -q upgrade',
            'sudo apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confnew" -y -q dist-upgrade',
            'sudo /sbin/shutdown -r +{}'.format(reboot_delay_min)
        ]
    elif os_flavor == "CentOS":
        logging.info("CentOS system detected. Updating via yum...")
        commands = [
            'sudo yum -y -q update',
            'sudo /usr/sbin/shutdown -r +{}'.format(reboot_delay_min)
        ]
    elif os_flavor == "AmazonAMI":
        logging.info("CentOS system detected. Updating via yum...")
        commands = [
            'sudo yum -y -q update',
            'sudo /sbin/shutdown -r +{}'.format(reboot_delay_min)
        ]
    else:
        logging.critical("Failed to determine OS flavor.  ***NOT UPDATING HOST***")
        logging.info("Output was:\n---[start output]---\n%s\n---[end output]---\n", os_flavor)
        exit(1)

    for cmd in commands:
        output = run_ssh_command(host, cmd)
        logging.info("---[start remote output]---\n%s\n---[end remote output]---", output)
    logging.info("Waiting for host [%s] reboot to initiate...", host)
    # sleep for a short period to allow reboot to stop services, thereby preventing
    # premature re-registration into the ELB.
    sleep((reboot_delay_min * 60) + 10)


def get_updateable_instances(environment):
    """Returns a list of updateable instances in the specified environment."""
    logging.info("Finding updateable instances...")
    ec2 = boto3.client('ec2')
    tag_filter = [
        {
            'Name': 'tag:AutoUpdate',
            'Values': ['True', 'true']
        },
        {
            'Name': 'tag:Environment',
            'Values': [environment]
        }
    ]
    instances = [i['Instances'][0] for i in ec2.describe_instances(Filters=tag_filter)['Reservations']]
    for i in instances:
        i_name = 'NO_NAME_TAG'
        for tag in i['Tags']:
            if tag['Key'] == 'Name':
                i_name = tag['Value']
        logging.info("Found EC2 Instance: %s  (%s, %s)", i_name, i['InstanceId'], i['PrivateIpAddress'])
    return instances


def find_elbs_for_instance(instance_id):
    """Returns a list of all ELBs which an instance is registered in."""
    elb_client = boto3.client('elb')

    logging.info("Finding ELBs containing instance [%s]...", instance_id)
    elbs = elb_client.describe_load_balancers()['LoadBalancerDescriptions']
    elbs_for_instance = []
    for e in elbs:
        for registered_instance in e['Instances']:
            if registered_instance['InstanceId'] == instance_id:
                logging.info("Found ELB [%s]", e['LoadBalancerName'])
                elbs_for_instance.append(e['LoadBalancerName'])
    return elbs_for_instance


def bleed_patch(instance, elbs, state_file='updatetool.state'):
    """Bleed instance from ELBs, patch+reboot, then re-register in ELBs."""
    add_to_state_file(instance['InstanceId'], elbs, state_file)
    for elb in elbs:
        remove_instance_from_elb(elb, instance['InstanceId'])

    install_updates_and_reboot(instance['PrivateIpAddress'])

    for elb in elbs:
        add_instance_to_elb(elb, instance['InstanceId'])
    remove_from_state_file(instance['InstanceId'], state_file)



if __name__ == "__main__":
    parser = ArgumentParser(description='Run rolling security updates on EC2 hosts.')
    parser.add_argument('environment', type=str,
                        help='Specify an environment to update (dev, stg, prd, etc...)')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help="Increase verbosity (more 'v's means more verbose)")
    parser.add_argument('-f', '--state-file', type=str, default='updatetool.state',
                        help='Specify an alternate state file location')
    args = parser.parse_args()

    if args.verbose == 0:
        LOGLEVEL = 'INFO'
        logging.getLogger('boto3').setLevel(logging.WARNING)
        logging.getLogger('botocore').setLevel(logging.WARNING)
        logging.getLogger('nose').setLevel(logging.WARNING)
    elif args.verbose == 1:
        LOGLEVEL = 'DEBUG'
        logging.getLogger('boto3').setLevel(logging.INFO)
        logging.getLogger('botocore').setLevel(logging.INFO)
        logging.getLogger('nose').setLevel(logging.INFO)
    elif args.verbose >= 2:
        LOGLEVEL = 'DEBUG'

    logging.basicConfig(
        format='%(asctime)s %(levelname)s - %(message)s',
        level=LOGLEVEL,
        datefmt='[%Y/%m/%d %H:%M:%S %Z]'
    )

    instances = get_updateable_instances(args.environment)
    for i in instances:
        # Allows recovery from failures that would leave instance deregistered from ELBs.
        elbs = list(frozenset(find_elbs_for_instance(i['InstanceId']) +
                              get_elbs_from_state_file(i['InstanceId'], args.state_file)))
        bleed_patch(i, elbs, state_file=args.state_file)
    logging.info("All done!")
