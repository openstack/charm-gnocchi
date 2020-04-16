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

import os
import collections
import subprocess

import charmhelpers.contrib.openstack.utils as ch_utils
import charmhelpers.contrib.network.ip as ch_ip
import charmhelpers.core.host as host

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
            self.config['openstack-origin'])
        if (ch_utils.OPENSTACK_RELEASES.index(release) >=
                ch_utils.OPENSTACK_RELEASES.index('queens')):
            if '?' in uri:
                uri += '&binary_prefix=true'
            else:
                uri += '?binary_prefix=true'
        return uri


class GnocchiCharmRelationAdapaters(adapters.OpenStackAPIRelationAdapters):

    """
    Adapters collection to append specific adapters for Gnocchi
    """

    relation_adapters = {
        'storage_ceph': charms_openstack.plugins.CephRelationAdapter,
        'shared_db': GnocchiCharmDatabaseRelationAdapter,
        'cluster': adapters.PeerHARelationAdapter,
        'coordinator_memcached': adapters.MemcacheRelationAdapter,
    }


class GnochiCharmBase(charms_openstack.charm.HAOpenStackCharm,
                      charms_openstack.plugins.BaseOpenStackCephCharm):

    """
    Base class for shared charm functions for all package types
    """
    abstract_class = True

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

    required_relations = ['shared-db', 'identity-service',
                          'storage-ceph', 'coordinator-memcached']

    ha_resources = ['vips', 'haproxy', 'dnsha']

    adapters_class = GnocchiCharmRelationAdapaters

    def enable_webserver_site(self):
        """Enable Gnocchi Webserver sites if rendered or installed"""
        pass

    def get_database_setup(self):
        return [{
            'database': 'gnocchi',
            'username': 'gnocchi',
            'hostname': ch_ip.get_relation_ip(DB_INTERFACE)}, ]

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


class GnocchiCharm(GnochiCharmBase):

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
                'apache2', 'libapache2-mod-wsgi']

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
                'python3-memcache']


class GnocchiSnapCharm(GnochiCharmBase):

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
