package main

import (
	"strconv"
	"strings"
	"testing"
)

func TestVAPSequentialVariablesAndOfficialStrings(t *testing.T) {
	raw := `{"policy":{"spec":{"variables":[{"name":"prefix","expression":"object.name.substring(0,3)"},{"name":"same","expression":"variables.prefix == 'abc'"}],"matchConditions":[{"name":"create","expression":"request.operation == 'CREATE'"}],"validations":[{"expression":"variables.same && has(object.metadata) && object.metadata.generation == 1"},{"expression":"object.items.map(x,x + '-ok') == ['a-ok','b-ok'] && object.name.startsWith('abc') && object.name.matches('^abc[0-9]+$')"}]}},"inputs":{"object":{"name":"abc123","metadata":{"generation":1},"items":["a","b"]},"request":{"operation":"CREATE"},"oldObject":null,"params":null}}`
	out, err := evaluate(strings.NewReader(raw))
	if err != nil {
		t.Fatal(err)
	}
	if !out.Compiled || !out.Evaluated || out.Decision != "pass" || out.AllExpressionsTrue == nil || !*out.AllExpressionsTrue {
		t.Fatalf("%+v", out)
	}
}
func TestNotMatchedIsNotDeny(t *testing.T) {
	out, err := evaluate(strings.NewReader(`{"policy":{"spec":{"matchConditions":[{"name":"skip","expression":"false"}],"validations":[{"expression":"false"}]}},"inputs":{"request":{},"object":{}}}`))
	if err != nil {
		t.Fatal(err)
	}
	if out.Decision != "not-matched" || out.AllExpressionsTrue != nil || out.Results[0].Evaluated {
		t.Fatalf("%+v", out)
	}
}
func TestDenyCompileErrorAndNonBoolean(t *testing.T) {
	for _, c := range []struct{ expr, decision string }{{"false", "deny"}, {"'text'", "error"}, {"not syntax (", "error"}, {"object.absent", "error"}} {
		raw := `{"policy":{"spec":{"validations":[{"expression":` + strconv.Quote(c.expr) + `}]}},"inputs":{"request":{},"object":{}}}`
		out, err := evaluate(strings.NewReader(raw))
		if err != nil {
			t.Fatal(err)
		}
		if out.Decision != c.decision {
			t.Fatalf("%s %+v", c.expr, out)
		}
	}
}
func TestVariableFailureAndConditionErrorStayErrors(t *testing.T) {
	cases := []string{
		`{"policy":{"spec":{"variables":[{"name":"first","expression":"variables.later"}],"validations":[{"expression":"true"}]}},"inputs":{"request":{},"object":{}}}`,
		`{"policy":{"spec":{"matchConditions":[{"name":"bad","expression":"'text'"}],"validations":[{"expression":"true"}]}},"inputs":{"request":{},"object":{}}}`,
	}
	for _, raw := range cases {
		out, err := evaluate(strings.NewReader(raw))
		if err != nil {
			t.Fatal(err)
		}
		if out.Decision != "error" || out.AllExpressionsTrue != nil {
			t.Fatalf("%+v", out)
		}
	}
}
func TestBoundsAndMalformedInput(t *testing.T) {
	for _, raw := range []string{`{`, `{"policy":{"spec":{"validations":[]}},"inputs":{}}`, strings.Repeat(" ", 4*1024*1024+1), `{"policy":{},"inputs":{}} {}`} {
		if _, err := evaluate(strings.NewReader(raw)); err == nil {
			t.Fatal("invalid input accepted")
		}
	}
}
func TestFalseConditionSkipsEvenWithOtherEvaluationError(t *testing.T) {
	out, err := evaluate(strings.NewReader(`{"policy":{"spec":{"matchConditions":[{"name":"bad","expression":"object.absent"},{"name":"skip","expression":"false"}],"validations":[{"expression":"false"}]}},"inputs":{"request":{},"object":{}}}`))
	if err != nil {
		t.Fatal(err)
	}
	if out.Decision != "not-matched" || out.Matched == nil || *out.Matched || out.AllExpressionsTrue != nil {
		t.Fatalf("%+v", out)
	}
}
