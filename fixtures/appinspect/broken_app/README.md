# AppInspect fixture — broken_app

A minimal Splunk app seeded with **three deliberate AppInspect failures** that
the local `splunk-appinspect` CLI marks as failures in `--mode test`. The
AppInspect loop must detect each, patch it deterministically, re-run AppInspect,
and reach zero failures.

## Run AppInspect against it

```bash
pip install splunk-appinspect
splunk-appinspect inspect broken_app --mode test --data-format json --output-file result.json
```

The JSON report is the loop's input. Parse `result.json` for `failure`-status
checks, patch, and re-run until clean.

## The three seeded failures

### 1. Forbidden local configuration
- **File:** `local/app.conf`
- **Check:** `check_that_local_does_not_exist`
- **Why it's here:** packaged Splunk apps should ship defaults in `default/`;
  local config is instance-specific and should not be part of a distributable
  app package.
- **Expected fix:** remove `local/` from the package.

### 2. Forbidden default user seed
- **File:** `default/user-seed.conf`
- **Check:** `check_user_seed_conf_deny_list`
- **Why it's here:** default login/password seeding is prohibited for Splunk
  Cloud and is a clear security issue.
- **Expected fix:** remove `default/user-seed.conf` and document that users are
  managed by Splunk auth, not app-shipped credentials.

### 3. Forbidden forwarding configuration
- **File:** `default/outputs.conf`
- **Check:** `check_if_outputs_conf_exists`
- **Why it's here:** apps must not enable forwarding to external indexers by
  default in Splunk Cloud.
- **Expected fix:** remove `default/outputs.conf` from the app package.

## Non-blocking warning

`appserver/static/vendor/dashboard.js` intentionally imports `moment` from
Splunk Web. AppInspect reports this as a warning
(`check_hotlinking_splunk_web_libraries`), not a red failure. It is left in the
fixture as optional dashboard material, but the demo's three red failures are
the deterministic checks above.

## Success criteria for the loop

1. All three `failure` checks detected from the AppInspect JSON.
2. Each patched correctly by a deterministic patch function.
3. AppInspect re-run returns zero failures (within `SELF_HEAL_MAX_ITERS`).
4. Every fix written to the provenance ledger with its rationale.

## Note

This app is intentionally broken. Do not install it in a production Splunk
instance. It exists solely as a healing target for the demo.
