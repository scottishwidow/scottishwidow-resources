TERRAFORM        ?= terraform
ANSIBLE_PLAYBOOK ?= ansible-playbook
TF_ARGS          ?=

REQUIRED_ENV  := AWS_PROFILE HONEYNET_HCLOUD_TOKEN

APPLY_ORDER   := bootstrap network sensor honeypots
DESTROY_ORDER := honeypots sensor network bootstrap

# Only the Honeynet token may reach the Honeynet project. This assignment
# overrides an HCLOUD_TOKEN inherited from the shell.
export HCLOUD_TOKEN := $(HONEYNET_HCLOUD_TOKEN)

# The sensor root forwards the honeypot ports to this IP, and the honeypots
# root gives it to honeypot-1.
export TF_VAR_honeypot_1_private_ip := 10.20.0.11

.NOTPARALLEL:
.PHONY: init apply destroy inventory configure verify

init: $(addprefix init-,$(APPLY_ORDER))
apply: $(addprefix apply-,$(APPLY_ORDER))
destroy: $(addprefix destroy-,$(DESTROY_ORDER))

inventory:
	$(call require_env)
	$(TERRAFORM) -chdir=sensor output -json ansible_inventory > ansible/inventory/sensor.json.tmp
	$(TERRAFORM) -chdir=honeypots output -json ansible_inventory > ansible/inventory/honeypots.json.tmp
	mv ansible/inventory/sensor.json.tmp ansible/inventory/sensor.json
	mv ansible/inventory/honeypots.json.tmp ansible/inventory/honeypots.json
	rm -f ansible/.known_hosts

configure: inventory
	cd ansible && $(ANSIBLE_PLAYBOOK) playbooks/site.yml

verify:
	cd ansible && $(ANSIBLE_PLAYBOOK) playbooks/verify.yml

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
