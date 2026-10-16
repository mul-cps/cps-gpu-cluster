import copy, hashlib, importlib.metadata, json, pathlib, subprocess, sys
from cps_compute.policy import Policy, PolicyError
from cps_compute.native_qualification import NativeGroupQualification
from cps_compute.native_groups import NativeGroupDeployment, WORKLOAD_IMAGE
from e2x_course_hub.course_service.app import CourseServiceApp
from e2x_course_hub.cps.workspaces import WorkspaceService
b=json.loads(pathlib.Path('/fixture.json').read_text());policy=Policy(b['policy']);config=b['configuration'];before=copy.deepcopy(config)
mode=NativeGroupQualification.from_config(config,policy)
assert mode.workload_image.endswith('@sha256:531027c8e330d4ce818598e998a29d502433e9064f06a32dfc208a06ef2d0ba4')
assert mode.cap_mib('interactive-native-qualification-5')==5120 and mode.cap_mib('interactive-native-qualification-20')==20480
assert config==before and mode._qualification_config()==mode._config()
for name in mode.profiles:
 assert policy.catalog['profiles'][name]['enabled'] is False
 try:policy.resources(name)
 except PolicyError:pass
 else:raise AssertionError('Qualification must not enable ordinary access')
for mutate in [lambda c:c.update(workloadImage='ghcr.io/mul-cps/cps-jupyter-notebook:latest'),lambda c:c.update(gates={'passed':True}),lambda c:c['node_pool'].update(memory_budget_mib=51200)]:
 changed=copy.deepcopy(config);mutate(changed)
 try:NativeGroupQualification.from_config(changed,policy)
 except ValueError:pass
 else:raise AssertionError('Unsafe qualification input accepted')
try:NativeGroupDeployment.from_config(config,policy)
except ValueError:pass
else:raise AssertionError('Operator fixture must not become production proof')
legacy=copy.deepcopy(b)
for name in legacy['configuration']['profile_caps']:legacy['policy']['profiles'][name]['images']=[WORKLOAD_IMAGE]
old=Policy(legacy['policy']);legacy['configuration'].update(workloadImage=WORKLOAD_IMAGE,policy_hash=old.hash)
assert NativeGroupQualification.from_config(legacy['configuration'],old).workload_image==WORKLOAD_IMAGE
assert NativeGroupQualification.from_config({'enabled':False},None) is None
assert CourseServiceApp.__module__=='e2x_course_hub.course_service.app' and WorkspaceService.__module__=='e2x_course_hub.cps.workspaces'
subprocess.run([sys.executable,'-m','pip','check'],check=True,stdout=subprocess.DEVNULL)
print(json.dumps({'candidate531_and_legacy916_models_passed':True,'profiles_stay_disabled':True,'unsafe_inputs_denied':True,'production_model_denied':True,'source_application_imports_passed':True,'pip_check_passed':True,'python':sys.version.split()[0],'hardware_qualified':False,'live_deployed':False}))
