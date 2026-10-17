# 17. Every Honeypot service claims one Ubuntu 22.04 Persona

Date: 2026-10-17

## Status

Accepted

## Context

Cowrie and OpenCanary ran with most of their upstream defaults. Scanners such
as Shodan Honeyscore, and attackers who check by hand, look for these defaults:

- Cowrie used the hostname `svr04` and its bundled Debian file contents. Its
  `/etc/passwd` had the user `phil`. Its userdb was `*:x:*`, so every password
  worked.
- OpenCanary used its default banners and the `nasLogin` skin. The
  `basicLogin` skin shows the text "Network Storage v5.13".
- The banners did not agree. Cowrie claimed Debian 12, Apache claimed Ubuntu
  12.04 and MySQL claimed Ubuntu 14.04, all on one host.
- The Sinkhole sent the body `honeynet-sinkhole` for every download. An
  attacker in Cowrie who ran `wget` and `cat` saw the label.

ADR-0015 accepted old version banners, because old versions attract exploit
attempts for old CVEs.

## Decision

- **One Persona.** `honeypot_persona` in `group_vars/all.yml` holds the
  hostname, the kernel and every service banner. The roles and `verify.yml`
  read it. No role holds its own banner.
- **The Persona is Ubuntu 22.04.** OpenSSH 8.9p1, Apache 2.4.52, vsftpd 3.0.5
  and MariaDB 10.6, as the Ubuntu 22.04 packages report them.
- **MariaDB, not MySQL.** OpenCanary refuses a MySQL banner that does not start
  with 3 to 6, so it cannot claim MySQL 8.0. MariaDB sends `5.5.5-` before its
  version, which OpenCanary accepts.
- **Cowrie file contents** come from `contents_path`. Templates replace
  `/etc/passwd`, `/etc/shadow`, `/etc/group`, `/etc/hostname`, `/etc/hosts`,
  `/etc/issue`, `/etc/motd`, `/etc/resolv.conf`, `/usr/lib/os-release`,
  `/proc/version`, `/proc/cpuinfo` and `/proc/meminfo`.
- **Cowrie accepts a list of weak root passwords** and refuses all other
  logins. Only root is on the list, because the pickle has no home directory
  for other users.
- **OpenCanary HTTP uses a custom skin** with a generic sign-in page and Apache
  2.4 error pages.
- **The Sinkhole body is an empty shell script** that holds the marker as a
  comment. Its certificate has the OpenSSL default subject.

## Consequences

- This replaces the old version banners of ADR-0015. Exploit bait stays:
  Ubuntu keeps the upstream version and backports fixes, so scanners that read
  the version still match `Apache/2.4.52` and `OpenSSH_8.9p1` to many CVEs.
- Fewer Cowrie logins succeed. Each session that gets in looks like a real
  compromise and is worth more.
- `make verify` checks every banner against the Persona, checks the Cowrie
  identity for stock values, and checks that an unlisted password fails.
- These tells stay, because removing them is not cheap:
  - The Cowrie directory tree is the bundled Debian `fs.pickle`. It has
    `/etc/debian_version` with Debian sources, `/proc/docker` and no home
    directories. A new tree needs `createfs` from a real Ubuntu host.
  - The `ps` output is the bundled one.
  - OpenCanary answers `/` with a redirect to `/index.html`.
  - OpenCanary MSSQL claims SQL Server 2012 on a Linux host.
  - The Sinkhole answers every DNS name with `1.1.1.1`.
  - The public IPv4 is in the Hetzner ASN.
