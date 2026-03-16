#!/usr/bin/env python3
"""
get_logs.py — View production logs from the Jemya EC2 instance via SSM.

Usage:
    python3 tools/get_logs.py                         # last 100 lines
    python3 tools/get_logs.py --lines 200             # last N lines
    python3 tools/get_logs.py --follow                # tail -f (streams for 60s)
    python3 tools/get_logs.py --filter "ERROR"        # grep for a pattern
    python3 tools/get_logs.py --filter "403|401"      # multiple patterns (regex)
    python3 tools/get_logs.py --nginx                 # nginx access/error logs
    python3 tools/get_logs.py --env                   # show container env vars
    python3 tools/get_logs.py --profile myprofile     # use a named AWS profile
"""

import argparse
import boto3
import sys
import time
from botocore.exceptions import ClientError, NoCredentialsError

REGION = "eu-west-1"
INSTANCE_TAG = "jemya-instance"
CONTAINER_FILTER = "jemya"


def find_instance(ec2_client: "boto3.client") -> str:
    resp = ec2_client.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [INSTANCE_TAG]},
            {"Name": "instance-state-name", "Values": ["running"]},
        ]
    )
    for reservation in resp["Reservations"]:
        for instance in reservation["Instances"]:
            return instance["InstanceId"]
    sys.exit("❌  No running jemya-instance found.")


def run_ssm(ssm_client, instance_id: str, command: str, timeout: int = 30) -> str:
    resp = ssm_client.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [command]},
    )
    command_id = resp["Command"]["CommandId"]

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        inv = ssm_client.get_command_invocation(
            CommandId=command_id, InstanceId=instance_id
        )
        if inv["Status"] not in ("Pending", "InProgress", "Delayed"):
            stdout = inv.get("StandardOutputContent", "").strip()
            stderr = inv.get("StandardErrorContent", "").strip()
            if inv["Status"] != "Success" and stderr:
                print(f"⚠️  Command exited with status {inv['Status']}", file=sys.stderr)
                print(stderr, file=sys.stderr)
            return stdout
    sys.exit("❌  SSM command timed out.")


def main():
    parser = argparse.ArgumentParser(description="View Jemya production logs via SSM")
    parser.add_argument("--lines", "-n", type=int, default=100, help="Number of log lines (default: 100)")
    parser.add_argument("--follow", "-f", action="store_true", help="Stream logs for 60 seconds (polling)")
    parser.add_argument("--filter", metavar="PATTERN", help="Grep pattern to filter log lines (regex)")
    parser.add_argument("--nginx", action="store_true", help="Show nginx access + error logs instead of app logs")
    parser.add_argument("--env", action="store_true", help="Show environment variables inside the container")
    parser.add_argument("--profile", default="jemya", help="AWS profile name (default: jemya)")
    args = parser.parse_args()

    try:
        session = boto3.Session(profile_name=args.profile, region_name=REGION)
        ec2 = session.client("ec2")
        ssm = session.client("ssm")
    except NoCredentialsError:
        sys.exit("❌  AWS credentials not found. Set up ~/.aws/credentials or use --profile.")

    instance_id = find_instance(ec2)
    print(f"✅  Instance: {instance_id}\n", flush=True)

    # Helper to resolve the active container name
    container_cmd = f"docker ps --filter name={CONTAINER_FILTER} --format '{{{{.Names}}}}' | head -1"

    if args.env:
        cmd = f"docker exec $({container_cmd}) env | sort"
        print("🔧  Container environment variables:\n")
        print(run_ssm(ssm, instance_id, cmd))
        return

    if args.nginx:
        cmd = (
            "echo '=== NGINX ACCESS (last 50) ===' && "
            "tail -50 /var/log/nginx/access.log 2>/dev/null || echo '(no access log)' && "
            "echo '' && echo '=== NGINX ERROR (last 50) ===' && "
            "tail -50 /var/log/nginx/error.log 2>/dev/null || echo '(no error log)'"
        )
        print(run_ssm(ssm, instance_id, cmd, timeout=30))
        return

    if args.follow:
        print(f"📡  Streaming logs (polling every 5s for 60s)… Ctrl-C to stop\n")
        seen_lines = set()
        deadline = time.time() + 60
        while time.time() < deadline:
            cmd = f"docker logs $({container_cmd}) --tail 50 2>&1"
            output = run_ssm(ssm, instance_id, cmd, timeout=30)
            for line in output.splitlines():
                if line not in seen_lines:
                    seen_lines.add(line)
                    print(line, flush=True)
            time.sleep(5)
        return

    # Standard log fetch
    cmd = f"docker logs $({container_cmd}) --tail {args.lines} 2>&1"
    if args.filter:
        cmd += f" | grep -E '{args.filter}'"

    label = f"📋  Last {args.lines} lines"
    if args.filter:
        label += f" filtered by '{args.filter}'"
    print(label + ":\n")

    output = run_ssm(ssm, instance_id, cmd, timeout=30)
    print(output if output else "(no output)")


if __name__ == "__main__":
    main()
