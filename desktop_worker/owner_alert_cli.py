"""Check or send a single no-cost Ash phone push test.

Run on the same computer and with the same private environment variables as
the paired Ash desktop worker. This never approves a tool or places a call.
"""
from __future__ import annotations
import argparse
import secrets
from free_owner_alerts import FreeOwnerAlerts


def main(argv=None, notifier=None) -> int:
    parser = argparse.ArgumentParser(description="Check Ash's free phone notifications.")
    parser.add_argument("action", choices=("check", "test"),
                        help="check configuration, or send a harmless one-time test to your subscribed phone")
    args = parser.parse_args(argv)
    owner = notifier or FreeOwnerAlerts()
    if not owner.configured():
        print("Free phone push is not configured. See BUSINESS_PARTNER.md to set up your private topic.")
        return 2
    if args.action == "check":
        print("Local notification configuration is valid. Phone subscription and real delivery are not yet tested.")
        return 0
    result = owner.alert(job_id="test-" + secrets.token_hex(8), category="test")
    if result["sent"]:
        print("Test notification accepted by the push service. Check your phone to verify actual delivery.")
        return 0
    print("Could not deliver a test notification. Reason: " + str(result["reason"]))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
