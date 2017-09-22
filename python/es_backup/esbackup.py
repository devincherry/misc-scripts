#!/usr/bin/env python
#
# Author: Devin Cherry <devincherry@gmail.com>
#############################################################
""" A tool for managing AWS ElasticSearch snapshots. """
import sys
import argparse
import time
from datetime import datetime
import yaml
from elasticsearch import Elasticsearch, RequestsHttpConnection, exceptions
from requests_aws4auth import AWS4Auth


OPTS = None

# list of snapshot repository names to skip/ignore for all operations
# (AWS maintains inaccessible snapshot repos in the cluster)
BAD_REPO_NAMES = [
    'cs-automated'
]


def __error_exit(msg):
    print >>sys.stderr, "ERROR: %s" % msg
    sys.exit(1)


def __snapshot_running(es):
    '''Returns True if a snapshot is running in any discovered repo.'''
    repos_raw = es.cat.repositories(v=False)
    repos = []
    for line in repos_raw.split('\n'):
        if line == '':
            continue
        repos.append(line.split()[0].strip())

    for bad_repo in BAD_REPO_NAMES:
        repos.remove(bad_repo)

    for r in repos:
        status = es.snapshot.status(repository=r)
        if status['snapshots']:
            return True
    return False


def elasticsearch_connection(cluster, username, password, ca_cert_path):
    '''Create and return an elasticsearch connection object.'''
    required_keys = ['url', 'region']
    for k in required_keys:
        if not cluster.has_key(k):
            __error_exit("Cluster configuration is missing key [%s]!" % k)

    awsauth = AWS4Auth(username, password, cluster['region'], 'es')
    es = Elasticsearch(
        ["https://%s:443/" % cluster['url']],
        use_ssl=True,
        verify_certs=True,
        ca_certs=ca_cert_path,
        http_auth=awsauth,
        connection_class=RequestsHttpConnection,
        timeout=60
    )

    if not es.ping():
        __error_exit("Failed to connect to cluster [%s]!" % cluster['url'])

    return es


def create_snapshot(es, indices, snapshot_name):
    '''Create a snapshot in the specified repo.'''
    try:
        (repo, snap) = snapshot_name.split('/')
    except ValueError:
        __error_exit("You must specify a snapshot name in the format \"repo_name/snapshot_name\"!")

    snapshot_body = "{\"indices\": \"%s\",\"ignore_unavailable\": false}" % indices

    try:
        snap_check = es.snapshot.get(repository=repo, snapshot=snap)
        print "Snapshot [%s] already exists in repo [%s]." % (snap, repo)
        if OPTS.verbose:
            print repr(snap_check)
    except exceptions.NotFoundError:
        es.snapshot.create(repository=repo, snapshot=snap, body=snapshot_body,
                           wait_for_completion=False)
        print "Started snapshot [%s] in repo [%s]..." % (snap, repo)


def delete_snapshot(es, snapshot_to_delete):
    '''Delete a snapshot from the specified repo on the specified cluster.'''
    try:
        (repo, snap) = snapshot_to_delete.split('/')
    except ValueError:
        __error_exit("You must specify a snapshot name in the format \"repo_name/snapshot_name\"!")

    try:
        snap_info = es.snapshot.get(repository=repo, snapshot=snap)
        if OPTS.verbose:
            print "Deleting: %s" % snap_info
    except exceptions.NotFoundError:
        __error_exit("Snapshot [%s] could not be found in repo [%s]." % (snap, repo))

    try:
        es.snapshot.delete(repository=repo, snapshot=snap)
        print "Snapshot [%s] has been deleted from repo [%s]." % (snap, repo)
    except exceptions.NotFoundError:
        # A successful deletion can cause NotFoundError to bubble up for some reason.
        # Let's try to handle that bug gracefully by checking if the delete succeeded.
        try:
            time.sleep(2)
            # This should throw a NotFoundError if the delete succeeded.
            snap_info = es.snapshot.get(repository=repo, snapshot=snap)
            __error_exit("Failed to delete snapshot [%s]!\nSnapshot info: %s" % (snap, snap_info))
        except exceptions.NotFoundError:
            print "Snapshot [%s] has been deleted from repo [%s]." % (snap, repo)


def create_repo(es, repo_name, bucket, bucket_region, s3_role_arn, read_only='false'):
    '''Create an ElasticSearch snapshot repository within the given cluster.'''
    repo_body = ''.join(['{"type": "s3","settings": {',
                         '"bucket": "{}", "region": "{}",'.format(bucket, bucket_region),
                         '"role_arn": "{}", '.format(s3_role_arn),
                         '"readonly": {}'.format(read_only),
                         '}}'])

    es.snapshot.create_repository(repository=repo_name, body=repo_body)
    print "Repo [%s] has been created." % repo_name
    if OPTS.verbose:
        print es.snapshot.get_repository(repository=repo_name)


def delete_repo(es, repo_to_delete):
    '''Remove a repository from the specified cluster.'''
    try:
        if OPTS.verbose:
            print "Removing Repository: %s" % es.snapshot.get_repository(repository=repo_to_delete)

        es.snapshot.delete_repository(repository=repo_to_delete)
        print "Repo [%s] has been deleted." % repo_to_delete
    except exceptions.NotFoundError:
        __error_exit("Repository [%s] could not be found." % repo_to_delete)


def restore_snapshot(es, src_snapshot, indices, rename_pattern, rename_replacement):
    '''Restores the specified source repo/snapshot using the specified rename_* options.'''
    try:
        (repo, snap) = src_snapshot.split('/')
    except ValueError:
        __error_exit("You must specify the src_snapshot in the format \"repo_name/snapshot_name\"!")

    if rename_pattern == '' and rename_replacement == '':
        # indices will be restored with their original unmodified names
        restore_body = ''.join(['{',
                                '"indices": "{}","ignore_unavailable": false,'.format(indices),
                                '"include_global_state": false}'])
    else:
        # indices will be restored with replacement names, using the
        # rename_{pattern,replacement} option values
        restore_body = ''.join(['{',
                                '"indices": "{}",'.format(indices),
                                '"ignore_unavailable": false,"include_global_state": false,',
                                '"rename_pattern": "{}",'.format(rename_pattern),
                                '"rename_replacement": "{}"'.format(rename_replacement),
                                '}'])

    restore_resp = es.snapshot.restore(repository=repo, snapshot=snap, body=restore_body,
                                       wait_for_completion=False)
    print "Snapshot [%s] restoration has begun!" % src_snapshot
    if OPTS.verbose:
        print "ElasticSearch Response: %s" % restore_resp


def show_snapshots(es):
    '''Enumerate all repositories on the cluster and list all snapshots.'''
    repos_raw = es.cat.repositories(v=False)
    repos = []
    for line in repos_raw.split('\n'):
        if line == '':
            continue
        repos.append(line.split()[0].strip())

    # skip any AWS-maintained snapshot repos, since we won't have access...
    for bad_repo in BAD_REPO_NAMES:
        repos.remove(bad_repo)

    if not repos:
        print "No snapshot repositories were found."

    for r in repos:
        print "=== Snapshots in repo [%s] ===" % r

        snap_data = es.snapshot.get(repository=r, snapshot='*')
        for s in snap_data['snapshots']:
            print "   %s (%s)" % (s['snapshot'], s['state'])
        print ""


def show_aliases(es):
    '''Prints a listing of all aliases, along with the indexes they were found in.'''
    aliases_raw = es.indices.get_alias(index='*', name='*', allow_no_indices=True,
                                       expand_wildcards='all', ignore_unavailable=True)
    if not aliases_raw.keys():
        print "No aliases were found."
        return

    aliases = {}
    for index_name in aliases_raw.keys():
        for alias in aliases_raw[index_name]['aliases'].keys():
            try:
                aliases[alias].append(index_name)
            except KeyError:
                aliases[alias] = [index_name]
    for alias in aliases:
        print "%s: %s" % (alias, aliases[alias])


def create_alias(es, alias, indices):
    '''Creates an alias for the given indices.'''
    index_list = indices.split(",")
    index_cnt = len(index_list)

    put_body = "{\"actions\": ["
    for index in index_list:
        put_body = put_body + "{\"add\": {\"index\": \"%s\", \"alias\": \"%s\"}}" % (index, alias)
        index_cnt -= 1
        if index_cnt > 0:
            put_body = put_body + ','
    put_body = put_body + "]}"
    if OPTS.verbose:
        print "Creating alias: %s" % put_body
    put_resp = es.indices.put_alias(index=indices, name=alias, body=put_body)
    print "Alias created: %s ==> %s" % (alias, indices)
    if OPTS.verbose:
        print put_resp


def delete_alias(es, alias, indices):
    '''Deletes an alias from the specified indices.'''
    delete_resp = es.indices.delete_alias(index=indices, name=alias)
    if OPTS.verbose:
        print delete_resp
    print "Alias [%s] has been removed from indices [%s]." % (alias, indices)


def delete_index(es, index_name):
    '''Deletes the specified index from the cluster.'''
    delete_resp = es.indices.delete(index=index_name)
    print "Index [%s] has been deleted." % index_name
    if OPTS.verbose:
        print delete_resp


def show_indices(es):
    '''Prints a listing of all indices in the cluster.'''
    indices_raw = es.indices.get(index='*')
    if not indices_raw.keys():
        print "No indices were found."
        return

    for i in sorted(indices_raw.keys()):
        print i
    print ""


def watch_snapshot(es):
    '''Blocks until snapshot completion.'''
    in_progress = True
    start_time = datetime.now()
    while in_progress:
        in_progress = __snapshot_running(es)
        sys.stdout.write(".")
        sys.stdout.flush()
        time.sleep(30)
    end_time = datetime.now()
    sys.stdout.write("\n")
    delta = end_time - start_time
    print "Total elapsed time: %s" % delta



if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Provides functions for managing AWS ElasticSearch snapshots.")
    parser.add_argument('-f', '--config-file', dest='cfg_file', help="The yaml config to load settings from. (default: config.yaml)", default='config.yaml')
    parser.add_argument('-v', '--verbose', action='store_true', help="Provide more verbose output.")
    subparsers = parser.add_subparsers(dest='command', description="valid subcommands")

    create_repo_parser = subparsers.add_parser('create_repo', help="Registers a snapshot repository in the specified cluster.")
    create_repo_parser.add_argument('cluster_name', help="The cluster to register the repo in.")
    create_repo_parser.add_argument('repo_name', help="The name of the repository you'd like to register.")
    create_repo_parser.add_argument('-b', '--s3-bucket', dest='s3_bucket', help="The S3 bucket to use for the repo.")
    create_repo_parser.add_argument('-r', '--s3-region', dest='s3_region', default='us-west-2', help="The AWS S3 region for the bucket. (default: us-west-2)")
    create_repo_parser.add_argument('--read-only', action='store_true', dest='read_only', default=False, help="Make the repo read-only.")
    create_repo_parser.add_argument('--s3-role-arn', dest='s3_role_arn', default='', help="The IAM role ARN used by elasticsearch to access S3. (default: value from config.yaml)")

    delete_repo_parser = subparsers.add_parser('delete_repo', help="Delete the specified repo from ElasticSearch (does not delete snapshot data).")
    delete_repo_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to remove the snapshot repository from.")
    delete_repo_parser.add_argument('repo_name', help="The repository you'd like to remove.")

    create_snap_parser = subparsers.add_parser('create_snapshot', help="Create a snapshot on the specified cluster.")
    create_snap_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to snapshot.")
    create_snap_parser.add_argument('snapshot_name', metavar='repo/snapshot', help="The snapshot to be created.")
    create_snap_parser.add_argument('-i', '--indices', dest='indices', default='*', help="The list of indices to include in the snapshot. (default: all indices)")

    delete_snap_parser = subparsers.add_parser('delete_snapshot', help="Delete the specified snapshot from the repo.")
    delete_snap_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to delete the snapshot from.")
    delete_snap_parser.add_argument('snapshot_name', metavar='repo/snapshot', help="The snapshot to be deleted.")

    restore_snap_parser = subparsers.add_parser('restore_snapshot', help="Restore the specified snapshot onto the cluster.")
    restore_snap_parser.add_argument('snapshot_name', metavar='src_repo/src_snapshot', help="The snapshot to be restored.")
    restore_snap_parser.add_argument('-i', '--indices', dest='indices', default='*', help="The indices to restore from the snapshot. (default: all indices)")
    restore_snap_parser.add_argument('-p', '--rename-pattern', dest='rename_pattern', default='', help="The index pattern to match for renaming purposes. (i.e. 'my_index_(.*)')")
    restore_snap_parser.add_argument('-r', '--rename-replacement', dest='rename_replacement', default='',
                                     help="The replacement name to be given to the restored indexes. (i.e. 'my_restored_index_$1')")

    show_snaps_parser = subparsers.add_parser('show_snapshots', help="Show the status of all snapshots in all repos on the given cluster.")
    show_snaps_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to get the snapshot status from.")

    watch_snapshot_parser = subparsers.add_parser('watch_snapshot', help="Loops continuously while any snapshots are currently running, returning control only when the cluster is available again.")
    watch_snapshot_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to create/update the alias in.")

    create_alias_parser = subparsers.add_parser('set_alias', help="Create or update an alias to point to the specified index/indices.")
    create_alias_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to create/update the alias in.")
    create_alias_parser.add_argument('alias_name', help="The name of the alias you'd like to create/update.")
    create_alias_parser.add_argument('index', help="The index the alias should reference. Accepts wildcards such as 'index_foo_*'.")

    delete_alias_parser = subparsers.add_parser('delete_alias', help="Deletes the specified alias.")
    delete_alias_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to create/update the alias in.")
    delete_alias_parser.add_argument('alias_name', help="The name of the alias you'd like to delete.")
    delete_alias_parser.add_argument('-i', '--index', dest='index', default='*', help="The list of indices to remove the alias from. (optional; default = all indices)")

    show_aliases_parser = subparsers.add_parser('show_aliases', help="Show all aliases, along with the indices they reference.")
    show_aliases_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to create/update the alias in.")

    delete_index_parser = subparsers.add_parser('delete_index', help="Deletes the specified index.")
    delete_index_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to remove the index from.")
    delete_index_parser.add_argument('index', metavar='index_name', help="The index to delete from the cluster.")
    delete_index_parser.add_argument('-f', '--force', dest='force', action='store_true', default=False, help="Delete immediately without prompting.")

    show_indices_parser = subparsers.add_parser('show_indices', help="Prints a listing of all indices in the cluster.")
    show_indices_parser.add_argument('cluster_name', help="The cluster (as defined in the config file) to remove the index from.")

    subparsers.add_parser('show_config', help="Print the raw config to the console.")

    OPTS = parser.parse_args()

    # read the config file
    CFG_FILE = open(OPTS.cfg_file, 'r')
    CFG = yaml.load(CFG_FILE)
    CFG_FILE.close()

    ES_OPERATIONS = [
        'create_repo',
        'delete_repo',
        'create_snapshot',
        'delete_snapshot',
        'restore_snapshot',
        'show_snapshots',
        'watch_snapshot',
        'set_alias',
        'delete_alias',
        'show_aliases',
        'delete_index',
        'show_indices'
    ]

    # get ready for ElasticSearch operations
    if OPTS.command in ES_OPERATIONS:
        if not CFG['clusters'].has_key(OPTS.cluster_name):
            __error_exit("No key [%s] in 'clusters' section of file [%s]!\nAvailable clusters: %s"
                         % (OPTS.cluster_name, OPTS.cfg_file, CFG['clusters'].keys()))

        ES = elasticsearch_connection(CFG['clusters'][OPTS.cluster_name],
                                      CFG['username'],
                                      CFG['password'],
                                      CFG['ca_cert_path'])


        ###                                         ###
        ### Start processing the command & options! ###
        ###                                         ###

        if OPTS.command == 'create_repo':
            # if --s3-role-arn is supplied, we'll use that instead of the config.yaml value
            if OPTS.s3_role_arn == '':
                if OPTS.verbose:
                    print "No --s3-role-arn supplied. Using value from config.yaml..."
                ROLE_ARN = CFG['clusters'][OPTS.cluster_name]['s3_role_arn']
            else:
                ROLE_ARN = OPTS.s3_role_arn

            if OPTS.read_only:
                create_repo(ES, OPTS.repo_name, OPTS.s3_bucket, OPTS.s3_region, ROLE_ARN,
                            read_only='true')
            else:
                create_repo(ES, OPTS.repo_name, OPTS.s3_bucket, OPTS.s3_region, ROLE_ARN,
                            read_only='false')

        elif OPTS.command == 'delete_repo':
            delete_repo(ES, OPTS.repo_name)

        elif OPTS.command == 'create_snapshot':
            create_snapshot(ES, OPTS.indices, OPTS.snapshot_name)

        elif OPTS.command == 'delete_snapshot':
            delete_snapshot(ES, OPTS.snapshot_name)

        elif OPTS.command == 'restore_snapshot':
            # rename_pattern and rename_replacement are mutually dependent options -- either they're both supplied, or they're both ommitted.
            if (OPTS.rename_pattern == '' and OPTS.rename_replacement == '') or (OPTS.rename_pattern != '' and OPTS.rename_replacement != ''):
                restore_snapshot(ES, OPTS.snapshot_name, OPTS.indices, OPTS.rename_pattern, OPTS.rename_replacement)
            else:
                if OPTS.rename_pattern == '':
                    __error_exit("You must supply a --rename-replacement value when supplying a --rename-pattern!")
                elif OPTS.rename_replacement == '':
                    __error_exit("You must supply a --rename-pattern value when supplying a --rename-replacement!")
            # NOTE: We'll probably want to handle some additional options eventually, like ignore_unavailable or include_global_state.
            #       Also, we should probably add handling for "include_aliases: false" so we can delete/recreate aliases separately.

        elif OPTS.command == 'show_snapshots':
            show_snapshots(ES)

        elif OPTS.command == 'watch_snapshot':
            watch_snapshot(ES)

        elif OPTS.command == 'set_alias':
            create_alias(ES, OPTS.alias_name, OPTS.index)

        elif OPTS.command == 'delete_alias':
            delete_alias(ES, OPTS.alias_name, OPTS.index)

        elif OPTS.command == 'show_aliases':
            show_aliases(ES)

        elif OPTS.command == 'delete_index':
            if OPTS.force:
                delete_index(ES, OPTS.index)
            else:
                resp = raw_input("Are you sure you want to permanently delete index [%s] (y/n)? " % OPTS.index)
                if resp.lower() == 'y':
                    delete_index(ES, OPTS.index)
                else:
                    print "Not deleting index."
                    sys.exit(0)

        elif OPTS.command == 'show_indices':
            show_indices(ES)

        elif OPTS.command == 'show_config':
            print yaml.dump(CFG, default_flow_style=False)

        else:
            __error_exit("[%s] is not a valid subcommand!" % OPTS.command)

    else:
        __error_exit("[%s] is not a valid command!" % OPTS.command)


# vim: ts=4 sw=4 et
