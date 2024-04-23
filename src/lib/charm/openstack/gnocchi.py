# Copyright 2017 Canonical Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import os
import collections
import subprocess

import charmhelpers.contrib.openstack.utils as ch_utils
import charmhelpers.contrib.network.ip as ch_ip
import charmhelpers.core.host as host
import charmhelpers.core.hookenv as hookenv

import charms_openstack.charm
import charms_openstack.adapters as adapters
import charms_openstack.ip as os_ip
import charms_openstack.plugins


GNOCCHI_DIR = '/etc/gnocchi'
GNOCCHI_CONF = os.path.join(GNOCCHI_DIR, 'gnocchi.conf')
GNOCCHI_API_PASTE = os.path.join(GNOCCHI_DIR, 'api-paste.ini')
GNOCCHI_WEBSERVER_SITE = 'gnocchi-api'
GNOCCHI_WSGI_CONF = '/etc/apache2/sites-available/{}.conf'.format(
    GNOCCHI_WEBSERVER_SITE)

SNAP_PREFIX = '/var/snap/gnocchi/common'

GNOCCHI_DIR_SNAP = '{}{}'.format(SNAP_PREFIX, GNOCCHI_DIR)
GNOCCHI_CONF_SNAP = os.path.join(GNOCCHI_DIR_SNAP, 'gnocchi.conf')
GNOCCHI_WEBSERVER_SITE_SNAP = 'gnocchi-nginx'
GNOCCHI_NGINX_SITE_CONF_SNAP = '{}{}'.format(
    SNAP_PREFIX,
    '/etc/nginx/sites-enabled/{}.conf'.format(
        GNOCCHI_WEBSERVER_SITE_SNAP
    )
)
GNOCCHI_NGINX_CONF_SNAP = '{}{}'.format(SNAP_PREFIX,
                                        '/etc/nginx/nginx.conf')

CEPH_CONF = '/etc/ceph/ceph.conf'
CEPH_CONF_SNAP = '{}{}'.format(SNAP_PREFIX, CEPH_CONF)

CEPH_KEYRING = '/etc/ceph/ceph.client.{}.keyring'
CEPH_KEYRING_SNAP = '{}{}'.format(SNAP_PREFIX, CEPH_KEYRING)

DB_INTERFACE = 'shared-db'

EXTERNAL_CA_CERT_FILE = '/usr/local/share/ca-certificates/gnocchi-external.crt'

charms_openstack.charm.use_defaults('charm.default-select-package-type')
charms_openstack.charm.use_defaults('charm.default-select-release')


@charms_openstack.adapters.config_property
def log_config(config):
    if ch_utils.snap_install_requested():
        return os.path.join(SNAP_PREFIX,
                            'log/gnocchi-api.log')
    else:
        return '/var/log/gnocchi/gnocchi-api.log'


@charms_openstack.adapters.config_property
def ceph_config(config):
    if ch_utils.snap_install_requested():
        return CEPH_CONF_SNAP
    else:
        return CEPH_CONF


class GnocchiCharmDatabaseRelationAdapter(adapters.DatabaseRelationAdapter):
    """
    Overrides default class to add binary_prefix option to solve
    'Invalid utf8 character' warnings
    """

    def get_uri(self, prefix=None):
        uri = super(GnocchiCharmDatabaseRelationAdapter, self).get_uri(prefix)
        release = ch_utils.get_os_codename_install_source(
            self.charm_instance.options.openstack_origin)
        if (ch_utils.OPENSTACK_RELEASES.index(release) >=
                ch_utils.OPENSTACK_RELEASES.index('queens')):
            if '?' in uri:
                uri += '&binary_prefix=true'
            else:
                uri += '?binary_prefix=true'
        return uri


class GnocchiCharmRelationAdapters(adapters.OpenStackAPIRelationAdapters):

    """
    Adapters collection to append specific adapters for Gnocchi
    """
    relation_adapters = {
        'storage_ceph': charms_openstack.plugins.CephRelationAdapter,
        'shared_db': GnocchiCharmDatabaseRelationAdapter,
        'cluster': adapters.PeerHARelationAdapter,
        'coordinator_memcached': adapters.MemcacheRelationAdapter,
    }


class GnocchiCharmBase(charms_openstack.plugins.PolicydOverridePlugin,
                       charms_openstack.charm.HAOpenStackCharm,
                       charms_openstack.plugins.BaseOpenStackCephCharm):

    """
    Base class for shared charm functions for all package types
    """
    abstract_class = True

    healthcheck = {
        'option': 'httpchk GET /healthcheck',
        'http-check': 'expect status 200',
    }

    # Internal name of charm
    service_name = name = 'gnocchi'

    default_service = 'gnocchi-api'

    service_type = 'gnocchi'

    api_ports = {
        'gnocchi-api': {
            os_ip.PUBLIC: 8041,
            os_ip.ADMIN: 8041,
            os_ip.INTERNAL: 8041,
        }
    }

    ha_resources = ['vips', 'haproxy', 'dnsha']

    adapters_class = GnocchiCharmRelationAdapters

    # policyd override constants
    policyd_service_name = 'gnocchi'

    def enable_webserver_site(self):
        """Enable Gnocchi Webserver sites if rendered or installed"""
        pass

    def get_database_setup(self):
        return [{
            'database': 'gnocchi',
            'username': 'gnocchi',
            'hostname': ch_ip.get_relation_ip(DB_INTERFACE)}, ]

    @property
    def required_relations(self):
        _required_relations = ['shared-db',
                               'identity-service',
                               'coordinator-memcached']
        if self.options.storage_backend == 'ceph':
            _required_relations.append('storage-ceph')
        return _required_relations

    @property
    def mandatory_config(self):
        _mandatory_config = []
        if self.options.storage_backend == 's3':
            s3_config = ['s3-region-name',
                         's3-endpoint-url',
                         's3-access-key-id',
                         's3-secret-access-key']
            _mandatory_config.extend(s3_config)
        return _mandatory_config

    @property
    def gnocchi_user(self):
        '''Determine user gnocchi processes will run as

        :return string: user for gnocchi processes
        '''
        return self.user

    @property
    def gnocchi_group(self):
        '''Determine group gnocchi processes will run as

        :return string: group for gnocchi processes
        '''
        return self.group

    @property
    def ceph_keyring(self):
        '''Determine location for ceph keyring file

        :return string: location of keyrings
        '''
        _type_map = {
            'snap': CEPH_KEYRING_SNAP,
            'deb': CEPH_KEYRING,
        }
        try:
            return _type_map[self.package_type]
        except KeyError:
            return CEPH_KEYRING

    def db_sync(self):
        """Override db_sync to catch exceptions for the s3 backend.
        Perform a database sync using the command defined in the
        self.sync_cmd attribute. The services defined in self.services are
        restarted after the database sync.
        """
        if not self.db_sync_done() and hookenv.is_leader():
            try:
                f = open("/var/log/gnocchi/gnocchi-upgrade.log", "w+")
                subprocess.check_call(self.sync_cmd,
                                      stdout=f,
                                      stderr=subprocess.STDOUT)
                hookenv.leader_set({'db-sync-done': True})
                # Restart services immediately after db sync as
                # render_domain_config needs a working system
                self.restart_all()
            except subprocess.CalledProcessError as e:
                hookenv.status_set('blocked', 'An error occured while ' +
                                   'running gnocchi-upgrade. Logs available ' +
                                   'in /var/log/gnocchi/gnocchi-upgrade.log')
                hookenv.log(e, hookenv.DEBUG)
                raise e

    def do_openstack_upgrade_db_migration(self):
        """Overrides do_openstack_upgrade_db_migration for Openstack
        upgrades. This function's purpose is to run a database migration
        after the Openstack upgrade. A check of the S3 connection is
        required first to avoid a failed migration, in the case of an S3
        storage backend.
        :returns: None
        """
        self.db_sync()

    def states_to_check(self, required_relations=None):
        """Custom states to check function.

        Construct a custom set of connected and available states for each
        of the relations passed, along with error messages and new status
        conditions.

        :param self: Self
        :type self: GnocchiCharm instance
        :param required_relations: List of relations which overrides
                                   self.relations
        :type required_relations: list of strings
        :returns: {relation: [(state, err_status, err_msg), (...),]}
        :rtype: dict
        """
        states_to_check = super().states_to_check(required_relations)
        states_to_check["gnocchi-upgrade"] = [
            ("gnocchi-storage-configuration.ready",
             "blocked",
             "Mandatory S3 configuration parameters missing."),
            ("gnocchi-storage-authentication.ready",
             "blocked",
             "Authentication to the storage backend failed. " +
             "Please verify your S3 credentials."),
            ("gnocchi-storage-network.ready",
             "blocked",
             "Could not connect to the storage backend endpoint URL. " +
             "Please verify your network and your s3 endpoint URL."),
            ("gnocchi-upgrade.ready",
             "error",
             "Storage backend not ready. Check logs for troubleshooting.")
        ]
        return states_to_check

    def configure_external_tls(self):
        """Installs an external root CA to the gnocchi units, if provided.
        The purpose of this is to allow connection to an external S3 endpoint
        with encryption.
        :returns: None
        """
        if self.options.trusted_external_ca_cert:
            ca_cert = self.options.trusted_external_ca_cert.strip()
            hookenv.log("Writing tls ca cert {}".format(ca_cert), hookenv.INFO)
            cert_content = base64.b64decode(ca_cert).decode()
            try:
                with open(EXTERNAL_CA_CERT_FILE, 'w') as fd:
                    fd.write(cert_content)
                subprocess.call(['/usr/sbin/update-ca-certificates'])
            except (subprocess.CalledProcessError, PermissionError) as error:
                hookenv.status_set(
                    'blocked',
                    'An error occured while uploading the external ca cert.'
                )
                hookenv.log('configure_external_ssl failed: {}'.format(error),
                            hookenv.ERROR)
                return


class GnocchiCharm(GnocchiCharmBase):

    """
    Charm for Juju deployment of Gnocchi
    """

    # First release supported
    release = 'mitaka'

    # Deb package type
    package_type = 'deb'

    # List of packages to install for this charm
    packages = ['gnocchi-api', 'gnocchi-metricd', 'python-apt',
                'ceph-common', 'python-rados', 'python-keystonemiddleware',
                'apache2', 'libapache2-mod-wsgi', 'python-boto3']

    services = ['gnocchi-metricd', 'apache2']

    restart_map = {
        GNOCCHI_CONF: services,
        GNOCCHI_WSGI_CONF: ['apache2'],
        GNOCCHI_API_PASTE: ['apache2'],
        CEPH_CONF: services,
    }

    release_pkg = 'gnocchi-common'

    package_codenames = {
        'gnocchi-common': collections.OrderedDict([
            ('2', 'mitaka'),
            ('3', 'pike'),
            ('4', 'train'),
            ('4.3', 'ussuri'),
            ('4.4.0', 'victoria'),
            ('4.4.1', 'yoga'),  # wallaby, xena, yoga
            ('4.4.2', 'zed'),
            ('4.5.0', 'bobcat'),  # antelope, bobcat
            ('4.6.0', 'caracal'),
        ]),
    }

    sync_cmd = ['gnocchi-upgrade',
                '--log-file=/var/log/gnocchi/gnocchi-upgrade.log']

    # User and group for permissions management
    user = 'gnocchi'
    group = 'gnocchi'

    def install(self):
        super(GnocchiCharm, self).install()
        # NOTE(jamespage): always pause gnocchi-api service as we force
        #                  execution with Apache2+mod_wsgi
        host.service_pause('gnocchi-api')

    def enable_webserver_site(self):
        """Enable Gnocchi API apache2 site if rendered or installed"""
        if os.path.exists(GNOCCHI_WSGI_CONF):
            check_enabled = subprocess.call(
                ['a2query', '-s', GNOCCHI_WEBSERVER_SITE]
            )
            if check_enabled != 0:
                subprocess.check_call(['a2ensite',
                                       GNOCCHI_WEBSERVER_SITE])
                host.service_reload('apache2',
                                    restart_on_failure=True)


class GnocchiQueensCharm(GnocchiCharm):

    """
    Charm for deployment of Gnocchi >= Queens
    """

    release = 'queens'

    python_version = 3

    packages = ['gnocchi-api', 'gnocchi-metricd', 'python3-apt',
                'ceph-common', 'python3-rados', 'python3-keystonemiddleware',
                'python3-memcache', 'python3-boto3']


class GnocchiSnapCharm(GnocchiCharmBase):

    """
    Charm for Juju deployment of Gnocchi via Snap
    """

    # First release supported
    # NOTE(coreycb): snap install is only supported from ocata up.
    release = 'ocata'

    # Snap package type
    package_type = 'snap'

    # List of packages and snaps to install for this charm
    snaps = ['gnocchi']
    packages = ['ceph-common']

    services = ['snap.gnocchi.metricd',
                'snap.gnocchi.nginx',
                'snap.gnocchi.uwsgi']

    snap_codenames = {
        'gnocchi': collections.OrderedDict([
            ('3', 'ocata'),
            ('4', 'pike'),
        ]),
    }

    release_snap = 'gnocchi'

    restart_map = {
        GNOCCHI_CONF_SNAP: ['snap.gnocchi.metricd', 'snap.gnocchi.uwsgi'],
        GNOCCHI_NGINX_SITE_CONF_SNAP: ['snap.gnocchi.nginx'],
        GNOCCHI_NGINX_CONF_SNAP: ['snap.gnocchi.nginx'],
        CEPH_CONF_SNAP: ['snap.gnocchi.metricd', 'snap.gnocchi.uwsgi'],
    }

    sync_cmd = [
        '/snap/bin/gnocchi.upgrade',
        '--log-file=/var/snap/gnocchi/common/log/gnocchi-upgrade.log'
    ]

    # User and group for permissions management
    user = 'root'
    group = 'root'
