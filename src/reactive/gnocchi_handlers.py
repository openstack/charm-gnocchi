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

import boto3
import botocore

import charm.openstack.gnocchi as gnocchi  # noqa

import charmhelpers.core.hookenv as hookenv

charm.use_defaults(
    'charm.installed',
    'shared-db.connected',
    'identity-service.connected',
    'config.changed',
    'config.rendered',
    'update-status',
    'certificates.available',
    'cluster.available',
)

required_interfaces = ['coordinator-memcached.available',
                       'shared-db.available',
                       'identity-service.available']

if hookenv.config('storage-backend').lower() == 'ceph':
    required_interfaces.append('storage-ceph.pools.available')


storage_config = ['config.changed.storage-backend',
                  'config.changed.s3-endpoint-url',
                  'config.changed.s3-region-name',
                  'config.changed.s3-access-key-id',
                  'config.changed.s3-secret-access-key']


@reactive.when_any(*storage_config)
def storage_backend_connection():
    """Test the connection to the S3 backend provided."""
    reactive.clear_flag('gnocchi-upgrade.ready')
    reactive.clear_flag('storage-ceph.needed')
    reactive.set_flag('gnocchi-storage-configuration.ready')
    reactive.set_flag('gnocchi-storage-authentication.ready')
    reactive.set_flag('gnocchi-storage-network.ready')

    with charm.provide_charm_instance() as charm_class:
        if charm_class.options.storage_backend == 's3':
            kwargs = {
                'region_name': charm_class.options.s3_region_name,
                'aws_access_key_id': charm_class.options.s3_access_key_id,
                'aws_secret_access_key':
                    charm_class.options.s3_secret_access_key,
                'endpoint_url': charm_class.options.s3_endpoint_url,
            }
            for value in kwargs.values():
                if not value:
                    hookenv.log('Mandatory S3 configuration parameters ' +
                                'missing.', hookenv.DEBUG)
                    reactive.clear_flag('gnocchi-storage-configuration.ready')
                    return

            try:
                boto3.client('s3', **kwargs)
                hookenv.log('S3 successfully reachable.', hookenv.DEBUG)
                reactive.set_flag('gnocchi-upgrade.ready')

            except botocore.exceptions.ClientError as e:
                hookenv.log("Authentication to S3 backend failed. Error : " +
                            "{}".format(e), hookenv.DEBUG)
                reactive.clear_flag('gnocchi-storage-authentication.ready')
                return
            except botocore.exceptions.EndpointConnectionError as e:
                hookenv.log("Could not connect to the endpoint URL: Error : " +
                            "{}".format(e), hookenv.DEBUG)
                reactive.clear_flag('gnocchi-storage-network.ready')
                return
            except botocore.exceptions.SSLError as e:
                # this status check does not check for ssl validation
                reactive.set_flag('gnocchi-upgrade.ready')
                return
            except Exception as e:
                hookenv.log("An error occured when trying to reach the S3 " +
                            "backend: {}".format(e), hookenv.DEBUG)
                return
        elif charm_class.options.storage_backend == 'ceph':
            reactive.set_flag('storage-ceph.needed')
            reactive.set_flag('gnocchi-upgrade.ready')
            return
        else:
            reactive.set_flag('gnocchi-upgrade.ready')


@reactive.when('gnocchi-upgrade.ready')
@reactive.when(*required_interfaces)
def render_config(*args):
    """Render the configuration for charm when all the interfaces are
    available.

    Note that the storage-ceph interface is optional and thus is only
    used if it is available.
    """

    with charm.provide_charm_instance() as charm_class:
        charm_class.upgrade_if_available(args)
        charm_class.configure_ssl()
        charm_class.render_with_interfaces(args)
        charm_class.enable_webserver_site()
    hookenv.log("Configuration rendered", hookenv.DEBUG)
    reactive.set_state('config.rendered')


# db_sync checks if sync has been done so rerunning is a noop.
@reactive.when('config.rendered')
@reactive.when_not('db.synced')
def init_db():
    with charm.provide_charm_instance() as charm_class:
        charm_class.db_sync()
        charm_class.assess_status()
    hookenv.log("Database synced", hookenv.DEBUG)
    reactive.set_state('db.synced')


@reactive.when('ha.connected')
@reactive.when_not('ha.available')
def cluster_connected(hacluster):
    """Configure HA resources in corosync"""
    with charm.provide_charm_instance() as charm_class:
        charm_class.configure_ha_resources(hacluster)
        charm_class.assess_status()


@reactive.when_not('ceph.create_pool.req.sent')
@reactive.when('storage-ceph.connected')
def storage_ceph_connected(ceph):
    ceph.create_pool(hookenv.service_name())
    reactive.set_state('ceph.create_pool.req.sent')


@reactive.when('storage-ceph.available')
def configure_ceph(ceph):
    with charm.provide_charm_instance() as charm_instance:
        key = ceph.key()
        if key and isinstance(key, str):
            charm_instance.configure_ceph_keyring(key)
        else:
            hookenv.log("No ceph keyring data is available")


@reactive.when_not('storage-ceph.pools.available')
@reactive.when('storage-ceph.connected')
def check_ceph_request_status(ceph):
    ceph.changed()


@reactive.when('storage-ceph.needed')
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


@reactive.when('storage-ceph.needed')
@reactive.when_not('storage-ceph.connected')
@reactive.when_not('storage-ceph.pools.available')
def reset_state_create_pool_req_sent():
    reactive.remove_state('ceph.create_pool.req.sent')
