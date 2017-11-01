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


GNOCCHI_DIR = '/etc/gnocchi'
GNOCCHI_CONF = os.path.join(GNOCCHI_DIR, 'gnocchi.conf')
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


# TODO(jamespage): charms.openstack
class StorageCephRelationAdapter(adapters.OpenStackRelationAdapter):

    """
    Adapter for the CephClientRequires relation interface.
    """

    interface_type = "ceph-client"

    @property
    def monitors(self):
        """
        Comma separated list of hosts that should be used
        to access Ceph.
        """
        hosts = sorted(self.relation.mon_hosts())
        if len(hosts) > 0:
            return ','.join(hosts)
        else:
            return None


class GnocchiCharmRelationAdapaters(adapters.OpenStackAPIRelationAdapters):

    """
    Adapters collection to append specific adapters for Gnocchi
    """

    relation_adapters = {
        'storage_ceph': StorageCephRelationAdapter,
        'shared_db': adapters.DatabaseRelationAdapter,
        'cluster': adapters.PeerHARelationAdapter,
        'coordinator_memcached': adapters.MemcacheRelationAdapter,
    }


class GnochiCharmBase(charms_openstack.charm.HAOpenStackCharm):

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

    ha_resources = ['vips', 'haproxy']

    adapters_class = GnocchiCharmRelationAdapaters

    def enable_webserver_site(self):
        """Enable Gnocchi Webserver sites if rendered or installed"""
        pass

    def get_database_setup(self):
        return [{
            'database': 'gnocchi',
            'username': 'gnocchi',
            'hostname': ch_ip.get_relation_ip(DB_INTERFACE)}, ]

    def disable_services(self):
        '''Disable all services related to gnocchi'''
        for svc in self.services:
            host.service_pause(svc)

    def enable_services(self):
        '''Enable all services related to gnocchi'''
        for svc in self.services:
            host.service_resume(svc)

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
        CEPH_CONF: services,
    }

    release_pkg = 'gnocchi-common'

    package_codenames = {
        'gnocchi-common': collections.OrderedDict([
            ('2', 'mitaka'),
            ('3', 'newton'),
            ('4', 'pike'),
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
            ('2', 'mitaka'),
            ('3', 'newton'),
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
