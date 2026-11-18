package checkpointadmissiontest
import("encoding/json";"os";"testing";"github.com/google/cel-go/cel")
func TestActualPolicyCEL(t *testing.T){
 raw,e:=os.ReadFile("../admission/policy.json");if e!=nil{t.Fatal(e)};var p map[string]interface{};if e=json.Unmarshal(raw,&p);e!=nil{t.Fatal(e)}
 s:=p["spec"].(map[string]interface{});expr:=s["validations"].([]interface{})[0].(map[string]interface{})["expression"].(string);cond:=s["matchConditions"].([]interface{})[0].(map[string]interface{})["expression"].(string)
 env,e:=cel.NewEnv(cel.Variable("object",cel.DynType),cel.Variable("request",cel.DynType));if e!=nil{t.Fatal(e)}
 ast,issues:=env.Compile(expr);if issues.Err()!=nil{t.Fatal(issues.Err())};pr,e:=env.Program(ast);if e!=nil{t.Fatal(e)}
 a,issues:=env.Compile(cond);if issues.Err()!=nil{t.Fatal(issues.Err())};cp,e:=env.Program(a);if e!=nil{t.Fatal(e)}
 cases:=[]struct{name,body string;allow bool}{
 {"old-default-rw",`{"volumes":[{"name":"d","persistentVolumeClaim":{"claimName":"compute-state"}}]}`,false},
 {"old-explicit-rw",`{"volumes":[{"name":"d","persistentVolumeClaim":{"claimName":"compute-state","readOnly":false}}]}`,false},
 {"old-ro",`{"volumes":[{"name":"d","persistentVolumeClaim":{"claimName":"compute-state","readOnly":true}}]}`,true},
 {"mount-ro-only-refused",`{"volumes":[{"name":"d","persistentVolumeClaim":{"claimName":"compute-state"}}],"containers":[{"volumeMounts":[{"name":"d","mountPath":"/data","readOnly":true}]}]}`,false},
 {"new-claim",`{"volumes":[{"name":"d","persistentVolumeClaim":{"claimName":"compute-state-checkpoint-20261118"}}]}`,true},
 {"backup-claim",`{"volumes":[{"name":"d","persistentVolumeClaim":{"claimName":"compute-state-backup"}}]}`,true},
 {"no-volumes",`{}`,true},
 {"config-only",`{"volumes":[{"name":"c","configMap":{"name":"unrelated"}}]}`,true},
 {"mixed-ro-rw-refused",`{"volumes":[{"name":"a","persistentVolumeClaim":{"claimName":"compute-state","readOnly":true}},{"name":"b","persistentVolumeClaim":{"claimName":"compute-state"}}]}`,false},
 }
 for _,c:=range cases{t.Run(c.name,func(t *testing.T){var ps map[string]interface{};json.Unmarshal([]byte(c.body),&ps);v,_,e:=pr.Eval(map[string]interface{}{"object":map[string]interface{}{"spec":ps}});if e!=nil||v.Value()!=c.allow{t.Fatalf("%v %v",v,e)}})}
 for _,label:=range []string{"old-rw","old-ro","target-rw","unrelated-rw"}{raw,e:=os.ReadFile("../admission/proposals/"+label+".json");if e!=nil{t.Fatal(e)};var obj map[string]interface{};if e=json.Unmarshal(raw,&obj);e!=nil{t.Fatal(e)};v,_,e:=pr.Eval(map[string]interface{}{"object":obj});if e!=nil||v.Value()!=(label!="old-rw"){t.Fatalf("proposal %s: %v %v",label,v,e)}}
 for _,ns:=range []string{"cps-compute","default","cps-compute-other",""}{v,_,e:=cp.Eval(map[string]interface{}{"request":map[string]interface{}{"namespace":ns}});if e!=nil||v.Value()!=(ns=="cps-compute"){t.Fatalf("namespace %s %v %v",ns,v,e)}}
}
