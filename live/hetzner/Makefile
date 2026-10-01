TERRAFORM ?= terraform
TF_ARGS   ?=

REQUIRED_ENV  := AWS_PROFILE HCLOUD_TOKEN

APPLY_ORDER   := bootstrap network openvpn private_hosts
DESTROY_ORDER := private_hosts openvpn network

.NOTPARALLEL:
.PHONY: init plan apply destroy

init: $(addprefix init-,$(APPLY_ORDER))
plan: $(addprefix plan-,$(APPLY_ORDER))
apply: $(addprefix apply-,$(APPLY_ORDER))
destroy: $(addprefix destroy-,$(DESTROY_ORDER))

init-%:
	$(call require_env)
	$(call require_stack,$*,$(APPLY_ORDER))
	$(TERRAFORM) -chdir=$* init -input=false $(TF_ARGS)

plan-%:
	$(call require_env)
	$(call require_stack,$*,$(APPLY_ORDER))
	$(TERRAFORM) -chdir=$* plan $(TF_ARGS)

apply-%:
	$(call require_env)
	$(call require_stack,$*,$(APPLY_ORDER))
	$(TERRAFORM) -chdir=$* apply $(TF_ARGS)

# bootstrap holds the state bucket of every other stack, so it is never destroyed from here.
destroy-%:
	$(call require_env)
	$(call require_stack,$*,$(DESTROY_ORDER))
	$(TERRAFORM) -chdir=$* destroy $(TF_ARGS)

require_stack = $(if $(filter $(1),$(2)),,$(error Unknown stack '$(1)'. Allowed: $(2)))
require_env   = $(foreach var,$(REQUIRED_ENV),$(if $($(var)),,$(error $(var) is not set)))
