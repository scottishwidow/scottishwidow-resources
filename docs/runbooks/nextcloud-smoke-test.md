# Runbook: Nextcloud AIO smoke test

Validate that the Nextcloud AIO deployment in `live/management` is functioning
end-to-end and that no container is faulty. Run this after a `terraform apply`, an
Ansible run, an instance replacement, or any time you want to confirm the stack is
healthy.

Everything here is **read-only**. It touches the control plane over SSM (no SSH —
see [ADR-0001](../adr/0001-ansible-over-ssm.md)) and the data plane over public
HTTPS. Nothing in this runbook mutates the instance.

## Prerequisites

- AWS credentials for account `975049889162`, region `eu-central-1`
  (`aws sts get-caller-identity` should succeed).
- The instance is tagged `Name=nextcloud` and managed by SSM.
- `dig`, `curl`, and `openssl` on the control node (the local workstation).

```sh
cd live/management
REGION=eu-central-1
DOMAIN=$(terraform output -raw next_cloud_domain)        # nextcloud.scottishwidow.click
EIP=$(terraform output -raw next_cloud_public_ip)        # 52.59.35.139
```

## Gotchas (learned the hard way)

- **The SSM run-command document is `AWS-RunShellScript`, _not_
  `AWS-RunShellCommand`.** The wrong name fails with an opaque `InvalidDocument`
  error. Confirm with:
  `aws ssm list-documents --region "$REGION" --filters Key=Owner,Values=Amazon --query "DocumentIdentifiers[?contains(Name,'Shell')].Name"`
- **Pass `--parameters` as a JSON file, not an inline string.** Docker
  `--format` templates use `{{...}}`, tabs, and nested quotes that the shell
  mangles inside `commands=[...]`. A `file://` JSON payload sidesteps all of it.
- **`nextcloud-aio-domaincheck` exiting `143` is expected, not a fault.** AIO
  spins it up as an ephemeral domain-reachability probe and stops it (SIGTERM →
  128+15 = 143) once the check passes. Verify it was clean (`OOMKilled=false`,
  empty `Error`) rather than assuming a crash.

## Step 1 — Instance is running

```sh
aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:Name,Values=nextcloud" \
            "Name=instance-state-name,Values=running" \
  --query 'Reservations[].Instances[].{ID:InstanceId,State:State.Name,Type:InstanceType,IP:PublicIpAddress}' \
  --output table
```

Expect: one instance, `State=running`, `Type=t4g.small`, `IP` matching `$EIP`.
Capture the instance ID for the SSM steps:

```sh
IID=$(aws ec2 describe-instances --region "$REGION" \
  --filters "Name=tag:Name,Values=nextcloud" "Name=instance-state-name,Values=running" \
  --query 'Reservations[0].Instances[0].InstanceId' --output text)
```

## Step 2 — SSM agent is online

```sh
aws ssm describe-instance-information --region "$REGION" \
  --filters "Key=InstanceIds,Values=$IID" \
  --query 'InstanceInformationList[].{Ping:PingStatus,Agent:AgentVersion,Platform:PlatformName}' \
  --output table
```

Expect: `Ping=Online`, `Platform=Ubuntu`. If this is offline, nothing downstream
will work — the control plane is SSM-only.

## Step 3 — Container stack is healthy

```sh
cat > /tmp/ssm-ps.json <<'EOF'
{
  "commands": [
    "echo ===DOCKER_PS===",
    "docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'",
    "echo ===UNHEALTHY===",
    "docker ps --filter health=unhealthy --format '{{.Names}}' || true",
    "echo ===DOCKER_INFO===",
    "docker info --format 'server={{.ServerVersion}} containers={{.Containers}} running={{.ContainersRunning}}'"
  ]
}
EOF

CMD_ID=$(aws ssm send-command --region "$REGION" --instance-ids "$IID" \
  --document-name "AWS-RunShellScript" --comment "nextcloud-smoke" \
  --parameters file:///tmp/ssm-ps.json --query 'Command.CommandId' --output text)

sleep 10
aws ssm get-command-invocation --region "$REGION" --command-id "$CMD_ID" \
  --instance-id "$IID" --query 'StandardOutputContent' --output text
```

Expect **7 running, all `(healthy)`**:

| Container | Role | Notable ports |
| --- | --- | --- |
| `nextcloud-aio-mastercontainer` | manages the inner stack, AIO admin UI | `127.0.0.1:8080` (off the internet) |
| `nextcloud-aio-apache` | public web front | `0.0.0.0:443` |
| `nextcloud-aio-nextcloud` | Nextcloud / PHP-FPM | `9000/tcp` |
| `nextcloud-aio-database` | PostgreSQL | `5432/tcp` |
| `nextcloud-aio-redis` | cache | `6379/tcp` |
| `nextcloud-aio-notify-push` | push notifications | — |
| `nextcloud-aio-collabora` | online office | `9980/tcp` |

- `===UNHEALTHY===` must be **empty**.
- `nextcloud-aio-domaincheck` shows `Exited (143)` — **expected** (see Gotchas).
- `docker info` reports `running=7` (the 8th container is the exited domaincheck).

If a container _other_ than domaincheck is exited or unhealthy, that is the fault
to investigate — pull its logs with
`docker logs <name> --tail 100` via the same SSM mechanism.

### Confirm the exited container is benign

```sh
cat > /tmp/ssm-dc.json <<'EOF'
{ "commands": [
  "docker inspect nextcloud-aio-domaincheck --format 'exit={{.State.ExitCode}} oom={{.State.OOMKilled}} err={{.State.Error}}'"
] }
EOF
CMD_ID=$(aws ssm send-command --region "$REGION" --instance-ids "$IID" \
  --document-name "AWS-RunShellScript" --parameters file:///tmp/ssm-dc.json \
  --query 'Command.CommandId' --output text)
sleep 6
aws ssm get-command-invocation --region "$REGION" --command-id "$CMD_ID" \
  --instance-id "$IID" --query 'StandardOutputContent' --output text
```

Expect: `exit=143 oom=false err=` — a clean SIGTERM, no OOM, no error.

## Step 4 — Nextcloud application status

```sh
cat > /tmp/ssm-occ.json <<'EOF'
{ "commands": [
  "echo ===OCC_STATUS===",
  "docker exec -u www-data nextcloud-aio-nextcloud php occ status",
  "echo ===TRUSTED_DOMAINS===",
  "docker exec -u www-data nextcloud-aio-nextcloud php occ config:system:get trusted_domains"
] }
EOF
CMD_ID=$(aws ssm send-command --region "$REGION" --instance-ids "$IID" \
  --document-name "AWS-RunShellScript" --parameters file:///tmp/ssm-occ.json \
  --query 'Command.CommandId' --output text)
sleep 12
aws ssm get-command-invocation --region "$REGION" --command-id "$CMD_ID" \
  --instance-id "$IID" --query 'StandardOutputContent' --output text
```

Expect:
- `installed: true`, `maintenance: false`, `needsDbUpgrade: false`.
- `trusted_domains` includes the public domain (`nextcloud.scottishwidow.click`).

## Step 5 — Public endpoint, DNS, and TLS

```sh
# DNS points at the EIP
dig +short "$DOMAIN"          # expect: the $EIP value

# status.php served over HTTPS
curl -sS -o /dev/null -w 'http_code=%{http_code}\n' "https://$DOMAIN/status.php" --max-time 15
curl -sS "https://$DOMAIN/status.php" --max-time 15; echo

# Valid Let's Encrypt certificate
echo | openssl s_client -connect "$DOMAIN:443" -servername "$DOMAIN" 2>/dev/null \
  | openssl x509 -noout -issuer -subject -dates
```

Expect:
- `dig` returns `$EIP`.
- `status.php` → `http_code=200` and JSON with `"installed":true,"maintenance":false`.
- Certificate `issuer` is **Let's Encrypt** with valid `notBefore`/`notAfter`
  dates (HTTP-01 validation succeeded over the public 80/443 slice). AIO renews
  it automatically.

## Pass criteria

The deployment is healthy when **all** hold:

- [ ] Instance `running`, EIP matches `terraform output`.
- [ ] SSM `Ping=Online`.
- [ ] 7 AIO containers running and `(healthy)`; `unhealthy` list empty.
- [ ] Only `nextcloud-aio-domaincheck` is exited, with `exit=143 oom=false`.
- [ ] `occ status`: installed, not in maintenance, no pending DB upgrade.
- [ ] Public domain resolves to the EIP and serves `status.php` over valid TLS.

## Notes

- The role pins `nextcloud/all-in-one:latest` (AIO's self-updating stable
  channel); the mastercontainer manages inner-image versions itself. Re-running
  Ansible does **not** pin a frozen version — by design.
- The AIO admin UI (`8080`) is bound to `127.0.0.1` and never exposed publicly.
  Reach it via an SSM port-forward only.
