package adaptation_test

import (
	"context"
	"fmt"
	"net"
	"time"

	nri "github.com/containerd/nri/pkg/adaptation"
	"github.com/containerd/nri/pkg/api"
	"github.com/containerd/nri/pkg/stub"
	validator "github.com/containerd/nri/plugins/default-validator"
	. "github.com/onsi/ginkgo/v2"
	. "github.com/onsi/gomega"
)

// These use the existing Suite's real Unix socket, stub and ttrpc transport.
// A transport timeout must not count as successful required-plugin presence.
var _ = Describe("CPS required plugin transport regression", func() {
	DescribeTable("preserves first-request admission semantics",
		func(mode string, required bool, wantError string) {
			nri.SetPluginRequestTimeout(100 * time.Millisecond)
			s := &Suite{}
			release := make(chan struct{})
			entered := make(chan struct{}, 1)
			var transport net.Conn
			plugin := &mockPlugin{idx: "10", name: "required", mask: api.MustParseEventMask("CreateContainer")}
			plugin.options = []stub.Option{stub.WithDialer(func(path string) (net.Conn, error) {
				conn, err := net.Dial("unix", path)
				transport = conn
				return conn, err
			})}
			plugin.createContainer = func(_ *mockPlugin, _ *api.PodSandbox, _ *api.Container) (*api.ContainerAdjustment, []*api.ContainerUpdate, error) {
				entered <- struct{}{}
				switch mode {
				case "timeout":
					<-release
				case "disconnect":
					return nil, nil, transport.Close()
				case "explicit-error":
					return nil, nil, fmt.Errorf("deliberate plugin refusal")
				case "adjustment", "conflict":
					adjustment := &api.ContainerAdjustment{}
					adjustment.AddAnnotation("cps-test-injected", "required")
					return adjustment, nil, nil
				}
				return nil, nil, nil
			}
			if mode == "unsubscribed" {
				plugin.mask = api.MustParseEventMask("RunPodSandbox")
			}
			plugins := []*mockPlugin{plugin}
			if mode == "conflict" {
				other := &mockPlugin{idx: "05", name: "other", mask: api.MustParseEventMask("CreateContainer")}
				other.createContainer = func(_ *mockPlugin, _ *api.PodSandbox, _ *api.Container) (*api.ContainerAdjustment, []*api.ContainerUpdate, error) {
					adjustment := &api.ContainerAdjustment{}
					adjustment.AddAnnotation("cps-test-injected", "other")
					return adjustment, nil, nil
				}
				plugins = append([]*mockPlugin{other}, plugins...)
			}
			s.Prepare(&mockRuntime{options: []nri.Option{
				nri.WithDefaultValidator(&validator.DefaultValidatorConfig{Enable: true}),
			}}, plugins...)
			DeferCleanup(func() {
				close(release)
				s.Cleanup()
				nri.SetPluginRequestTimeout(nri.DefaultPluginRequestTimeout)
			})
			s.Startup()
			pod := &api.PodSandbox{Id: "pod", Uid: "uid", Name: "pod", Namespace: "default"}
			if required {
				pod.Annotations = map[string]string{
					"required-plugins.noderesource.dev/container.main": `["required"]`,
				}
			}
			Expect(s.runtime.RunPodSandbox(context.Background(), &api.RunPodSandboxRequest{Pod: pod})).To(Succeed())
			if mode == "disconnected-before" {
				Expect(transport.Close()).To(Succeed())
				Expect(plugin.Wait(PluginDisconnected, time.After(startupTimeout))).To(Succeed())
			}
			request := &api.CreateContainerRequest{Pod: pod, Container: &api.Container{
				Id: "container", Name: "main", PodSandboxId: "pod", State: api.ContainerState_CONTAINER_CREATED,
			}}
			// This is the FIRST request, not a retry after removal of the plugin.
			response, err := s.runtime.CreateContainer(context.Background(), request)
			if wantError != "" {
				Expect(err).To(HaveOccurred(), "first CreateContainer unexpectedly succeeded: %#v", response)
				Expect(err.Error()).To(ContainSubstring(wantError))
				Expect(response).To(BeNil())
			} else {
				Expect(err).NotTo(HaveOccurred())
				Expect(response).NotTo(BeNil())
			}
			if mode == "timeout" || mode == "disconnect" {
				Expect(entered).To(HaveLen(1), "the request must reach the real plugin before transport failure")
				Expect(plugin.Wait(PluginDisconnected, time.After(startupTimeout))).To(Succeed())
			}
			if mode == "unsubscribed" {
				Expect(entered).To(BeEmpty())
			}
			if mode == "adjustment" {
				Expect(response.Adjust.Annotations).To(HaveKeyWithValue("cps-test-injected", "required"))
			}
			if mode == "explicit-error" || mode == "conflict" {
				Expect(err.Error()).NotTo(ContainSubstring("required plugin"))
			}
		},
		Entry("rejects first required timeout", "timeout", true, `required plugin "required" not present`),
		Entry("rejects required transport disconnect", "disconnect", true, `required plugin "required" not present`),
		Entry("rejects already disconnected required plugin", "disconnected-before", true, `required plugin "required" not present`),
		Entry("keeps unannotated CPU creation after timeout", "timeout", false, ""),
		Entry("keeps unannotated CPU creation after disconnect", "disconnect", false, ""),
		Entry("preserves successful nil adjustment", "nil", true, ""),
		Entry("preserves registered unsubscribed plugin", "unsubscribed", true, ""),
		Entry("preserves successful injected adjustment", "adjustment", true, ""),
		Entry("preserves explicit plugin error", "explicit-error", true, "deliberate plugin refusal"),
		Entry("preserves adjustment conflict", "conflict", true, "both tried to set"),
	)
})
