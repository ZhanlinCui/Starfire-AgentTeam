package provisioner

import "testing"

func TestRuntimeImagesIncludesNemoClaw(t *testing.T) {
	got, ok := RuntimeImages["nemoclaw"]
	if !ok {
		t.Fatalf("missing runtime image for nemoclaw")
	}
	if got != "workspace-template:nemoclaw" {
		t.Fatalf("unexpected image for nemoclaw: %s", got)
	}
}
