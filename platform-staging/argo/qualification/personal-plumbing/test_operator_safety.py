"""Safety invariants for unexecuted operator and fixture administration paths."""
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import ssl
import unittest
from unittest.mock import patch


def module(name):
    spec=importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


operator=module('activation_operator')
fixtures=module('fixture_hub_users')
ownership=module('ownership_http')


class SafetyTests(unittest.TestCase):
    def test_qa_config_preserves_source_and_disables_storage_pod_clients(self):
        current={'state_directory':'/production','hubs':{'cps':{'canonical_people':{},'workspace_principals':{}},
            'cit':{'canonical_people':{},'workspace_principals':{}}},'storage':{'enabled':True},
            'artifacts':{'lifecycle':{'enabled':True}},'jobsets':{'enabled':True},'shutdownObserver':{'kubernetes':True}}
        before=copy.deepcopy(current)
        qa=ownership.qa_runtime(current,{'fixture-user':'fixture-canonical-person'})
        self.assertEqual(current,before)
        self.assertEqual(qa['state_directory'],'/tmp/qa-state')
        self.assertEqual(qa['argo_url'],'https://cps-argo-argo-workflows-server.cps-argo.svc.cluster.local:2746')
        self.assertFalse(qa['storage']['enabled']);self.assertFalse(qa['jobsets']['enabled'])
        self.assertFalse(qa['shutdownObserver']['kubernetes']);self.assertFalse(qa['artifacts']['lifecycle']['enabled'])
        self.assertEqual(qa['hubs']['cit']['canonical_people'],{})

    def test_privacy_probe_rejects_admin_before_contacting_gateway(self):
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'visitor';token.write_text('synthetic-only');token.chmod(0o600)
            spec={'gatewayUrl':'https://gateway.invalid','gatewayCaFile':ssl.get_default_verify_paths().cafile,
                  'visitors':[{'source':'cps','tokenFile':str(token),'expectedHubUser':'fixture-user'}]}
            with patch.object(ownership,'get',return_value=(200,{'name':'fixture-user','admin':True})) as get:
                with self.assertRaises(AssertionError):ownership.probe(spec)
                get.assert_called_once()
                self.assertEqual(get.call_args.args[0],'https://jupyterhub.dshl.unileoben.ac.at/hub/api/user')

    def test_missing_own_artifact_cannot_produce_passing_extended_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'visitor';token.write_text('synthetic-only');token.chmod(0o600)
            case={'source':'cps','tokenFile':str(token),'ownWorkflow':'own','foreignWorkflow':'foreign',
                  'unknownWorkflow':'unknown','ownNode':'own-node','foreignNode':'foreign-node','unknownNode':'unknown-node',
                  'expectedLogMarker':'controlled-log','expectedArtifactSha256':'unused'}
            spec={'gatewayUrl':'https://gateway.invalid','gatewayCaFile':ssl.get_default_verify_paths().cafile,'visitors':[case]}
            with patch.object(ownership,'probe',return_value={'passed':True,'cases':[{}]}),\
                 patch.object(ownership,'request',side_effect=[(200,{'content-type':'text/event-stream'},b'controlled-log'),(503,{},b'')]):
                with self.assertRaises(AssertionError):ownership.extended_probe(spec)

    def test_private_preparation_does_not_require_browser_flow_it_enables(self):
        evidence={'gatewayStateSnapshotVerified':True,'gatewayImage':'current-image',
            'hubDatabaseConfigSnapshotsVerified':{'cps':True,'cit':True},
            'activationGates':{'normalOwnerPrivacyQualified':True,'aliasInventoryReviewed':True,
                               'actualBrowserHubOAuthQualified':False}}
        operator.private_preparation_evidence(evidence,'current-image')
        evidence['activationGates']['normalOwnerPrivacyQualified']=False
        with self.assertRaises(AssertionError):operator.private_preparation_evidence(evidence,'current-image')

    def test_hub_registration_preserves_existing_roles_services_and_narrow_scope(self):
        for source in ('cps','cit'):
            existing_roles=[{'name':'console','scopes':['read:users']},{'name':'user','scopes':['self','access:services!service=other']}]
            c=SimpleNamespace(JupyterHub=SimpleNamespace(services=[{'name':'other'}],load_roles=copy.deepcopy(existing_roles)))
            with patch.object(Path,'read_text',return_value='synthetic-test-credential'):
                exec(operator.hub_module(source),{'c':c})
            self.assertEqual(c.JupyterHub.services[0],{'name':'other'})
            service=c.JupyterHub.services[1]
            self.assertEqual(service['oauth_client_allowed_scopes'],[])
            self.assertNotIn('url',service)
            self.assertEqual(service['oauth_redirect_uri'],operator.SOURCES[source][1]+'/argo/oauth_callback')
            self.assertEqual(c.JupyterHub.load_roles[0],existing_roles[0])
            self.assertEqual(c.JupyterHub.load_roles[1]['scopes'],existing_roles[1]['scopes']+['access:services!service='+source+'-argo-ui'])

    def test_hub_module_refuses_duplicate_service(self):
        c=SimpleNamespace(JupyterHub=SimpleNamespace(services=[{'name':'cps-argo-ui'}],load_roles=[]))
        with self.assertRaises(RuntimeError):exec(operator.hub_module('cps'),{'c':c})

    def test_focused_resources_have_no_public_route_and_only_reviewed_namespace_peers(self):
        resources=operator.rendered_objects()
        self.assertFalse(any(o['kind']=='Ingress' for o in resources))
        native=next(o for o in resources if o['metadata']['name']=='personal-argo-native-assets')
        peer=native['spec']['ingress'][0]['from'][0]
        self.assertEqual(peer['namespaceSelector']['matchLabels'],{'kubernetes.io/metadata.name':'cps-compute'})
        self.assertEqual(peer['podSelector']['matchExpressions'][0]['values'],['cps-argo-ui','cit-argo-ui'])
        self.assertEqual(native['spec']['ingress'][0]['ports'],[{'protocol':'TCP','port':2746}])
        self.assertTrue(next(o for o in resources if o['kind']=='CronJob')['spec']['suspend'])

    def test_cleanup_requires_creation_receipt_before_any_hub_or_cluster_operation(self):
        with tempfile.TemporaryDirectory() as directory:
            token=Path(directory)/'admin';token.write_text('synthetic-only');token.chmod(0o600)
            receipt=Path(directory)/'absent'
            with patch.object(fixtures,'request') as request,patch.object(fixtures.subprocess,'run') as run:
                with self.assertRaises(FileNotFoundError):fixtures.execute(token,receipt,True)
                request.assert_not_called();run.assert_not_called()
            receipt.write_text(json.dumps({'reviewSha256':'wrong','hubApi':fixtures.HUB,'createdUsers':fixtures.USERS}))
            with patch.object(fixtures,'request') as request,patch.object(fixtures.subprocess,'run') as run:
                with self.assertRaises(AssertionError):fixtures.execute(token,receipt,True)
                request.assert_not_called();run.assert_not_called()

    def test_rollback_refuses_changed_gateway_owned_fields(self):
        live={'spec':{'template':{'spec':{'containers':[{'name':'gateway','image':'concurrent-image'}],
              'volumes':[{'name':'config','secret':{'secretName':operator.RUNTIME_NEW}}]}}}}
        with patch.object(operator,'get',return_value=live),patch.object(operator,'replace') as replace:
            with self.assertRaises(AssertionError):operator.rollback_fields('previous-image',[],True)
            replace.assert_not_called()


if __name__=='__main__':unittest.main()
