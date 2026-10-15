"""CIT upstream refresh must be requested separately from Hub-to-Dex scopes."""
from pathlib import Path
import yaml

VALUES=Path(__file__).parents[2]/'cluster-maintenance/clusters/cit-cps-gpu/system/auth/dex/values.yaml'


def test_cit_oidc_connector_requests_upstream_refresh_without_changing_client():
    config=yaml.safe_load(VALUES.read_text())['config']
    row=next(c for c in config['connectors'] if c['id']=='cit')
    assert row['type']=='oidc'
    upstream=row['config']
    assert upstream['scopes']==['profile','email','offline_access']
    assert upstream['issuer']=='https://auth.dshl.unileoben.ac.at/application/o/dex-rancher-broker/'
    assert upstream['clientID']=='qlPmVf0I9embINVWrDqSjWIjoD6HrTwx6TbEUYXq'
    assert upstream['clientSecret']=='$DEX_CIT_CLIENT_SECRET'
    assert upstream['redirectURI']=='https://dex.dshl.unileoben.ac.at/callback'
    assert upstream['insecureEnableGroups'] is True


def test_cps_connector_and_existing_static_clients_are_not_reconfigured():
    config=yaml.safe_load(VALUES.read_text())['config']
    cps=next(c for c in config['connectors'] if c['id']=='cps')['config']
    assert 'scopes' not in cps
    assert cps['clientSecret']=='$DEX_CPS_CLIENT_SECRET'
    assert {c['id'] for c in config['staticClients']}=={'rancher','jupyterhub','cit-jupyterhub'}
    assert next(c for c in config['staticClients'] if c['id']=='cit-jupyterhub')['secret']=='$DEX_CIT_JHUB_CLIENT_SECRET'
