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

from __future__ import absolute_import
from __future__ import print_function

import mock

import charms_openstack.test_utils as test_utils

import reactive.gnocchi_handlers as handlers


class TestRegisteredHooks(test_utils.TestRegisteredHooks):

    def test_hooks(self):
        defaults = [
            'charm.installed',
            'shared-db.connected',
            'ha.connected',
            'identity-service.connected',
            'config.changed',
            'config.rendered',
            'update-status',
            'charm.default-select-release',
            'certificates.available']
        hook_set = {
            'when': {
                'define_storage_states': (
                    'config.changed.storage-backend',
                ),
                'render_config': (
                    'coordinator-memcached.available',
                    'shared-db.available',
                    'identity-service.available',
                    'gnocchi-upgrade.ready',
                ),
                'init_db': (
                    'config.rendered',
                ),
                'cluster_connected': (
                    'ha.connected',
                ),
                'provide_gnocchi_url': (
                    'metric-service.connected',
                    'config.rendered',
                    'db.synced',
                ),
                'configure_ceph': (
                    'storage-ceph.available',
                ),
                'storage_ceph_connected': (
                    'storage-ceph.connected',
                ),
                'check_ceph_request_status': (
                    'storage-ceph.connected',
                ),
                'storage_ceph_disconnected': (
                    'storage-ceph.needed',
                ),
                'reset_state_create_pool_req_sent': (
                    'storage-ceph.needed',
                )
            },
            'when_not': {
                'storage_ceph_disconnected': (
                    'storage-ceph.connected',
                ),
                'cluster_connected': (
                    'ha.available',
                ),
                'init_db': (
                    'db.synced',
                ),
                'storage_ceph_connected': (
                    'ceph.create_pool.req.sent',
                ),
                'check_ceph_request_status': (
                    'storage-ceph.pools.available',
                ),
                'reset_state_create_pool_req_sent': (
                    'storage-ceph.connected',
                    'storage-ceph.pools.available',
                ),
            },
        }
        # test that the hooks were registered via the
        # reactive.gnocchi_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestHandlers(test_utils.PatchHelper):

    def setUp(self):
        super(TestHandlers, self).setUp()
        self.gnocchi_charm = mock.MagicMock()
        self.gnocchi_charm.gnocchi_user = 'gnocchi'
        self.gnocchi_charm.gnocchi_group = 'gnocchi'
        self.patch_object(handlers.charm, 'provide_charm_instance',
                          new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = \
            self.gnocchi_charm
        self.provide_charm_instance().__exit__.return_value = None

    def test_render_stuff(self):
        self.patch_object(handlers.reactive, 'set_state')
        self.patch_object(handlers.charm, 'optional_interfaces')

        handlers.render_config('arg1', 'arg2')
        self.gnocchi_charm.render_with_interfaces.assert_called_once_with(
            ('arg1', 'arg2')
        )
        self.gnocchi_charm.enable_webserver_site.assert_called_once_with()
        self.set_state.assert_called_once_with('config.rendered')

    def test_init_db(self):
        handlers.init_db()
        self.gnocchi_charm.db_sync.assert_called_once_with()

    @mock.patch.object(handlers, 'hookenv')
    def test_storage_ceph_connected(self, hookenv):
        mock_ceph = mock.MagicMock()
        hookenv.service_name.return_value = 'mygnocchi'
        handlers.storage_ceph_connected(mock_ceph)
        mock_ceph.create_pool.assert_called_once_with(
            'mygnocchi',
        )

    def test_configure_ceph(self):
        mock_ceph = mock.MagicMock()
        mock_ceph.key.return_value = 'testkey'
        handlers.configure_ceph(mock_ceph)
        self.gnocchi_charm.configure_ceph_keyring.assert_called_once_with(
            'testkey')
        mock_ceph.key.assert_called_once_with()

    def test_storage_ceph_disconnected(self):
        handlers.storage_ceph_disconnected()
        self.gnocchi_charm.delete_ceph_keyring.assert_called_once_with()

    @mock.patch.object(handlers.reactive.flags, 'is_flag_set')
    def test_provide_gnocchi_url(self, mock_is_flag_set):
        mock_is_flag_set.return_value = False
        mock_gnocchi = mock.MagicMock()
        self.gnocchi_charm.public_url = "http://gnocchi:8041"
        handlers.provide_gnocchi_url(mock_gnocchi)
        mock_gnocchi.set_gnocchi_url.assert_called_once_with(
            "http://gnocchi:8041"
        )

    @mock.patch.object(handlers.reactive.flags, 'is_flag_set')
    def test_provide_gnocchi_url_ha_connected(self, mock_is_flag_set):
        mock_is_flag_set.side_effect = [True, False]
        mock_gnocchi = mock.MagicMock()
        handlers.provide_gnocchi_url(mock_gnocchi)
        mock_gnocchi.set_gnocchi_url.assert_not_called()

    @mock.patch.object(handlers.reactive.flags, 'is_flag_set')
    def test_provide_gnocchi_url_ha_available(self, mock_is_flag_set):
        mock_is_flag_set.side_effect = [True, True]
        mock_gnocchi = mock.MagicMock()
        self.gnocchi_charm.public_url = "http://gnocchi:8041"
        handlers.provide_gnocchi_url(mock_gnocchi)
        mock_gnocchi.set_gnocchi_url.assert_called_once_with(
            "http://gnocchi:8041"
        )

    def test_reset_state_create_pool_req_sent(self):
        self.patch_object(handlers.reactive, 'remove_state')
        handlers.reset_state_create_pool_req_sent()
        self.remove_state.assert_called_once_with('ceph.create_pool.req.sent')
