TERRAFORM        ?= terraform
ANSIBLE_PLAYBOOK ?= ansible-playbook
TF_ARGS          ?=

REQUIRED_ENV  := AWS_PROFILE OVPN_HCLOUD_TOKEN

APPLY_ORDER   := network openvpn private_hosts
DESTROY_ORDER := private_hosts openvpn network

# Only the OVPN token may reach the OVPN project. This assignment
# overrides an HCLOUD_TOKEN inherited from the shell.
export HCLOUD_TOKEN := $(OVPN_HCLOUD_TOKEN)

.NOTPARALLEL:
.PHONY: init apply destroy inventory configure

init: $(addprefix init-,$(APPLY_ORDER))
apply: $(addprefix apply-,$(APPLY_ORDER))
destroy: $(addprefix destroy-,$(DESTROY_ORDER))

inventory:
	$(call require_env)
	$(TERRAFORM) -chdir=openvpn output -json ansible_inventory > ansible/inventory/hosts.json.tmp
	mv ansible/inventory/hosts.json.tmp ansible/inventory/hosts.json
	rm -f ansible/.known_hosts

configure: inventory
	cd ansible && $(ANSIBLE_PLAYBOOK) playbooks/openvpn.yml

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

destroy-%:
	$(call require_env)
	$(call require_stack,$*,$(DESTROY_ORDER))
	$(TERRAFORM) -chdir=$* destroy $(TF_ARGS)

require_stack = $(if $(filter $(1),$(2)),,$(error Unknown stack '$(1)'. Allowed: $(2)))
require_env   = $(foreach var,$(REQUIRED_ENV),$(if $($(var)),,$(error $(var) is not set)))
