variable "name" {
  description = "Name prefix for the IAM role and for the Name tag applied to snapshots."
  type        = string
}

variable "description" {
  description = "Description of the DLM lifecycle policy. DLM restricts the charset to [0-9A-Za-z _-]; colons and slashes are rejected."
  type        = string

  validation {
    condition     = can(regex("^[0-9A-Za-z _-]+$", var.description))
    error_message = "DLM policy descriptions may only contain [0-9A-Za-z _-]."
  }
}

variable "target_tags" {
  description = "Tags an instance must carry for DLM to snapshot it. Anything else given these tags will also be snapshotted; conversely, retagging a target silently stops its backups."
  type        = map(string)
}

variable "schedules" {
  description = "Snapshot schedules. Each has a name, a cron expression (UTC), and the number of snapshots to retain."
  type = list(object({
    name            = string
    cron_expression = string
    retain_count    = number
  }))

  validation {
    condition     = length(var.schedules) >= 1 && length(var.schedules) <= 4
    error_message = "DLM allows between 1 and 4 schedules per policy."
  }

  validation {
    condition     = alltrue([for s in var.schedules : s.retain_count >= 1 && s.retain_count <= 1000])
    error_message = "DLM retain_rule.count must be between 1 and 1000."
  }
}

variable "exclude_boot_volume" {
  description = "Whether to leave the boot volume out of the snapshot. Leave false where the boot volume is also the data volume — excluding it would back up nothing."
  type        = bool
  default     = false
}

variable "no_reboot" {
  description = "Whether DLM may reboot the instance to take a snapshot. Defaults to true (never reboot production for a backup), which makes snapshots crash-consistent rather than quiesced."
  type        = bool
  default     = true
}

variable "snapshot_tags" {
  description = "Tags added to each snapshot, alongside a Name of <name>-backup and the schedule name."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tags applied to the IAM role and the lifecycle policy itself."
  type        = map(string)
  default     = {}
}
