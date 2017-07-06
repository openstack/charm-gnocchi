import os
import collections
import subprocess

import charmhelpers.core.hookenv as hookenv
import charmhelpers.core.host as host

import charms_openstack.charm
import charms_openstack.adapters as adapters
import charms_openstack.ip as os_ip


GNOCCHI_DIR = '/etc/gnocchi'
GNOCCHI_CONF = os.path.join(GNOCCHI_DIR, 'gnocchi.conf')
GNOCCHI_APACHE_SITE = 'gnocchi-api'
GNOCCHI_WSGI_CONF = '/etc/apache2/sites-available/{}.conf'.format(
    GNOCCHI_APACHE_SITE)

CEPH_CONF = '/etc/ceph/ceph.conf'

CEPH_POOL_NAME = 'gnocchi'


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
        hosts = self.relation.mon_hosts()
        if len(hosts) > 1:
            return ','.join(hosts)
        else:
            return None


class GnocchiCharmRelationAdapaters(adapters.OpenStackAPIRelationAdapters):

    """
    Adapters collection to append ceph-client adapter for Gnocchi
    """

    relation_adapters = {
        'storage_ceph': StorageCephRelationAdapter,
        'shared_db': adapters.DatabaseRelationAdapter,
        'cluster': adapters.PeerHARelationAdapter,
    }


class GnocchiCharm(charms_openstack.charm.HAOpenStackCharm):

    """
    Charm for Juju deployment of Gnocchi
    """

    # Internal name of charm
    service_name = name = 'gnocchi'

    # First release supported
    release = 'mitaka'

    # List of packages to install for this charm
    packages = ['gnocchi-api', 'gnocchi-metricd', 'python-apt',
                'ceph-common', 'python-rados', 'python-keystonemiddleware',
                'apache2', 'libapache2-mod-wsgi']

    api_ports = {
        'gnocchi-api': {
            os_ip.PUBLIC: 8041,
            os_ip.ADMIN: 8041,
            os_ip.INTERNAL: 8041,
        }
    }

    default_service = 'gnocchi-api'

    service_type = 'gnocchi'

    services = ['gnocchi-metricd', 'apache2']

    required_relations = ['shared-db', 'identity-service', 'storage-ceph']

    restart_map = {
        GNOCCHI_CONF: services,
        GNOCCHI_WSGI_CONF: ['apache2'],
        CEPH_CONF: services,
    }

    ha_resources = ['vips', 'haproxy']

    release_pkg = 'gnocchi-common'

    package_codenames = {
        'gnocchi-common': collections.OrderedDict([
            ('2', 'mitaka'),
            ('3', 'newton'),
            ('4', 'pike'),
        ]),
    }

    sync_cmd = ['gnocchi-upgrade']

    adapters_class = GnocchiCharmRelationAdapaters

    def install(self):
        super(GnocchiCharm, self).install()
        # NOTE(jamespage): always pause gnocchi-api service as we force
        #                  execution with Apache2+mod_wsgi
        host.service_pause('gnocchi-api')

    def enable_apache2_site(self):
        """Enable Gnocchi API apache2 site if rendered or installed"""
        if os.path.exists(GNOCCHI_WSGI_CONF):
            check_enabled = subprocess.call(
                ['a2query', '-s', GNOCCHI_APACHE_SITE]
            )
            if check_enabled != 0:
                subprocess.check_call(['a2ensite',
                                       GNOCCHI_APACHE_SITE])
                host.service_reload('apache2',
                                    restart_on_failure=True)

    def get_database_setup(self):
        return [{
            'database': 'gnocchi',
            'username': 'gnocchi',
            'hostname': hookenv.unit_private_ip()}, ]
