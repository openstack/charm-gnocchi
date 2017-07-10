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
        # reactive.barbican_handlers
        self.registered_hooks_test_helper(handlers, hook_set, defaults)


class TestRenderStuff(test_utils.PatchHelper):

    def test_render_stuff(self):
        gnocchi_charm = mock.MagicMock()
        self.patch_object(handlers.charm, 'provide_charm_instance',
                          new=mock.MagicMock())
        self.provide_charm_instance().__enter__.return_value = gnocchi_charm
        self.provide_charm_instance().__exit__.return_value = None
        handlers.render_config('arg1', 'arg2')
        gnocchi_charm.render_with_interfaces.assert_called_once_with(
            ('arg1', 'arg2')
        )
        gnocchi_charm.assess_status.assert_called_once_with()
        gnocchi_charm.enable_apache2_site.assert_called_once_with()
