# updatetool

A security updates orchestration tool. Performs rolling updates on all EC2 instances
with the tags `AutoUpdate=true` and `Environment=argument`.

The tool finds all instances with the above-mentioned tag combination, then finds all ELBs
that each instance is registered in. It then deregisters the instance, waiting for bleed-out
to complete, installs all OS security updates, reboots the instance, and re-registers it in
the same ELBs (waiting for the instance to go back `InService`).

The utility creates a `deploytool.state` file during the process, so that instances can be
re-registered in their proper ELBs upon retry, even if an error/exception occurs during the
deregister/update/reboot/reregister process.

# Installation

After cloning updatetool, install project dependencies via `pip`:

```
$ pip install -r requirements.txt
```

# Usage

## Run Updates

```
### Performs updates on the specified environment:
$ python updatetool.py <environment>
```

Where:
- `environment` is the deployment environment, e.g. dev, stg, prd

