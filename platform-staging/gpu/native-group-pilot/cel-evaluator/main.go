// Offline dynamic CEL comparison aid, not Kubernetes admission equivalence.
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"strconv"
	"strings"

	"github.com/google/cel-go/cel"
	"github.com/google/cel-go/common/types"
	"github.com/google/cel-go/ext"
)

type expression struct {
	Name       string `json:"name"`
	Expression string `json:"expression"`
}
type input struct {
	Policy struct {
		Spec struct {
			Variables       []expression `json:"variables"`
			MatchConditions []expression `json:"matchConditions"`
			Validations     []expression `json:"validations"`
		} `json:"spec"`
	} `json:"policy"`
	Inputs map[string]interface{} `json:"inputs"`
}
type result struct {
	Name       string `json:"name,omitempty"`
	Expression string `json:"expression"`
	Compiled   bool   `json:"compiled"`
	Evaluated  bool   `json:"evaluated"`
	Value      *bool  `json:"value"`
	Error      string `json:"error,omitempty"`
}
type output struct {
	Compiled           bool     `json:"compiled"`
	Evaluated          bool     `json:"evaluated"`
	AllExpressionsTrue *bool    `json:"allExpressionsTrue"`
	Matched            *bool    `json:"matched"`
	Decision           string   `json:"decision"`
	Variables          []result `json:"variables"`
	MatchConditions    []result `json:"matchConditions"`
	Results            []result `json:"results"`
}

func numbers(v interface{}) (interface{}, error) {
	switch x := v.(type) {
	case json.Number:
		if !strings.ContainsAny(string(x), ".eE") {
			return strconv.ParseInt(string(x), 10, 64)
		}
		return strconv.ParseFloat(string(x), 64)
	case map[string]interface{}:
		for k, child := range x {
			n, err := numbers(child)
			if err != nil {
				return nil, err
			}
			x[k] = n
		}
		return x, nil
	case []interface{}:
		for k, child := range x {
			n, err := numbers(child)
			if err != nil {
				return nil, err
			}
			x[k] = n
		}
		return x, nil
	default:
		return v, nil
	}
}
func evaluate(reader io.Reader) (output, error) {
	out := output{Decision: "error", Variables: []result{}, MatchConditions: []result{}, Results: []result{}}
	raw, err := io.ReadAll(io.LimitReader(reader, 4*1024*1024+1))
	if err != nil {
		return out, err
	}
	if len(raw) > 4*1024*1024 {
		return out, fmt.Errorf("input exceeds 4MiB")
	}
	var data input
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	// VAP metadata and validation message fields are deliberately irrelevant.
	if err = decoder.Decode(&data); err != nil {
		return out, err
	}
	if err = decoder.Decode(new(interface{})); err != io.EOF {
		return out, fmt.Errorf("exactly one JSON input required")
	}
	spec := data.Policy.Spec
	if len(spec.Variables) > 64 || len(spec.MatchConditions) > 64 || len(spec.Validations) < 1 || len(spec.Validations) > 256 || data.Inputs == nil {
		return out, fmt.Errorf("bounded variables/conditions and 1..256 validations required")
	}
	for key := range data.Inputs {
		if key != "object" && key != "oldObject" && key != "request" && key != "params" {
			return out, fmt.Errorf("unknown input binding")
		}
	}
	bindings := map[string]interface{}{}
	for _, key := range []string{"object", "oldObject", "request", "params"} {
		v, err := numbers(data.Inputs[key])
		if err != nil {
			return out, err
		}
		bindings[key] = v
	}
	vars := map[string]interface{}{}
	bindings["variables"] = vars
	env, err := cel.NewEnv(cel.Variable("object", cel.DynType), cel.Variable("oldObject", cel.DynType), cel.Variable("request", cel.DynType), cel.Variable("params", cel.DynType), cel.Variable("variables", cel.DynType), ext.Strings())
	if err != nil {
		return out, err
	}
	sets := [][]expression{spec.Variables, spec.MatchConditions, spec.Validations}
	destinations := []*[]result{&out.Variables, &out.MatchConditions, &out.Results}
	programs := make([][]cel.Program, 3)
	out.Compiled = true
	for group, entries := range sets {
		programs[group] = make([]cel.Program, len(entries))
		seen := map[string]bool{}
		for i, item := range entries {
			row := result{Name: item.Name, Expression: item.Expression}
			if len(item.Expression) == 0 || len(item.Expression) > 32768 {
				return out, fmt.Errorf("expression size exceeds 1..32768 bytes")
			}
			if group < 2 {
				if item.Name == "" || seen[item.Name] {
					return out, fmt.Errorf("distinct variable/condition names required")
				}
				seen[item.Name] = true
			}
			ast, issues := env.Compile(item.Expression)
			if issues != nil && issues.Err() != nil {
				row.Error = issues.Err().Error()
				out.Compiled = false
			} else {
				program, e := env.Program(ast, cel.CostLimit(1000000))
				if e != nil {
					row.Error = e.Error()
					out.Compiled = false
				} else {
					programs[group][i] = program
					row.Compiled = true
				}
			}
			*destinations[group] = append(*destinations[group], row)
		}
	}
	if !out.Compiled {
		return out, nil
	}
	for i, p := range programs[0] {
		value, _, e := p.Eval(bindings)
		if e != nil {
			out.Variables[i].Error = e.Error()
			return out, nil
		}
		vars[spec.Variables[i].Name] = value
		out.Variables[i].Evaluated = true
	}
	matched := true
	conditionError := false
	for i, p := range programs[1] {
		value, _, e := p.Eval(bindings)
		if e != nil {
			out.MatchConditions[i].Error = e.Error()
			conditionError = true
			continue
		}
		b, ok := value.(types.Bool)
		if !ok {
			out.MatchConditions[i].Error = "expression must evaluate to strict bool"
			conditionError = true
			continue
		}
		v := bool(b)
		out.MatchConditions[i].Value = &v
		out.MatchConditions[i].Evaluated = true
		if !v {
			matched = false
		}
	}
	// Kubernetes matching semantics: any false condition skips the policy, even if another errors.
	if !matched {
		out.Matched = &matched
		out.Evaluated = true
		out.Decision = "not-matched"
		return out, nil
	}
	if conditionError {
		return out, nil
	}
	out.Matched = &matched
	all := true
	complete := true
	for i, p := range programs[2] {
		value, _, e := p.Eval(bindings)
		if e != nil {
			out.Results[i].Error = e.Error()
			complete = false
			continue
		}
		b, ok := value.(types.Bool)
		if !ok {
			out.Results[i].Error = "expression must evaluate to strict bool"
			complete = false
			continue
		}
		v := bool(b)
		out.Results[i].Value = &v
		out.Results[i].Evaluated = true
		if !v {
			all = false
		}
	}
	out.Evaluated = complete
	if complete {
		out.AllExpressionsTrue = &all
		if all {
			out.Decision = "pass"
		} else {
			out.Decision = "deny"
		}
	}
	return out, nil
}
func main() {
	out, err := evaluate(os.Stdin)
	if err != nil {
		json.NewEncoder(os.Stdout).Encode(map[string]string{"error": err.Error()})
		os.Exit(2)
	}
	if err = json.NewEncoder(os.Stdout).Encode(out); err != nil {
		os.Exit(2)
	}
}
