import collections
import socket
import subprocess

import charmhelpers.core.hookenv as hookenv
import charms_openstack.charm
import charms_openstack.ip as os_ip

# import charms_openstack.sdn.odl as odl
# import charms_openstack.sdn.ovs as ovs


class GnocchiCharm(charms_openstack.charm.HAOpenStackCharm):

    # Internal name of charm
    service_name = name = 'gnocchi'

    # First release supported
    release = 'mitaka'

    # List of packages to install for this charm
    packages = ['gnocchi-api', 'gnocchi-metricd', 'python-apt']

    api_ports = {
        'apache2': {
            os_ip.PUBLIC: 8041,
            os_ip.ADMIN: 8041,
            os_ip.INTERNAL: 8041,
        }
    }

    service_type = 'gnocchi'
    default_service = 'apache2'
    services = ['haproxy', 'apache2 gnocchi-metricd', 'apache2']

    # Note that the hsm interface is optional - defined in config.yaml
    required_relations = ['shared-db', 'amqp', 'identity-service']

    restart_map = {

        '/etc/gnocchi/gnocchi.conf': services,
    }

    ha_resources = ['vips', 'haproxy']

    release_pkg = 'gnocchi-common'

    package_codenames = {
        'gnocchi-common': collections.OrderedDict([
            ('2', 'mitaka'),
            ('3', 'newton'),
            ('4', 'ocata'),
        ]),
    }


    sync_cmd = ['gnocchi-upgrade']

    def get_amqp_credentials(self):
        return ('gnocchi', 'gnocchi')

    def get_database_setup(self):
        return [{
            'database': 'gnocchi',
            'username': 'gnocchi',
            'hostname': hookenv.unit_private_ip() },]