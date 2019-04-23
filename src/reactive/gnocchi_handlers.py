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

import charms_openstack.charm as charm
import charms.reactive as reactive

import charm.openstack.gnocchi as gnocchi  # noqa

import charmhelpers.core.hookenv as hookenv

charm.use_defaults(
    'charm.installed',
    'shared-db.connected',
    'identity-service.connected',
    'identity-service.available',  # enables SSL support
    'config.changed',
    'update-status')

required_interfaces = ['coordinator-memcached.available',
                       'shared-db.available',
                       'identity-service.available',
                       'storage-ceph.pools.available']


@reactive.when_not_all(*required_interfaces)
def disable_services():
    with charm.provide_charm_instance() as charm_class:
        charm_class.disable_services()


@reactive.when(*required_interfaces)
def render_config(*args):
    """Render the configuration for charm when all the interfaces are
    available.
    """
    with charm.provide_charm_instance() as charm_class:
        charm_class.upgrade_if_available(args)
        charm_class.configure_ssl()
        charm_class.enable_services()
        charm_class.render_with_interfaces(args)
        charm_class.enable_webserver_site()
        charm_class.assess_status()
    hookenv.log("Configuration rendered", hookenv.DEBUG)
    reactive.set_state('config.rendered')


# db_sync checks if sync has been done so rerunning is a noop
@reactive.when('config.rendered')
@reactive.when_not('db.synced')
def init_db():
    with charm.provide_charm_instance() as charm_class:
        charm_class.db_sync()
    hookenv.log("Database synced", hookenv.DEBUG)
    reactive.set_state('db.synced')


@reactive.when('ha.connected')
@reactive.when_not('ha.available')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    with charm.provide_charm_instance() as charm_class:
        charm_class.configure_ha_resources(hacluster)
        charm_class.assess_status()


@reactive.when('storage-ceph.connected')
def storage_ceph_connected(ceph):
    ceph.create_pool(hookenv.service_name())


@reactive.when('storage-ceph.available')
def configure_ceph(ceph):
    with charm.provide_charm_instance() as charm_instance:
        charm_instance.configure_ceph_keyring(ceph.key())


@reactive.when_not('storage-ceph.connected')
def storage_ceph_disconnected():
    with charm.provide_charm_instance() as charm_instance:
        charm_instance.delete_ceph_keyring()


@reactive.when('metric-service.connected')
@reactive.when('config.rendered')
@reactive.when('db.synced')
def provide_gnocchi_url(metric_service):
    # Reactive endpoints are only fully functional in their respective relation
    # hooks. So we cannot rely on ha.is_clustered() which would return
    # False when not in a relation hook. Use flags instead.
    # Check if the optional relation, ha is connected. If it is,
    # check if it is available.
    if (reactive.flags.is_flag_set('ha.connected') and
            not reactive.flags.is_flag_set('ha.available')):
        hookenv.log("Hacluster is related but not yet clustered",
                    hookenv.DEBUG)
        return
    with charm.provide_charm_instance() as charm_class:
        hookenv.log("Providing gnocchi URL: {}"
                    .format(charm_class.public_url), hookenv.DEBUG)
        metric_service.set_gnocchi_url(charm_class.public_url)
