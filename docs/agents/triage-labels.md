# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Beyond the five roles

`ready-for-remediation` is a sixth label, outside the table above and belonging
to one capability rather than to the tracker as a whole. Applied to an issue the
IaC security triage pipeline filed, it asks that pipeline for a patch; it means
nothing on any other issue. See
[`security/iac_security/CONTEXT.md`](../../security/iac_security/CONTEXT.md).

No pipeline in this repository applies `ready-for-agent` or
`ready-for-remediation` itself. Both authorise unattended work, and an agent
able to apply one would be authorising its own.
