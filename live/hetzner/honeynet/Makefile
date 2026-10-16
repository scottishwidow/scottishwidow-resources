TERRAFORM        ?= terraform
ANSIBLE_PLAYBOOK ?= ansible-playbook
TF_ARGS          ?=

REQUIRED_ENV  := AWS_PROFILE HONEYNET_HCLOUD_TOKEN

APPLY_ORDER   := network sensor honeypots
DESTROY_ORDER := honeypots sensor network
ALL_STACKS    := bootstrap $(APPLY_ORDER)

export HCLOUD_TOKEN := $(HONEYNET_HCLOUD_TOKEN)

export TF_VAR_honeypot_1_private_ip := 10.20.0.11

export TF_VAR_proxy_port := 3128

export TF_VAR_honeypot_port_redirects := {"21":2121,"22":2222,"23":2223,"80":8080}

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
	$(call require_stack,$*,$(ALL_STACKS))
	$(TERRAFORM) -chdir=$* init -input=false $(TF_ARGS)

plan-%:
	$(call require_env)
	$(call require_stack,$*,$(ALL_STACKS))
	$(TERRAFORM) -chdir=$* plan $(TF_ARGS)

apply-%:
	$(call require_env)
	$(call require_stack,$*,$(ALL_STACKS))
	$(TERRAFORM) -chdir=$* apply $(TF_ARGS)

destroy-%:
	$(call require_env)
	$(call require_stack,$*,$(ALL_STACKS))
	$(TERRAFORM) -chdir=$* destroy $(TF_ARGS)

require_stack = $(if $(filter $(1),$(2)),,$(error Unknown stack '$(1)'. Allowed: $(2)))
require_env   = $(foreach var,$(REQUIRED_ENV),$(if $($(var)),,$(error $(var) is not set)))
