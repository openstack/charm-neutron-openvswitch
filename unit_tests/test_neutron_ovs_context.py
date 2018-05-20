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

from test_utils import CharmTestCase
from test_utils import patch_open
from mock import patch, Mock
import neutron_ovs_context as context
import charmhelpers

_LSB_RELEASE_XENIAL = {
    'DISTRIB_CODENAME': 'xenial',
}

_LSB_RELEASE_TRUSTY = {
    'DISTRIB_CODENAME': 'trusty',
}

TO_PATCH = [
    'config',
    'unit_get',
    'get_host_ip',
    'network_get_primary_address',
    'glob',
    'PCINetDevices',
    'relation_ids',
    'relation_get',
    'related_units',
    'lsb_release',
]


def fake_context(settings):
    def outer():
        def inner():
            return settings
        return inner
    return outer


class OVSPluginContextTest(CharmTestCase):

    def setUp(self):
        super(OVSPluginContextTest, self).setUp(context, TO_PATCH)
        self.config.side_effect = self.test_config.get
        self.test_config.set('debug', True)
        self.test_config.set('verbose', True)
        self.test_config.set('use-syslog', True)
        self.network_get_primary_address.side_effect = NotImplementedError
        self.lsb_release.return_value = _LSB_RELEASE_XENIAL

    def tearDown(self):
        super(OVSPluginContextTest, self).tearDown()

    @patch('charmhelpers.contrib.openstack.context.config')
    @patch('charmhelpers.contrib.openstack.context.NeutronPortContext.'
           'resolve_ports')
    def test_data_port_name(self, mock_resolve_ports, config):
        self.test_config.set('data-port', 'br-data:em1')
        config.side_effect = self.test_config.get
        mock_resolve_ports.side_effect = lambda ports: ports
        self.assertEqual(
            charmhelpers.contrib.openstack.context.DataPortContext()(),
            {'em1': 'br-data'}
        )

    @patch('charmhelpers.contrib.openstack.context.is_phy_iface',
           lambda port: True)
    @patch('charmhelpers.contrib.openstack.context.config')
    @patch('charmhelpers.contrib.openstack.context.get_nic_hwaddr')
    @patch('charmhelpers.contrib.openstack.context.list_nics')
    def test_data_port_mac(self, list_nics, get_nic_hwaddr, config):
        machine_machs = {
            'em1': 'aa:aa:aa:aa:aa:aa',
            'eth0': 'bb:bb:bb:bb:bb:bb',
        }
        absent_mac = "cc:cc:cc:cc:cc:cc"
        config_macs = ("br-d1:%s br-d2:%s" %
                       (absent_mac, machine_machs['em1']))
        self.test_config.set('data-port', config_macs)
        config.side_effect = self.test_config.get
        list_nics.return_value = machine_machs.keys()
        get_nic_hwaddr.side_effect = lambda nic: machine_machs[nic]
        self.assertEqual(
            charmhelpers.contrib.openstack.context.DataPortContext()(),
            {'em1': 'br-d2'}
        )

    @patch.object(charmhelpers.contrib.openstack.utils,
                  'get_os_codename_package')
    @patch.object(charmhelpers.contrib.openstack.context, 'config',
                  lambda *args: None)
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    @patch.object(charmhelpers.contrib.openstack.context, 'config')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'is_clustered')
    @patch.object(charmhelpers.contrib.openstack.context, 'https')
    @patch.object(context.OVSPluginContext, '_ensure_packages')
    @patch.object(charmhelpers.contrib.openstack.context,
                  'neutron_plugin_attribute')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_private_ip')
    def test_neutroncc_context_api_rel(self, _unit_priv_ip, _npa, _ens_pkgs,
                                       _https, _is_clus, _unit_get,
                                       _config, _runits, _rids, _rget,
                                       _get_os_cdnm_pkg):
        def mock_npa(plugin, section, manager):
            if section == "driver":
                return "neutron.randomdriver"
            if section == "config":
                return "neutron.randomconfig"

        config = {'vlan-ranges': "physnet1:1000:1500 physnet2:2000:2500",
                  'use-syslog': True,
                  'verbose': True,
                  'debug': True,
                  'bridge-mappings': "physnet1:br-data physnet2:br-data",
                  'flat-network-providers': 'physnet3 physnet4',
                  'prevent-arp-spoofing': False,
                  'enable-dpdk': False}

        def mock_config(key=None):
            if key:
                return config.get(key)

            return config

        _get_os_cdnm_pkg.return_value = 'ocata'
        self.maxDiff = None
        self.config.side_effect = mock_config
        _npa.side_effect = mock_npa
        _unit_get.return_value = '127.0.0.13'
        _unit_priv_ip.return_value = '127.0.0.14'
        _is_clus.return_value = False
        _runits.return_value = ['unit1']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'l2-population': 'True',
            'enable-qos': 'True',
            'network-device-mtu': 1500,
            'overlay-network-type': 'gre',
            'enable-dvr': 'True',
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.get_host_ip.return_value = '127.0.0.15'
        napi_ctxt = context.OVSPluginContext()
        expect = {
            'neutron_security_groups': True,
            'distributed_routing': True,
            'verbose': True,
            'extension_drivers': 'qos',
            'local_ip': '127.0.0.15',
            'network_device_mtu': 1500,
            'veth_mtu': 1500,
            'config': 'neutron.randomconfig',
            'use_syslog': True,
            'enable_dpdk': False,
            'firewall_driver': 'iptables_hybrid',
            'network_manager': 'neutron',
            'debug': True,
            'core_plugin': 'neutron.randomdriver',
            'neutron_plugin': 'ovs',
            'neutron_url': 'https://127.0.0.13:9696',
            'l2_population': True,
            'overlay_network_type': 'gre',
            'polling_interval': 2,
            'rpc_response_timeout': 60,
            'report_interval': 30,
            'network_providers': 'physnet3,physnet4',
            'bridge_mappings': 'physnet1:br-data,physnet2:br-data',
            'vlan_ranges': 'physnet1:1000:1500,physnet2:2000:2500',
            'prevent_arp_spoofing': False,
        }
        self.assertEqual(expect, napi_ctxt())

    @patch.object(charmhelpers.contrib.openstack.utils,
                  'get_os_codename_package')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    @patch.object(charmhelpers.contrib.openstack.context, 'config')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'is_clustered')
    @patch.object(charmhelpers.contrib.openstack.context, 'https')
    @patch.object(context.OVSPluginContext, '_ensure_packages')
    @patch.object(charmhelpers.contrib.openstack.context,
                  'neutron_plugin_attribute')
    @patch.object(charmhelpers.contrib.openstack.context, 'unit_private_ip')
    def test_neutroncc_context_api_rel_disable_security(self,
                                                        _unit_priv_ip, _npa,
                                                        _ens_pkgs,
                                                        _https, _is_clus,
                                                        _unit_get,
                                                        _config, _runits,
                                                        _rids, _rget,
                                                        _get_os_cdnm_pkg):
        def mock_npa(plugin, section, manager):
            if section == "driver":
                return "neutron.randomdriver"
            if section == "config":
                return "neutron.randomconfig"

        _get_os_cdnm_pkg.return_value = 'ocata'
        _npa.side_effect = mock_npa
        _config.return_value = 'ovs'
        _unit_get.return_value = '127.0.0.13'
        _unit_priv_ip.return_value = '127.0.0.14'
        _is_clus.return_value = False
        self.test_config.set('disable-security-groups', True)
        _runits.return_value = ['unit1']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'l2-population': 'True',
            'enable-qos': 'True',
            'network-device-mtu': 1500,
            'overlay-network-type': 'gre',
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.get_host_ip.return_value = '127.0.0.15'
        napi_ctxt = context.OVSPluginContext()
        expect = {
            'distributed_routing': False,
            'neutron_alchemy_flags': {},
            'neutron_security_groups': False,
            'verbose': True,
            'extension_drivers': 'qos',
            'local_ip': '127.0.0.15',
            'veth_mtu': 1500,
            'network_device_mtu': 1500,
            'config': 'neutron.randomconfig',
            'use_syslog': True,
            'enable_dpdk': False,
            'firewall_driver': 'iptables_hybrid',
            'network_manager': 'neutron',
            'debug': True,
            'core_plugin': 'neutron.randomdriver',
            'neutron_plugin': 'ovs',
            'neutron_url': 'https://127.0.0.13:9696',
            'l2_population': True,
            'overlay_network_type': 'gre',
            'polling_interval': 2,
            'rpc_response_timeout': 60,
            'sriov_vfs_blanket': 'auto',
            'report_interval': 30,
            'bridge_mappings': 'physnet1:br-data',
            'vlan_ranges': 'physnet1:1000:2000',
            'prevent_arp_spoofing': True,
        }
        self.maxDiff = None
        self.assertEqual(expect, napi_ctxt())


class DHCPAgentContextTest(CharmTestCase):

    def setUp(self):
        super(DHCPAgentContextTest, self).setUp(context, TO_PATCH)
        self.config.side_effect = self.test_config.get

    def tearDown(self):
        super(DHCPAgentContextTest, self).tearDown()

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    def test_default_availability_zone_not_provided(self, _runits, _rids,
                                                    _rget):
        _runits.return_value = ['neutron-api/0']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'enable-dvr': 'True',
            'l2-population': 'True',
            'overlay-netweork-type': 'vxlan',
            'network-device-mtu': 1500,
            'dns-domain': 'openstack.example.'
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = None
        self.assertEqual(
            context.DHCPAgentContext()(),
            {'dns_domain': 'openstack.example.',
             'dns_servers': None}
        )
        self.relation_ids.assert_called_with('neutron-plugin')
        self.relation_get.assert_called_once_with(
            'default_availability_zone',
            rid='rid1',
            unit='nova-compute/0')

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    def test_default_availability_zone_provided(self, _runits, _rids, _rget):
        _runits.return_value = ['neutron-api/0']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'enable-dvr': 'True',
            'l2-population': 'True',
            'overlay-netweork-type': 'vxlan',
            'network-device-mtu': 1500,
            'dns-domain': 'openstack.example.'
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.test_config.set('dns-servers', '8.8.8.8,4.4.4.4')
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = 'nova'
        self.assertEqual(
            context.DHCPAgentContext()(),
            {'availability_zone': 'nova',
             'dns_domain': 'openstack.example.',
             'dns_servers': '8.8.8.8,4.4.4.4'}
        )
        self.relation_ids.assert_called_with('neutron-plugin')
        self.relation_get.assert_called_once_with(
            'default_availability_zone',
            rid='rid1',
            unit='nova-compute/0')

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    def test_no_dns_domain(self, _runits, _rids, _rget):
        _runits.return_value = ['neutron-api/0']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'enable-dvr': 'True',
            'l2-population': 'True',
            'overlay-netweork-type': 'vxlan',
            'network-device-mtu': 1500,
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.test_config.set('dns-servers', '8.8.8.8')
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = 'nova'
        self.assertEqual(
            context.DHCPAgentContext()(),
            {'availability_zone': 'nova',
             'dns_servers': '8.8.8.8'}
        )
        self.relation_ids.assert_called_with('neutron-plugin')
        self.relation_get.assert_called_once_with(
            'default_availability_zone',
            rid='rid1',
            unit='nova-compute/0')

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    def test_dnsmasq_flags(self, _runits, _rids, _rget):
        _runits.return_value = ['neutron-api/0']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'enable-dvr': 'True',
            'l2-population': 'True',
            'overlay-netweork-type': 'vxlan',
            'network-device-mtu': 1500,
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = None
        self.test_config.set('dnsmasq-flags', 'dhcp-userclass=set:ipxe,iPXE,'
                                              'dhcp-match=set:ipxe,175,'
                                              'server=1.2.3.4')
        self.assertEqual(
            context.DHCPAgentContext()(),
            {
                'dnsmasq_flags': {
                    'dhcp-userclass': 'set:ipxe,iPXE',
                    'dhcp-match': 'set:ipxe,175',
                    'server': '1.2.3.4',
                },
                'dns_servers': None,
            }
        )


class L3AgentContextTest(CharmTestCase):

    def setUp(self):
        super(L3AgentContextTest, self).setUp(context, TO_PATCH)
        self.config.side_effect = self.test_config.get

    def tearDown(self):
        super(L3AgentContextTest, self).tearDown()

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    def test_dvr_enabled(self, _runits, _rids, _rget):
        _runits.return_value = ['unit1']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'enable-dvr': 'True',
            'l2-population': 'True',
            'overlay-network-type': 'vxlan',
            'network-device-mtu': 1500,
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.assertEqual(
            context.L3AgentContext()(), {'agent_mode': 'dvr',
                                         'external_configuration_new': True}
        )

    @patch.object(charmhelpers.contrib.openstack.context, 'relation_get')
    @patch.object(charmhelpers.contrib.openstack.context, 'relation_ids')
    @patch.object(charmhelpers.contrib.openstack.context, 'related_units')
    def test_dvr_disabled(self, _runits, _rids, _rget):
        _runits.return_value = ['unit1']
        _rids.return_value = ['rid2']
        rdata = {
            'neutron-security-groups': 'True',
            'enable-dvr': 'False',
            'l2-population': 'True',
            'overlay-network-type': 'vxlan',
            'network-device-mtu': 1500,
        }
        _rget.side_effect = lambda *args, **kwargs: rdata
        self.assertEqual(context.L3AgentContext()(), {'agent_mode': 'legacy'})


class SharedSecretContext(CharmTestCase):

    def setUp(self):
        super(SharedSecretContext, self).setUp(context,
                                               TO_PATCH)
        self.config.side_effect = self.test_config.get

    @patch('os.path')
    @patch('uuid.uuid4')
    def test_secret_created_stored(self, _uuid4, _path):
        _path.exists.return_value = False
        _uuid4.return_value = 'secret_thing'
        with patch_open() as (_open, _file):
            self.assertEqual(context.get_shared_secret(),
                             'secret_thing')
            _open.assert_called_with(
                context.SHARED_SECRET.format('quantum'), 'w')
            _file.write.assert_called_with('secret_thing')

    @patch('os.path')
    def test_secret_retrieved(self, _path):
        _path.exists.return_value = True
        with patch_open() as (_open, _file):
            _file.read.return_value = 'secret_thing\n'
            self.assertEqual(context.get_shared_secret(),
                             'secret_thing')
            _open.assert_called_with(
                context.SHARED_SECRET.format('quantum'), 'r')

    @patch.object(context, 'NeutronAPIContext')
    @patch.object(context, 'get_shared_secret')
    def test_shared_secretcontext_dvr(self, _shared_secret,
                                      _NeutronAPIContext):
        _NeutronAPIContext.side_effect = fake_context({'enable_dvr': True})
        _shared_secret.return_value = 'secret_thing'
        self.assertEqual(context.SharedSecretContext()(),
                         {'shared_secret': 'secret_thing'})

    @patch.object(context, 'NeutronAPIContext')
    @patch.object(context, 'get_shared_secret')
    def test_shared_secretcontext_nodvr(self, _shared_secret,
                                        _NeutronAPIContext):
        _NeutronAPIContext.side_effect = fake_context({'enable_dvr': False})
        _shared_secret.return_value = 'secret_thing'
        self.assertEqual(context.SharedSecretContext()(), {})


class MockPCIDevice(object):
    '''Simple wrapper to mock pci.PCINetDevice class'''
    def __init__(self, address):
        self.pci_address = address


TEST_CPULIST_1 = "0-3"
TEST_CPULIST_2 = "0-7,16-23"
TEST_CPULIST_3 = "0,4,8,12,16,20,24"
DPDK_DATA_PORTS = (
    "br-phynet3:fe:16:41:df:23:fe "
    "br-phynet1:fe:16:41:df:23:fd "
    "br-phynet2:fe:f2:d0:45:dc:66"
)
BOND_MAPPINGS = (
    "bond0:fe:16:41:df:23:fe "
    "bond0:fe:16:41:df:23:fd "
    "bond1:fe:f2:d0:45:dc:66"
)
PCI_DEVICE_MAP = {
    'fe:16:41:df:23:fd': MockPCIDevice('0000:00:1c.0'),
    'fe:16:41:df:23:fe': MockPCIDevice('0000:00:1d.0'),
}


class TestDPDKUtils(CharmTestCase):

    def setUp(self):
        super(TestDPDKUtils, self).setUp(context, TO_PATCH)
        self.config.side_effect = self.test_config.get

    def test_parse_cpu_list(self):
        self.assertEqual(context.parse_cpu_list(TEST_CPULIST_1),
                         [0, 1, 2, 3])
        self.assertEqual(context.parse_cpu_list(TEST_CPULIST_2),
                         [0, 1, 2, 3, 4, 5, 6, 7,
                          16, 17, 18, 19, 20, 21, 22, 23])
        self.assertEqual(context.parse_cpu_list(TEST_CPULIST_3),
                         [0, 4, 8, 12, 16, 20, 24])

    @patch.object(context, 'parse_cpu_list', wraps=context.parse_cpu_list)
    def test_numa_node_cores(self, _parse_cpu_list):
        self.glob.glob.return_value = [
            '/sys/devices/system/node/node0'
        ]
        with patch_open() as (_, mock_file):
            mock_file.read.return_value = TEST_CPULIST_1
            self.assertEqual(context.numa_node_cores(),
                             {'0': [0, 1, 2, 3]})
        self.glob.glob.assert_called_with('/sys/devices/system/node/node*')
        _parse_cpu_list.assert_called_with(TEST_CPULIST_1)

    def test_resolve_dpdk_bridges(self):
        self.test_config.set('data-port', DPDK_DATA_PORTS)
        _pci_devices = Mock()
        _pci_devices.get_device_from_mac.side_effect = PCI_DEVICE_MAP.get
        self.PCINetDevices.return_value = _pci_devices
        self.assertEqual(context.resolve_dpdk_bridges(),
                         {'0000:00:1c.0': 'br-phynet1',
                          '0000:00:1d.0': 'br-phynet3'})

    def test_resolve_dpdk_bonds(self):
        self.test_config.set('bond-mappings', BOND_MAPPINGS)
        _pci_devices = Mock()
        _pci_devices.get_device_from_mac.side_effect = PCI_DEVICE_MAP.get
        self.PCINetDevices.return_value = _pci_devices
        self.assertEqual(context.resolve_dpdk_bonds(),
                         {'0000:00:1c.0': 'bond0',
                          '0000:00:1d.0': 'bond0'})


DPDK_PATCH = [
    'parse_cpu_list',
    'numa_node_cores',
    'resolve_dpdk_bridges',
    'glob',
]

NUMA_CORES_SINGLE = {
    '0': [0, 1, 2, 3]
}

NUMA_CORES_MULTI = {
    '0': [0, 1, 2, 3],
    '1': [4, 5, 6, 7]
}


class TestOVSDPDKDeviceContext(CharmTestCase):

    def setUp(self):
        super(TestOVSDPDKDeviceContext, self).setUp(context,
                                                    TO_PATCH + DPDK_PATCH)
        self.config.side_effect = self.test_config.get
        self.test_context = context.OVSDPDKDeviceContext()
        self.test_config.set('enable-dpdk', True)

    def test_device_whitelist(self):
        '''Test device whitelist generation'''
        self.resolve_dpdk_bridges.return_value = [
            '0000:00:1c.0',
            '0000:00:1d.0'
        ]
        self.assertEqual(self.test_context.device_whitelist(),
                         '-w 0000:00:1c.0 -w 0000:00:1d.0')

    def test_socket_memory(self):
        '''Test socket memory configuration'''
        self.glob.glob.return_value = ['a']
        self.assertEqual(self.test_context.socket_memory(),
                         '1024')

        self.glob.glob.return_value = ['a', 'b']
        self.assertEqual(self.test_context.socket_memory(),
                         '1024,1024')

        self.test_config.set('dpdk-socket-memory', 2048)
        self.assertEqual(self.test_context.socket_memory(),
                         '2048,2048')

    def test_cpu_mask(self):
        '''Test generation of hex CPU masks'''
        self.numa_node_cores.return_value = NUMA_CORES_SINGLE
        self.assertEqual(self.test_context.cpu_mask(), '0x01')

        self.numa_node_cores.return_value = NUMA_CORES_MULTI
        self.assertEqual(self.test_context.cpu_mask(), '0x11')

        self.test_config.set('dpdk-socket-cores', 2)
        self.assertEqual(self.test_context.cpu_mask(), '0x33')

    def test_context_no_devices(self):
        '''Ensure that DPDK is disable when no devices detected'''
        self.resolve_dpdk_bridges.return_value = []
        self.assertEqual(self.test_context(), {})

    def test_context_devices(self):
        '''Ensure DPDK is enabled when devices are detected'''
        self.resolve_dpdk_bridges.return_value = [
            '0000:00:1c.0',
            '0000:00:1d.0'
        ]
        self.numa_node_cores.return_value = NUMA_CORES_SINGLE
        self.glob.glob.return_value = ['a']
        self.assertEqual(self.test_context(), {
            'cpu_mask': '0x01',
            'device_whitelist': '-w 0000:00:1c.0 -w 0000:00:1d.0',
            'dpdk_enabled': True,
            'socket_memory': '1024'
        })


class TestDPDKDeviceContext(CharmTestCase):

    def setUp(self):
        super(TestDPDKDeviceContext, self).setUp(context,
                                                 TO_PATCH + DPDK_PATCH)
        self.config.side_effect = self.test_config.get
        self.test_context = context.DPDKDeviceContext()

    def test_context(self):
        self.resolve_dpdk_bridges.return_value = [
            '0000:00:1c.0',
            '0000:00:1d.0'
        ]
        self.assertEqual(self.test_context(), {
            'devices': ['0000:00:1c.0', '0000:00:1d.0'],
            'driver': 'uio_pci_generic'
        })
        self.config.assert_called_with('dpdk-driver')

    def test_context_none_driver(self):
        self.test_config.set('dpdk-driver', 'none')
        self.resolve_dpdk_bridges.return_value = [
            '0000:00:1c.0',
            '0000:00:1d.0'
        ]
        self.assertEqual(self.test_context(), {})
        self.config.assert_called_with('dpdk-driver')


class TestRemoteRestartContext(CharmTestCase):

    def setUp(self):
        super(TestRemoteRestartContext, self).setUp(context,
                                                    TO_PATCH)
        self.config.side_effect = self.test_config.get

    def test_restart_trigger_present(self):
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = {
            'restart-trigger': '8f73-f3adb96a90d8',
        }
        self.assertEqual(
            context.RemoteRestartContext()(),
            {'restart_trigger': '8f73-f3adb96a90d8'}
        )
        self.relation_ids.assert_called_with('neutron-plugin')

    def test_restart_trigger_present_alt_relation(self):
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = {
            'restart-trigger': '8f73-f3adb96a90d8',
        }
        self.assertEqual(
            context.RemoteRestartContext(['neutron-control'])(),
            {'restart_trigger': '8f73-f3adb96a90d8'}
        )
        self.relation_ids.assert_called_with('neutron-control')

    def test_restart_trigger_present_multi_relation(self):
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        ids = [
            {'restart-trigger': '8f73'},
            {'restart-trigger': '2ac3'}]
        self.relation_get.side_effect = lambda rid, unit: ids.pop()
        self.assertEqual(
            context.RemoteRestartContext(
                ['neutron-plugin', 'neutron-control'])(),
            {'restart_trigger': '2ac3-8f73'}
        )
        self.relation_ids.assert_called_with('neutron-control')

    def test_restart_trigger_absent(self):
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = {}
        self.assertEqual(context.RemoteRestartContext()(), {})

    def test_restart_trigger_service(self):
        self.relation_ids.return_value = ['rid1']
        self.related_units.return_value = ['nova-compute/0']
        self.relation_get.return_value = {
            'restart-trigger-neutron': 'neutron-uuid',
        }
        self.assertEqual(
            context.RemoteRestartContext()(),
            {'restart_trigger_neutron': 'neutron-uuid'}
        )


class TestFirewallDriver(CharmTestCase):

    TO_PATCH = [
        'config',
        'lsb_release',
    ]

    def setUp(self):
        super(TestFirewallDriver, self).setUp(context,
                                              self.TO_PATCH)
        self.config.side_effect = self.test_config.get

    def test_get_firewall_driver_xenial_unset(self):
        self.lsb_release.return_value = _LSB_RELEASE_XENIAL
        self.assertEqual(context._get_firewall_driver(),
                         context.IPTABLES_HYBRID)

    def test_get_firewall_driver_xenial_openvswitch(self):
        self.test_config.set('firewall-driver', 'openvswitch')
        self.lsb_release.return_value = _LSB_RELEASE_XENIAL
        self.assertEqual(context._get_firewall_driver(),
                         context.OPENVSWITCH)

    def test_get_firewall_driver_xenial_invalid(self):
        self.test_config.set('firewall-driver', 'foobar')
        self.lsb_release.return_value = _LSB_RELEASE_XENIAL
        self.assertEqual(context._get_firewall_driver(),
                         context.IPTABLES_HYBRID)

    def test_get_firewall_driver_trusty_openvswitch(self):
        self.test_config.set('firewall-driver', 'openvswitch')
        self.lsb_release.return_value = _LSB_RELEASE_TRUSTY
        self.assertEqual(context._get_firewall_driver(),
                         context.IPTABLES_HYBRID)
