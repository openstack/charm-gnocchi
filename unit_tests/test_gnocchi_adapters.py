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

from __future__ import absolute_import
from __future__ import print_function

import mock

import charms_openstack.test_utils as test_utils

import charm.openstack.gnocchi as gnocchi


class TestAdapters(test_utils.PatchHelper):

    _mons = [
        '1.2.3.4:123',
        '1.2.3.5:123',
        '1.2.3.6:123',
    ]

    def test_storage_ceph(self):
        adapter = gnocchi.StorageCephRelationAdapter()
        adapter.relation = mock.MagicMock()
        adapter.relation.mon_hosts.return_value = self._mons
        self.assertEqual(adapter.monitors,
                         ','.join(self._mons))
        adapter.relation.mon_hosts.return_value = []
        self.assertEqual(adapter.monitors, None)
