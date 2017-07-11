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
            'identity-service.connected',
            'identity-service.available',  # enables SSL support
            'config.changed',
            'update-status']
        hook_set = {
            'when': {
                'render_config': (
                    'coordinator.available',
                    'shared-db.available',
                    'identity-service.available',
                    'storage-ceph.pools.available',
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
                ),
                'configure_ceph': (
                    'storage-ceph.available',
                ),
                'storage_ceph_connected': (
                    'storage-ceph.connected',
                ),
            },
            'when_not': {
                'storage_ceph_disconnected': (
                    'storage-ceph.connected',
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
        self.patch_object(handlers.charm, 'provide_charm_instance',
                          new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = \
            self.gnocchi_charm
        self.provide_charm_instance().__exit__.return_value = None

    def test_render_stuff(self):
        handlers.render_config('arg1', 'arg2')
        self.gnocchi_charm.render_with_interfaces.assert_called_once_with(
            ('arg1', 'arg2')
        )
        self.gnocchi_charm.assess_status.assert_called_once_with()
        self.gnocchi_charm.enable_apache2_site.assert_called_once_with()

    def test_init_db(self):
        handlers.init_db()
        self.gnocchi_charm.db_sync.assert_called_once_with()

    def test_storage_ceph_connected(self):
        mock_ceph = mock.MagicMock()
        handlers.storage_ceph_connected(mock_ceph)
        mock_ceph.create_pool.assert_called_once_with(
            handlers.gnocchi.CEPH_POOL_NAME
        )

    @mock.patch.object(handlers, 'hookenv')
    @mock.patch.object(handlers, 'ceph_helper')
    def test_configure_ceph(self, mock_ceph_helper, mock_hookenv):
        mock_ceph = mock.MagicMock()
        mock_ceph.key.return_value = 'testkey'
        mock_hookenv.service_name.return_value = 'gnocchi'
        handlers.configure_ceph(mock_ceph)
        mock_ceph_helper.create_keyring.assert_called_once_with(
            'gnocchi',
            'testkey',
        )
        mock_ceph.key.assert_called_once_with()

    @mock.patch.object(handlers, 'hookenv')
    @mock.patch.object(handlers, 'ceph_helper')
    def test_storage_ceph_disconnected(self, mock_ceph_helper,
                                       mock_hookenv):
        mock_hookenv.service_name.return_value = 'gnocchi'
        handlers.storage_ceph_disconnected()
        mock_ceph_helper.delete_keyring.assert_called_once_with('gnocchi')

    def test_provide_gnocchi_url(self):
        mock_gnocchi = mock.MagicMock()
        self.gnocchi_charm.public_url = "http://gnocchi:8041"
        handlers.provide_gnocchi_url(mock_gnocchi)
        mock_gnocchi.set_gnocchi_url.assert_called_once_with(
            "http://gnocchi:8041"
        )
