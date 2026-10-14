import asyncio,json,os,sys
from e2x_course_hub.cps.compute import ComputePolicyClient
v=json.load(sys.stdin)
async def run():
 client=ComputePolicyClient(os.environ['CPS_WORKSPACE_CONTROL_URL'],os.environ['CPS_WORKSPACE_CONTROL_TOKEN'],v['source'])
 status=await client.reservation_state(v['workspace'])
 assert status['active'] is False and status.get('attempt') is None
 print(json.dumps({'source':v['source'],'workspace':v['workspace'],'reservation':status}))
asyncio.run(run())
