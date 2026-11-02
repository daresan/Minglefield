"""SEC-01 trusted LOCAL host administrator provisioning. No HTTP route."""
import argparse
from private_alpha_auth import AlphaAuthStore, ident
from sec01_integrated_alpha_admission import IntegratedAlphaAdmission
from sec01_host_commit_policy_sim import HostCommitPolicy

def main():
    p=argparse.ArgumentParser(description="LOCAL ONLY: host admin fixture provisioning")
    p.add_argument("--auth-db",required=True)
    p.add_argument("--host",required=True)
    p.add_argument("--admin",required=True)
    args=p.parse_args()
    if not ident(args.host) or not ident(args.admin):
        p.error("invalid identity")
    store=AlphaAuthStore(args.auth_db)
    policy=HostCommitPolicy(IntegratedAlphaAdmission(store))
    with store._tx() as db:
        if db.execute("SELECT 1 FROM alpha_users WHERE user_id=? AND disabled=0",
                      (args.admin,)).fetchone() is None:
            p.error("administrator must be an existing active Alpha user")
    policy.add_admin_fixture(args.host,args.admin)
    print("LOCAL host admin assigned:",args.host,args.admin)

if __name__=="__main__":
    main()
