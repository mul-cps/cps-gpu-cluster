import copy,json,tempfile,unittest
from pathlib import Path
import kai_placement_render as r
import kai_placement_run as q
NODE='k3s-wk-gpu3';UID='7b3b5113-158d-4e0d-bd63-898a508fe806'
PEERS={'k3s-wk-gpu2':'3336cdd5-d245-436e-b57c-2f66c6dcaa41'}
QUAL='cps.unileoben.ac.at/upstream-gpu-sharing'
TAINT={'key':'cps.unileoben.ac.at/maintenance','value':'upstream-pilot','effect':'NoSchedule'}
def selection():
 return dict(node=NODE,node_uid=UID,node_ip='10.21.0.40',gpu_uuids=['GPU-0a9f2da8-59f5-1cb0-9ead-d9fce56b69e5','GPU-e7a56fad-ce29-f7d7-380a-3b5ae62a0b2a'],expected_boot_id='11111111-1111-4111-8111-111111111111',driver_pod='driver',driver_pod_uid='22222222-2222-4222-8222-222222222222',driver_cid='a'*64,fractiond_pod='fractiond',fractiond_pod_uid='33333333-3333-4333-8333-333333333333',fractiond_cid='b'*64,release_reference='offline-root-release',ssh_target='ubuntu@10.21.0.40',ssh_key='/home/bjoern/.ssh/id_ed25519')
def node():
 return {'metadata':{'name':NODE,'uid':UID,'labels':{'nvidia.com/gpu.memory':'40960'}},'spec':{'unschedulable':False,'taints':[TAINT.copy()]},'status':{'conditions':[{'type':'Ready','status':'True'}],'addresses':[{'type':'InternalIP','address':'10.21.0.40'}],'nodeInfo':{'bootID':selection()['expected_boot_id'],'kernelVersion':'7.0.0-43-generic','osImage':'Ubuntu 26.04.1 LTS'}}}
def peers():
 return [{'metadata':{'name':n,'uid':u,'labels':{QUAL:'qualified'}},'status':{'conditions':[{'type':'Ready','status':'True'}]}}for n,u in PEERS.items()]
class Candidate(unittest.TestCase):
 def test_only_exact_accepted_peer_allowed_without_selected_qualification(self):
  self.assertEqual(q.validate_qualified_nodes(peers(),NODE,UID,PEERS),[{'name':'k3s-wk-gpu2','uid':PEERS['k3s-wk-gpu2'],'ready':True}])
 def test_reject_qualified_selected_replaced_unready_extra_peer(self):
  for change in ['selected','uid','unready','extra','deleting']:
   rows=peers()
   if change=='selected':rows.append({'metadata':{'name':NODE,'uid':UID,'labels':{QUAL:'qualified'}},'status':{'conditions':[{'type':'Ready','status':'True'}]}})
   if change=='uid':rows[0]['metadata']['uid']='changed'
   if change=='unready':rows[0]['status']['conditions'][0]['status']='False'
   if change=='extra':rows.append(copy.deepcopy(rows[0]))
   if change=='deleting':rows[0]['metadata']['deletionTimestamp']='now'
   with self.subTest(change=change),self.assertRaises((RuntimeError,ValueError)):q.validate_qualified_nodes(rows,NODE,UID,PEERS)
 def test_render_exact_candidate_selector_taint_and_payload(self):
  with tempfile.TemporaryDirectory()as t:
   f=Path(t)/'selection.json';s=selection();f.write_text(json.dumps(s))
   args=['--candidate-selection',str(f),'--node',NODE,'--operator-selected-worker',NODE,'--node-ip',s['node_ip'],'--gpu-a',s['gpu_uuids'][0],'--gpu-b',s['gpu_uuids'][1],'--expected-boot-id',s['expected_boot_id'],'--expected-module-srcversion','10301D70B8ED1758BC717E9','--accepted-qualified-peer','k3s-wk-gpu2='+PEERS['k3s-wk-gpu2'],'--output',t+'/out']
   a=r.arguments(args);cm,pods,summary=r.render(a)
   self.assertEqual(len(pods),15)
   for p in pods.values():
    self.assertEqual(p['spec']['nodeSelector'],{'kubernetes.io/hostname':NODE})
    self.assertEqual(p['spec']['tolerations'],[{**TAINT,'operator':'Equal'}])
    self.assertNotIn('nodeName',p['spec']);self.assertNotIn('runtimeClassName',p['spec'])
   self.assertEqual(summary['candidate_selection'],s)
 def test_candidate_node_rejects_all_identity_and_fence_changes(self):
  import candidate_guard as g
  g.validate_node(node(),selection())
  for change in ['qualified','uid','boot','cordon','taint-absent','taint-value','extra-taint']:
   n=node()
   if change=='qualified':n['metadata']['labels'][QUAL]='qualified'
   if change=='uid':n['metadata']['uid']='replaced'
   if change=='boot':n['status']['nodeInfo']['bootID']='old'
   if change=='cordon':n['spec']['unschedulable']=True
   if change=='taint-absent':n['spec']['taints']=[]
   if change=='taint-value':n['spec']['taints'][0]['value']='other'
   if change=='extra-taint':n['spec']['taints'].append({'key':'other','effect':'NoSchedule'})
   with self.subTest(change=change),self.assertRaises(ValueError):g.validate_node(n,selection())
 def test_payload_all_manifests_and_sequence_unchanged_except_admin_scheduling(self):
  import importlib.util
  from types import SimpleNamespace
  here=Path(__file__).parent
  spec=importlib.util.spec_from_file_location('original_renderer',here/'originals/kai_placement_render.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);old.HISTORICAL=here/'inputs'
  s=selection();a=SimpleNamespace(node=NODE,node_ip=s['node_ip'],operator_selected_worker=NODE,accepted_qualified_peers=PEERS,gpu_a=s['gpu_uuids'][0],gpu_b=s['gpu_uuids'][1],expected_boot_id=s['expected_boot_id'],expected_module_srcversion='10301D70B8ED1758BC717E9',run_id='kai-offline',namespace='gpu-operator',queue='cps-interactive',candidate_selection=s)
  c0,p0,e0=old.render(a);c1,p1,e1=r.render(a)
  self.assertEqual(c0,c1);self.assertEqual(e0['sequence'],e1['sequence'])
  for role in p0:
   p0[role]['spec'].pop('nodeSelector');p1[role]['spec'].pop('nodeSelector');p1[role]['spec'].pop('tolerations')
  self.assertEqual(p0,p1)
 def test_operand_replacement_refused(self):
  import candidate_guard as g
  s=selection();p={'metadata':{'name':s['fractiond_pod'],'uid':s['fractiond_pod_uid']},'spec':{'nodeName':NODE},'status':{'containerStatuses':[{'name':'fractiond','ready':True,'state':{'running':{}},'containerID':'containerd://'+s['fractiond_cid']}]}}
  g.validate_operand(p,s,'fractiond')
  p['status']['containerStatuses'][0]['containerID']='containerd://'+'c'*64
  with self.assertRaises(ValueError):g.validate_operand(p,s,'fractiond')
  p['status']['containerStatuses'][0]['containerID']='containerd://'+s['fractiond_cid'];p['metadata']['uid']='replaced'
  with self.assertRaises(ValueError):g.validate_operand(p,s,'fractiond')
 def test_cli_default_render_has_no_transport_and_release_mismatch_refuses(self):
  import subprocess,os,sys
  with tempfile.TemporaryDirectory()as t:
   d=Path(t);f=d/'selection.json';s=selection();f.write_text(json.dumps(s));b=d/'bin';b.mkdir()
   for n in ['kubectl','ssh']:
    x=b/n;x.write_text('#!/bin/sh\necho TRANSPORT_FORBIDDEN >&2\nexit 91\n');x.chmod(0o755)
   args=['--candidate-selection',str(f),'--node',NODE,'--operator-selected-worker',NODE,'--node-ip',s['node_ip'],'--gpu-a',s['gpu_uuids'][0],'--gpu-b',s['gpu_uuids'][1],'--expected-boot-id',s['expected_boot_id'],'--expected-module-srcversion','10301D70B8ED1758BC717E9','--accepted-qualified-peer','k3s-wk-gpu2='+PEERS['k3s-wk-gpu2'],'--output',str(d/'out')]
   cmd=[sys.executable,str(Path(__file__).with_name('kai_placement_run.py')),*args]
   env={**os.environ,'PATH':str(b)+os.pathsep+os.environ['PATH']}
   result=subprocess.run(cmd,text=True,capture_output=True,env=env);self.assertEqual(result.returncode,0,result.stderr);self.assertNotIn('TRANSPORT_FORBIDDEN',result.stderr)
   result=subprocess.run(cmd+['--execute','--parent-idle-release','WRONG','--ssh-target',s['ssh_target'],'--ssh-key',s['ssh_key']],text=True,capture_output=True,env=env)
   self.assertNotEqual(result.returncode,0);self.assertIn('release/SSH mismatch',result.stderr);self.assertNotIn('TRANSPORT_FORBIDDEN',result.stderr)
if __name__=='__main__':unittest.main()
