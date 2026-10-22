import ast
from pathlib import Path

HERE=Path(__file__).parent
BOOT='a464df41-e391-4443-b8e8-ad7ecd052318'
GENERATION='4ebffc96-e25e-4583-a3b8-0d853fd90efd'
ROOT='/var/lib/cps-native-gpu/qualification/1f7d941a-872d-4453-a1ba-fd489d8aff14/cohorts/6ba3353d-bf13-4cad-9c35-3119dd279a67/ipc-kmsg-witness'

def literals(name):
    return {node.id if isinstance(node,ast.Name) else '':value for statement in ast.parse((HERE/name).read_text()).body
            if isinstance(statement,ast.Assign) for node in statement.targets
            for value in [ast.literal_eval(statement.value) if isinstance(statement.value,ast.Constant) else None]}

def test_only_exact_fresh_boot_and_qa_operator_path_are_selected():
    for name in ('ipc_endpoint.py','ipc_host_pid.py','kernel_witness_collector.py','kernel_witness_validator.py'):
        assert literals(name)['BOOT']==BOOT
    for name in ('kernel_witness_collector.py','kernel_witness_validator.py'):
        assert literals(name)['GENERATION']==GENERATION
    assert literals('kernel_witness_transport.py')['ROOT']==ROOT
    assert "Path('"+ROOT+"')" in (HERE/'kernel_witness_collector.py').read_text()
