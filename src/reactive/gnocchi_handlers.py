# Copyright 2016 Canonical Ltd
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

import charmhelpers.contrib.storage.linux.ceph as ceph_helper
import charmhelpers.core.hookenv as hookenv

charm.use_defaults(
    'charm.installed',
    'shared-db.connected',
    'identity-service.connected',
    'identity-service.available',  # enables SSL support
    'config.changed',
    'update-status')


@reactive.when('shared-db.available')
@reactive.when('identity-service.available')
@reactive.when('storage-ceph.available')
@reactive.when('storage-ceph.pools.available')
def render_config(*args):
    """Render the configuration for charm when all the interfaces are
    available.
    """
    with charm.provide_charm_instance() as charm_class:
        charm_class.render_with_interfaces(args)
        charm_class.enable_apache2_site()
        charm_class.assess_status()
    reactive.set_state('config.rendered')


# db_sync checks if sync has been done so rerunning is a noop
@reactive.when('config.rendered')
def init_db():
    with charm.provide_charm_instance() as charm_class:
        charm_class.db_sync()


@reactive.when('ha.connected')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    with charm.provide_charm_instance() as charm_class:
        charm_class.configure_ha_resources(hacluster)
        charm_class.assess_status()


@reactive.when('storage-ceph.connected')
def storage_ceph_connected(ceph):
    ceph.create_pool(gnocchi.CEPH_POOL_NAME)


@reactive.when('storage-ceph.available')
def configure_ceph(ceph):
    ceph_helper.create_keyring(hookenv.service_name(),
                               ceph.key())


@reactive.when_not('storage-ceph.connected')
def storage_ceph_disconnected():
    ceph_helper.delete_keyring(hookenv.service_name())
