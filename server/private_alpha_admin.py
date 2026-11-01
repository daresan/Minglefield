"""Local operator CLI for private alpha test identities. Never a web endpoint."""
import argparse
import getpass
from private_alpha_auth import AlphaAuthStore

def main():
    parser = argparse.ArgumentParser(description="LOCAL operator only; never publish credentials")
    parser.add_argument("--db", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    invite = sub.add_parser("invite")
    invite.add_argument("user_id")
    invite.add_argument("--ttl", type=int, default=3600)
    redeem = sub.add_parser("redeem")
    redeem.add_argument("--agent", required=True)
    revoke = sub.add_parser("disable-user")
    revoke.add_argument("user_id")
    reset = sub.add_parser("reset-password", help="LOCAL OPERATOR ONLY: reset password")
    reset.add_argument("user_id")
    args = parser.parse_args()
    store = AlphaAuthStore(args.db)
    if args.command == "invite":
        print("Invitation secret (share only over a private channel):",
              store.invite(args.user_id, ttl=args.ttl))
    elif args.command == "redeem":
        token = getpass.getpass("Invitation secret: ")
        session = store.redeem(token, agent_id=args.agent)
        if session is None:
            raise SystemExit("Invitation invalid, used, expired or agent occupied")
        print("Session bearer (local test only; never share):", session)
    elif args.command == "reset-password":
        password = getpass.getpass("New password (min 12 chars): ")
        confirmation = getpass.getpass("Repeat new password: ")
        if password != confirmation:
            raise SystemExit("Passwords differ")
        if not store.operator_reset_password(args.user_id, password):
            raise SystemExit("Unknown/disabled account or invalid password")
        print("Password reset; old sessions revoked. Agents and jobs preserved.")
    else:
        print("Disabled" if store.disable_user(args.user_id) else "Unknown user")

if __name__ == "__main__":
    main()
