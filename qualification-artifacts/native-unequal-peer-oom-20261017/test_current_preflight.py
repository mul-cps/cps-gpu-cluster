"""Current released Node image must pass; superseded process must fail before cap reads."""
import copy
import unittest
from unittest.mock import patch
import current_preflight as current

CURRENT_NODE = 'ghcr.io/mul-cps/cps-native-node@sha256:7e319bfcb546efa9ae2fea975dcf082460802578da0c804f60eb0c8f64c08bb0'
OLD_NODE = 'ghcr.io/mul-cps/cps-native-node@sha256:47d8e532409337c864d02fc608600b4aecea650075573690b4f17dcb7a670c7f'

class CohortTests(unittest.TestCase):
    def fixture(self, node_image):
        targets={'pods':{k:{'namespace':('jupyterhub' if k=='a' else 'cit-jhub'),'name':'lab-'+k,'uid':'00000000-0000-4000-8000-00000000000'+str(i),'cap_mib':(5120 if k=='a' else 10240)}for i,k in enumerate(('a','b'),1)},'node':{'namespace':'cps-native-system','name':'node-agent','uid':'00000000-0000-4000-8000-000000000003'},'observer':{'namespace':'gpu-operator','name':'cps-native-driver-control','uid':'00000000-0000-4000-8000-000000000004'}}
        actual={}
        for key,row in [*targets['pods'].items(),('node',targets['node']),('observer',targets['observer'])]:
            image=node_image if key=='node' else current.NOTEBOOK_IMAGE
            container='node-agent' if key=='node' else 'control' if key=='observer' else 'notebook'
            actual[row['name']]={'metadata':{'uid':row['uid']},'spec':{'nodeName':'k3s-wk-gpu2','hostPID':key=='observer','containers':[{'name':container,'image':image}]},'status':{'phase':'Running','containerStatuses':[{'name':container,'imageID':image,'ready':True,'restartCount':0,'state':{'running':{}}}]}}
        rows=[{'pod_uid':targets['pods'][k]['uid'],'identity':{'cgroup_inode':i}}for i,k in enumerate(('a','b'),1)]
        return targets,actual,rows

    def test_released_node_and_qualified_gpu_notebook_are_accepted(self):
        targets,actual,rows=self.fixture(CURRENT_NODE)
        with patch.object(current,'pod',side_effect=lambda row:copy.deepcopy(actual[row['name']])),patch.object(current,'command',return_value=rows):
            result=current.preflight({'manifest':targets})
        self.assertEqual(result['host']['targets'],rows)

    def test_superseded_node_is_rejected_before_any_cap_query(self):
        targets,actual,rows=self.fixture(OLD_NODE)
        with patch.object(current,'pod',side_effect=lambda row:copy.deepcopy(actual[row['name']])),patch.object(current,'command',side_effect=AssertionError('Cap query must not run')):
            with self.assertRaisesRegex(ValueError,'Exact qualified installed runtime image'):
                current.preflight({'manifest':targets})

if __name__=='__main__':unittest.main()
