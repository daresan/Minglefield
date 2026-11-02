"""SEC-01 host-admin scheduling and FINAL MOCK COMMIT policy.

Local-only SQLite simulator. Host admins own policy, not job requesters.
No actual effects, no network, no GPU polling. A supplied utilization value
is untrusted fixture telemetry; production requires host-owned measurement.
The online proof precheck happens BEFORE the commit transaction, so remote
revocation atomicity is NOT solved by this demonstration.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from private_alpha_auth import ident
from host_runtime_config import validate_runtime, RuntimeConfigurationError, prepare_comfy_effect
from comfy_workflow_inspection import WorkflowError

def _window_matches(config, local):
    """Weekdays denote the day a window starts, including overnight windows."""
    start, end = config["start_minute"], config["end_minute"]
    minute = local.hour * 60 + local.minute
    weekday = local.weekday()
    if start < end:
        return weekday in config["weekdays"] and start <= minute < end
    if start > end:
        return ((weekday in config["weekdays"] and minute >= start)
                or ((weekday - 1) % 7 in config["weekdays"] and minute < end))
    return False

@dataclass(frozen=True)
class HostDecision:
    state: str
    reason: str

class HostCommitPolicy:
    def __init__(self, authority):
        self.authority=authority
        with authority.store._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_comfy_workflows(
                host_id TEXT NOT NULL, effect_id TEXT NOT NULL,
                runtime_id TEXT NOT NULL, workflow TEXT NOT NULL,
                metadata TEXT NOT NULL, PRIMARY KEY(host_id,effect_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_job_parameters(
                job_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                effect_id TEXT NOT NULL, workflow_sha256 TEXT NOT NULL,
                parameters TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS alpha_git_profiles(
                host_id TEXT NOT NULL, profile_id TEXT NOT NULL, owner_id TEXT NOT NULL,
                auth_method TEXT NOT NULL, label TEXT NOT NULL,
                git_executable TEXT NOT NULL, author_name TEXT NOT NULL,
                author_email TEXT NOT NULL, PRIMARY KEY(host_id,profile_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS alpha_game_projects(
                project_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                owner_id TEXT NOT NULL, name TEXT NOT NULL,
                repository_root TEXT NOT NULL, staging_root TEXT NOT NULL,
                output_root TEXT NOT NULL, settings_revision INTEGER NOT NULL DEFAULT 1,
                UNIQUE(host_id,project_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_settings(\n                host_id TEXT PRIMARY KEY, settings TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_runtimes(
                host_id TEXT NOT NULL, runtime_id TEXT NOT NULL,
                config TEXT NOT NULL, PRIMARY KEY(host_id,runtime_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_owners(
                host_id TEXT PRIMARY KEY, owner_id TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_effect_definitions(
                host_id TEXT NOT NULL, effect_id TEXT NOT NULL,
                description TEXT NOT NULL, enabled INTEGER NOT NULL,
                PRIMARY KEY(host_id,effect_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_jobs(
                job_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                effect_id TEXT NOT NULL, requested_by TEXT NOT NULL,
                state TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(host_id,job_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_admins(
                host_id TEXT NOT NULL, admin_id TEXT NOT NULL,
                PRIMARY KEY(host_id,admin_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_rules(
                host_id TEXT NOT NULL, rule_id TEXT NOT NULL,
                priority INTEGER NOT NULL, enabled INTEGER NOT NULL,
                config TEXT NOT NULL, PRIMARY KEY(host_id,rule_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_approvals(
                host_id TEXT NOT NULL, effect_key TEXT NOT NULL,
                approved_by TEXT NOT NULL, PRIMARY KEY(host_id,effect_key))""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_commits(
                effect_key TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                binding TEXT NOT NULL, rule_id TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_active_slots(
                effect_key TEXT PRIMARY KEY, host_id TEXT NOT NULL)""")

    def list_git_profiles(self, host_id, owner_id):
        """List credential-free Git configuration metadata for an owned host."""
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return None
            rows=db.execute("""SELECT profile_id,label,auth_method,git_executable,
                author_name,author_email FROM alpha_git_profiles
                WHERE host_id=? AND owner_id=? ORDER BY label,profile_id""",
                (host_id,owner_id)).fetchall()
        return [dict(zip(("profile_id","label","auth_method","git_executable",
                          "author_name","author_email"),row)) for row in rows]

    def save_git_profile(self, host_id, owner_id, profile):
        """Store only non-secret settings; no tokens, passwords or private keys."""
        fields={"profile_id","label","auth_method","git_executable","author_name","author_email"}
        if type(profile) is not dict or set(profile)!=fields:
            return HostDecision("denied","invalid_git_profile")
        if (not ident(profile["profile_id"]) or
                profile["auth_method"] not in ("local","ssh","credential_manager","github_cli") or
                any(type(profile[k]) is not str or len(profile[k])>256
                    for k in fields) or
                not 1<=len(profile["label"].strip())<=120 or
                not profile["git_executable"].strip()):
            return HostDecision("denied","invalid_git_profile")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return HostDecision("denied","not_host_owner")
            db.execute("""INSERT INTO alpha_git_profiles(
                host_id,profile_id,owner_id,label,auth_method,git_executable,author_name,author_email)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(host_id,profile_id) DO UPDATE SET
                label=excluded.label,auth_method=excluded.auth_method,
                git_executable=excluded.git_executable,author_name=excluded.author_name,
                author_email=excluded.author_email""",
                (host_id,profile["profile_id"],owner_id,profile["label"].strip(),
                 profile["auth_method"],profile["git_executable"].strip(),
                 profile["author_name"],profile["author_email"]))
        return HostDecision("saved","git_profile_saved")

    def list_game_projects(self, host_id, owner_id):
        """Return only projects belonging to an authorized host owner."""
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return None
            rows=db.execute("""SELECT project_id,name,repository_root,staging_root,
                output_root,settings_revision FROM alpha_game_projects
                WHERE host_id=? AND owner_id=? ORDER BY name,project_id""",
                (host_id,owner_id)).fetchall()
            keys=("project_id","name","repository_root","staging_root",
                  "output_root","settings_revision")
            return [dict(zip(keys,row)) for row in rows]

    def create_game_project(self, host_id, owner_id, project_id, name,
                            repository_root, staging_root, output_root):
        """Register project metadata without touching the filesystem or host paths."""
        from pathlib import Path
        import sqlite3
        if (not ident(project_id) or type(name) is not str
                or not 1 <= len(name.strip()) <= 120):
            return HostDecision("denied","invalid_project_identity")
        paths=(repository_root,staging_root,output_root)
        if any(type(path) is not str or not path or len(path)>1024
               or not Path(path).is_absolute() for path in paths):
            return HostDecision("denied","invalid_project_path")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return HostDecision("denied","not_host_owner")
            try:
                db.execute("""INSERT INTO alpha_game_projects(
                    project_id,host_id,owner_id,name,repository_root,staging_root,output_root)
                    VALUES(?,?,?,?,?,?,?)""",
                    (project_id,host_id,owner_id,name.strip(),*paths))
            except sqlite3.IntegrityError:
                return HostDecision("denied","project_id_exists")
        return HostDecision("created","game_project_created")

    def update_game_project(self, host_id, owner_id, project_id, revision,
                            name, repository_root, staging_root, output_root):
        """Optimistic, owner-scoped metadata update; never modifies files."""
        from pathlib import Path
        if (not ident(project_id) or type(revision) is not int or revision < 1
                or type(name) is not str or not 1 <= len(name.strip()) <= 120):
            return HostDecision("denied","invalid_project_update")
        paths=(repository_root,staging_root,output_root)
        if any(type(p) is not str or not p or len(p)>1024
               or not Path(p).is_absolute() for p in paths):
            return HostDecision("denied","invalid_project_path")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return HostDecision("denied","not_host_owner")
            row=db.execute("""SELECT settings_revision FROM alpha_game_projects
                WHERE host_id=? AND owner_id=? AND project_id=?""",
                (host_id,owner_id,project_id)).fetchone()
            if row is None:
                return HostDecision("denied","project_not_found")
            if row[0]!=revision:
                return HostDecision("denied","revision_conflict")
            db.execute("""UPDATE alpha_game_projects SET name=?,repository_root=?,
                staging_root=?,output_root=?,settings_revision=settings_revision+1
                WHERE host_id=? AND owner_id=? AND project_id=? AND settings_revision=?""",
                (name.strip(),*paths,host_id,owner_id,project_id,revision))
        return HostDecision("saved","game_project_updated")

    def inspect_game_project_paths(self, host_id, owner_id, project_id):
        """Read-only local directory inspection; no creation or writes."""
        from pathlib import Path
        if not ident(project_id):
            return None
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return None
            row=db.execute("""SELECT repository_root,staging_root,output_root
                FROM alpha_game_projects WHERE host_id=? AND owner_id=? AND project_id=?""",
                (host_id,owner_id,project_id)).fetchone()
        if row is None:
            return None
        result={}
        for key,raw in zip(("repository_root","staging_root","output_root"),row):
            path=Path(raw)
            try:
                exists=path.exists()
                is_directory=path.is_dir() if exists else False
                result[key]={"path":raw,"state":(
                    "missing" if not exists else "directory" if is_directory else "not_directory")}
            except OSError:
                result[key]={"path":raw,"state":"unavailable"}
        return result

    @staticmethod
    def _prepare_game_ignore(repo, staging, output):
        """Append anchored ignore rules for in-repo asset directories only."""
        import subprocess
        from pathlib import Path
        root=Path(repo).resolve()
        paths=[Path(staging).resolve(),Path(output).resolve()]
        rules=[]
        for path in paths:
            if not path.is_relative_to(root):
                continue
            relative=path.relative_to(root)
            if any(part in (".git", ".minglefield") for part in relative.parts):
                return {"state":"denied","reason":"reserved_asset_directory"}
            rules.append("/"+"/".join(relative.parts)+"/")
        if not rules:
            return {"state":"unchanged","rules_added":[],"tracked_assets":[]}
        ignore=root/".gitignore"
        if ignore.is_symlink() or (ignore.exists() and not ignore.is_file()):
            return {"state":"denied","reason":"gitignore_not_regular_file"}
        try:
            existing=ignore.read_text(encoding="utf-8-sig") if ignore.exists() else ""
        except (OSError,UnicodeError):
            return {"state":"denied","reason":"gitignore_unreadable"}
        present=set(existing.splitlines())
        added=[rule for rule in dict.fromkeys(rules) if rule not in present]
        tracked=[]
        try:
            result=subprocess.run(["git","-C",str(root),"rev-parse","--show-toplevel"],
                                  capture_output=True,text=True,timeout=8,
                                  stdin=subprocess.DEVNULL)
            if result.returncode==0 and Path(result.stdout.strip()).resolve()==root:
                tracked_result=subprocess.run(["git","-C",str(root),"ls-files","--",
                                               *[rule.strip("/") for rule in rules]],
                                               capture_output=True,text=True,timeout=8,
                                               stdin=subprocess.DEVNULL)
                if tracked_result.returncode==0:
                    tracked=tracked_result.stdout.splitlines()
        except (OSError,subprocess.TimeoutExpired,ValueError):
            pass
        if added:
            try:
                with ignore.open("a",encoding="utf-8",newline="\n") as stream:
                    if existing and not existing.endswith(("\n","\r")):
                        stream.write("\n")
                    stream.write("\n".join(added)+"\n")
            except OSError:
                return {"state":"denied","reason":"gitignore_write_failed"}
        return {"state":"updated" if added else "unchanged",
                "rules_added":added,"tracked_assets":tracked}

    def prepare_game_project_directories(self, host_id, owner_id, project_id, revision):
        """Explicitly create only missing staging/output directories for a current project."""
        from pathlib import Path
        if not ident(project_id) or type(revision) is not int or revision < 1:
            return {"state":"denied","reason":"invalid_project_prepare"}
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return {"state":"denied","reason":"not_host_owner"}
            row=db.execute("""SELECT repository_root,staging_root,output_root,settings_revision
                FROM alpha_game_projects WHERE host_id=? AND owner_id=? AND project_id=?""",
                (host_id,owner_id,project_id)).fetchone()
        if row is None:
            return {"state":"denied","reason":"project_not_found"}
        repo,staging,output,current_revision=row
        if revision!=current_revision:
            return {"state":"denied","reason":"revision_conflict"}
        roots=[Path(repo),Path(staging),Path(output)]
        try:
            resolved=[p.resolve(strict=False) for p in roots]
            if (resolved[0] in resolved[1:] or resolved[1]==resolved[2] or
                    any(resolved[i].is_relative_to(resolved[j])
                        for i,j in ((0,1),(0,2)))):
                return {"state":"denied","reason":"unsafe_project_paths"}
            for path in roots:
                if path.exists() and not path.is_dir():
                    return {"state":"denied","reason":"path_not_directory"}
            created=[]
            for path in roots:
                if not path.is_dir():
                    path.mkdir(parents=True,exist_ok=True)
                    created.append(str(path))
            ignore=self._prepare_game_ignore(repo,staging,output)
            if ignore["state"]=="denied":
                return {"state":"denied","reason":ignore["reason"],"created":created}
            return {"state":"prepared","reason":"project_directories_ready",
                    "created":created,"gitignore":ignore}
        except (OSError,ValueError):
            return {"state":"denied","reason":"filesystem_error"}

    def inspect_game_git(self, host_id, owner_id, project_id):
        """Read-only Git status; distinguish uninitialized and nested repositories."""
        import subprocess
        from pathlib import Path
        if not ident(project_id):
            return None
        with self.authority.store._tx() as db:
            if not db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                              (host_id,owner_id)).fetchone():
                return None
            row=db.execute("""SELECT repository_root FROM alpha_game_projects
                WHERE host_id=? AND owner_id=? AND project_id=?""",
                (host_id,owner_id,project_id)).fetchone()
        if row is None:
            return None
        root=Path(row[0])
        if not root.is_dir():
            return {"state":"missing_directory"}
        try:
            result=subprocess.run(["git","-C",str(root),"rev-parse","--show-toplevel"],
                                  capture_output=True,text=True,timeout=8,
                                  stdin=subprocess.DEVNULL)
            if result.returncode!=0:
                return {"state":"not_initialized"}
            actual=Path(result.stdout.strip()).resolve()
            return {"state":"initialized" if actual==root.resolve() else "nested_in_repository",
                    "git_root":str(actual)}
        except (OSError,subprocess.TimeoutExpired,ValueError):
            return {"state":"git_unavailable"}

    def inspect_game_compatibility(self, host_id, owner_id, project_id):
        """Read-only compatibility report for existing or new game repositories."""
        import json
        import subprocess
        from pathlib import Path
        if not ident(project_id):
            return None
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return None
            row=db.execute("""SELECT repository_root,staging_root,output_root
                FROM alpha_game_projects WHERE host_id=? AND owner_id=? AND project_id=?""",
                (host_id,owner_id,project_id)).fetchone()
        if row is None:
            return None
        root=Path(row[0])
        git=self.inspect_game_git(host_id,owner_id,project_id)
        report={"project_id":project_id,"git":git,"manifest":{"state":"missing"},
                "assets":{},"issues":[],"ready":False}
        if not root.is_dir():
            report["issues"].append("repository_directory_missing")
            return report
        manifest=root/".minglefield"/"project.json"
        if manifest.is_symlink():
            report["manifest"]={"state":"unsafe_symlink"}
            report["issues"].append("manifest_unsafe")
        elif manifest.exists():
            if not manifest.is_file():
                report["manifest"]={"state":"not_file"}
                report["issues"].append("manifest_invalid")
            else:
                try:
                    data=json.loads(manifest.read_text(encoding="utf-8"))
                    version=data.get("schema_version") if isinstance(data,dict) else None
                    if type(version) is not int or version<1:
                        report["manifest"]={"state":"invalid_version",
                                            "supported_schema_version":1}
                        report["issues"].append("manifest_invalid_version")
                    elif data.get("project_id")!=project_id:
                        report["manifest"]={"state":"project_mismatch",
                                            "schema_version":version,
                                            "supported_schema_version":1}
                        report["issues"].append("manifest_project_mismatch")
                    elif version>1:
                        report["manifest"]={"state":"newer_version",
                                            "schema_version":version,
                                            "supported_schema_version":1,
                                            "migration":"unsupported_downgrade"}
                        report["issues"].append("manifest_newer_version")
                    else:
                        report["manifest"]={"state":"compatible","schema_version":1,
                                            "supported_schema_version":1,
                                            "migration":"not_required"}
                except (OSError,UnicodeError,ValueError):
                    report["manifest"]={"state":"invalid"}
                    report["issues"].append("manifest_invalid")
        else:
            report["issues"].append("manifest_missing")
        for name,raw in (("staging",row[1]),("output",row[2])):
            path=Path(raw)
            resolved=path.resolve(strict=False)
            inside=resolved.is_relative_to(root.resolve())
            info={"path":raw,"inside_repository":inside,
                  "directory_exists":path.is_dir(),"ignored":None,"tracked":None}
            if inside and git and git.get("state")=="initialized":
                rel=resolved.relative_to(root.resolve()).as_posix()
                try:
                    ignored=subprocess.run(["git","-C",str(root),"check-ignore","-q",
                                            "--no-index","--",rel+"/"],
                                           timeout=8,stdin=subprocess.DEVNULL,
                                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    info["ignored"]=ignored.returncode==0
                    tracked=subprocess.run(["git","-C",str(root),"ls-files","-z","--",rel],
                                           timeout=8,stdin=subprocess.DEVNULL,
                                           capture_output=True)
                    if tracked.returncode==0:
                        info["tracked"]=len([x for x in tracked.stdout.split(b"\0") if x])
                except (OSError,subprocess.TimeoutExpired):
                    report["issues"].append(name+"_git_check_unavailable")
                if info["ignored"] is False:
                    report["issues"].append(name+"_not_ignored")
                if info["tracked"]:
                    report["issues"].append(name+"_has_tracked_files")
            report["assets"][name]=info
        if git and git.get("state") not in ("initialized","not_initialized"):
            report["issues"].append("git_"+git.get("state","unknown"))
        report["ready"]=not report["issues"]
        return report

    def inspect_game_integration_update(self, host_id, owner_id, project_id,
                                        release_repository=None, release_fetcher=None):
        """Read-only integration status; GitHub source must be explicitly selected."""
        report=self.inspect_game_compatibility(host_id,owner_id,project_id)
        if report is None:
            return None
        manifest=report["manifest"]
        state=manifest["state"]
        installed=manifest.get("schema_version")
        if state=="compatible":
            update_state="availability_unknown"
        elif state=="missing":
            update_state="setup_required"
        else:
            update_state="manual_review_required"
        release_catalog={"state":"not_configured"}
        if release_repository is not None:
            from game_release_metadata import fetch_releases
            fetcher=release_fetcher or fetch_releases
            try:
                release_catalog=fetcher(release_repository)
                if not isinstance(release_catalog,dict) or release_catalog.get("state") not in ("available","unavailable"):
                    release_catalog={"state":"unavailable","reason":"invalid_adapter_response","releases":[]}
            except (ValueError,TypeError):
                release_catalog={"state":"unavailable","reason":"invalid_repository","releases":[]}
        return {"project_id":project_id,
                "installed_schema_version":installed,
                "supported_schema_version":1,
                "integration_version":None,
                "update_state":update_state,
                "release_catalog":release_catalog,
                "update_available":None,
                "notes":"Installed integration version is unknown; release metadata does not establish update availability.",
                "manifest_state":state}

    def prepare_game_manifest(self, host_id, owner_id, project_id, revision):
        """Create a minimal versioned manifest, preserving any existing manifest."""
        import json
        from pathlib import Path
        if not ident(project_id) or type(revision) is not int or revision<1:
            return {"state":"denied","reason":"invalid_manifest_prepare"}
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return {"state":"denied","reason":"not_host_owner"}
            row=db.execute("""SELECT repository_root,settings_revision FROM alpha_game_projects
                WHERE host_id=? AND owner_id=? AND project_id=?""",
                (host_id,owner_id,project_id)).fetchone()
        if row is None:
            return {"state":"denied","reason":"project_not_found"}
        root,actual_revision=row
        if revision!=actual_revision:
            return {"state":"denied","reason":"revision_conflict"}
        repo=Path(root)
        if not repo.is_dir():
            return {"state":"denied","reason":"repository_directory_missing"}
        directory=repo/".minglefield"
        target=directory/"project.json"
        try:
            if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
                return {"state":"denied","reason":"manifest_directory_unsafe"}
            if target.is_symlink():
                return {"state":"denied","reason":"manifest_target_unsafe"}
            if target.exists():
                report=self.inspect_game_compatibility(host_id,owner_id,project_id)
                return {"state":"unchanged","reason":"manifest_already_exists",
                        "manifest":report["manifest"]}
            directory.mkdir(exist_ok=True)
            content=json.dumps({"schema_version":1,"project_id":project_id},
                               indent=2,ensure_ascii=False)+"\n"
            with target.open("x",encoding="utf-8",newline="\n") as stream:
                stream.write(content)
            return {"state":"created","path":str(target),"schema_version":1}
        except FileExistsError:
            return {"state":"unchanged","reason":"manifest_already_exists"}
        except (OSError,ValueError):
            return {"state":"denied","reason":"manifest_filesystem_error"}

    def initialize_game_git(self, host_id, owner_id, project_id, revision, profile_id):
        """Explicit, owner-scoped git init; never commits or changes remotes."""
        import subprocess
        from pathlib import Path
        if not ident(project_id) or not ident(profile_id) or type(revision) is not int:
            return {"state":"denied","reason":"invalid_git_init"}
        with self.authority.store._tx() as db:
            if not db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                              (host_id,owner_id)).fetchone():
                return {"state":"denied","reason":"not_host_owner"}
            row=db.execute("""SELECT repository_root,settings_revision FROM alpha_game_projects
                WHERE host_id=? AND owner_id=? AND project_id=?""",
                (host_id,owner_id,project_id)).fetchone()
            profile=db.execute("""SELECT git_executable FROM alpha_git_profiles
                WHERE host_id=? AND owner_id=? AND profile_id=?""",
                (host_id,owner_id,profile_id)).fetchone()
        if row is None:
            return {"state":"denied","reason":"project_not_found"}
        if profile is None:
            return {"state":"denied","reason":"git_profile_not_found"}
        root=Path(row[0])
        if revision!=row[1]:
            return {"state":"denied","reason":"revision_conflict"}
        if not root.is_dir() or root.is_symlink():
            return {"state":"denied","reason":"repository_directory_invalid"}
        status=self.inspect_game_git(host_id,owner_id,project_id)
        if status is None or status["state"]!="not_initialized":
            return {"state":"denied","reason":"repository_not_uninitialized",
                    "git_status":status}
        try:
            command=[profile[0],"-C",str(root),"init"]
            result=subprocess.run(command,capture_output=True,text=True,timeout=20,
                                  stdin=subprocess.DEVNULL,
                                  env=__import__("os").environ.copy())
            if result.returncode:
                return {"state":"denied","reason":"git_init_failed"}
            return {"state":"initialized","reason":"git_init_completed"}
        except (OSError,subprocess.TimeoutExpired,ValueError):
            return {"state":"denied","reason":"git_unavailable"}

    def delete_game_project(self, host_id, owner_id, project_id, revision):
        """Remove only a registry row, never project directories or files."""
        if not ident(project_id) or type(revision) is not int or revision < 1:
            return HostDecision("denied","invalid_project_delete")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return HostDecision("denied","not_host_owner")
            row=db.execute("""SELECT settings_revision FROM alpha_game_projects
                WHERE host_id=? AND owner_id=? AND project_id=?""",
                (host_id,owner_id,project_id)).fetchone()
            if row is None:
                return HostDecision("denied","project_not_found")
            if row[0]!=revision:
                return HostDecision("denied","revision_conflict")
            db.execute("""DELETE FROM alpha_game_projects WHERE host_id=? AND owner_id=?
                AND project_id=? AND settings_revision=?""",
                (host_id,owner_id,project_id,revision))
        return HostDecision("deleted","game_project_unregistered")

    def host_settings(self, host_id, owner_id):
        with self.authority.store._tx() as db:
            if not db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                              (host_id,owner_id)).fetchone():
                return None
            row=db.execute("SELECT settings FROM sec01_host_settings WHERE host_id=?",
                           (host_id,)).fetchone()
            return json.loads(row[0]) if row else {"staging_root":"","output_root":""}

    def save_host_settings(self, host_id, owner_id, settings):
        from pathlib import Path
        if type(settings) is not dict or set(settings)!={"staging_root","output_root"}:
            return HostDecision("denied","invalid_settings")
        for value in settings.values():
            if type(value) is not str or (value and
                    (not Path(value).is_absolute() or len(value)>1024)):
                return HostDecision("denied","invalid_host_path")
        with self.authority.store._tx() as db:
            if not db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                              (host_id,owner_id)).fetchone():
                return HostDecision("denied","not_host_owner")
            db.execute("INSERT INTO sec01_host_settings(host_id,settings) VALUES(?,?) ON CONFLICT(host_id) DO UPDATE SET settings=excluded.settings",
                       (host_id,json.dumps(settings,sort_keys=True)))
        return HostDecision("saved","host_settings_saved")

    def upsert_runtime(self, host_id, owner_id, config):
        """Store host-owned runtime settings without starting execution."""
        if not ident(host_id) or not ident(owner_id):
            return HostDecision("denied", "invalid_host")
        try:
            runtime = validate_runtime(config)
        except (RuntimeConfigurationError, ValueError):
            return HostDecision("denied", "invalid_runtime")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id, owner_id)).fetchone() is None:
                return HostDecision("denied", "not_host_owner")
            db.execute("""INSERT INTO sec01_host_runtimes
                (host_id,runtime_id,config) VALUES(?,?,?)
                ON CONFLICT(host_id,runtime_id) DO UPDATE SET config=excluded.config""",
                (host_id, runtime["id"], json.dumps(runtime, sort_keys=True)))
        return HostDecision("saved", "runtime_config_saved")

    def list_runtimes(self, host_id, owner_id):
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id, owner_id)).fetchone() is None:
                return None
            rows = db.execute("SELECT config FROM sec01_host_runtimes WHERE host_id=? ORDER BY runtime_id",
                              (host_id,)).fetchall()
            return [json.loads(row[0]) for row in rows]

    def delete_runtime(self, host_id, owner_id, runtime_id):
        if not all(ident(v) for v in (host_id, owner_id, runtime_id)):
            return HostDecision("denied", "invalid_runtime")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id, owner_id)).fetchone() is None:
                return HostDecision("denied", "not_host_owner")
            count = db.execute("DELETE FROM sec01_host_runtimes WHERE host_id=? AND runtime_id=?",
                               (host_id, runtime_id)).rowcount
            return HostDecision("deleted" if count else "denied",
                                "runtime_deleted" if count else "runtime_missing")

    def claim_local_host(self, host_id, owner_id):
        """Only invoke after gateway-local bootstrap proof AND live Alpha session."""
        if not ident(host_id) or not ident(owner_id):
            return HostDecision("denied","invalid_host")
        with self.authority.store._tx() as db:
            if db.execute("""SELECT 1 FROM alpha_users WHERE user_id=? AND disabled=0""",
                          (owner_id,)).fetchone() is None:
                return HostDecision("denied","invalid_owner")
            old=db.execute("""SELECT owner_id FROM sec01_host_owners
                WHERE host_id=?""",(host_id,)).fetchone()
            if old is not None:
                return HostDecision("claimed" if old==(owner_id,) else "denied",
                    "already_owned" if old==(owner_id,) else "host_owned_by_other_user")
            host=db.execute("""SELECT operator_id FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()
            if host is not None and host[0]!=owner_id:
                return HostDecision("denied","existing_host_requires_operator_migration")
            if host is None:
                db.execute("""INSERT INTO alpha_executor_hosts VALUES(?,?,1)""",
                           (host_id,owner_id))
            db.execute("""INSERT INTO sec01_host_owners VALUES(?,?)""",
                       (host_id,owner_id))
            return HostDecision("claimed","local_host_claimed_no_effect")

    def import_comfy_workflow(self, host_id, owner_id, runtime_id, effect_id,
                              description, workflow, object_info, bindings):
        """Create a new disabled effect with a validated workflow; never overwrite."""
        if (not all(ident(v) for v in (host_id, owner_id, runtime_id, effect_id))
                or type(description) is not str or len(description)>256
                or type(workflow) is not dict or type(object_info) is not dict):
            return HostDecision("denied", "invalid_workflow_import")
        raw = json.dumps(workflow, separators=(",", ":"), ensure_ascii=False)
        try:
            prepared = prepare_comfy_effect(raw, object_info, bindings)
        except (WorkflowError, ValueError, TypeError):
            return HostDecision("denied", "invalid_workflow_import")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id, owner_id)).fetchone() is None:
                return HostDecision("denied", "not_host_owner")
            row = db.execute("SELECT config FROM sec01_host_runtimes WHERE host_id=? AND runtime_id=?",
                             (host_id, runtime_id)).fetchone()
            if row is None or json.loads(row[0])["type"] != "comfyui":
                return HostDecision("denied", "runtime_unavailable")
            if db.execute("""SELECT 1 FROM sec01_host_effect_definitions
                WHERE host_id=? AND effect_id=?""",(host_id,effect_id)).fetchone():
                return HostDecision("denied", "effect_id_already_exists")
            db.execute("""INSERT INTO sec01_host_effect_definitions
                (host_id,effect_id,description,enabled) VALUES(?,?,?,0)""",
                (host_id,effect_id,description))
            db.execute("""INSERT INTO sec01_host_comfy_workflows
                (host_id,effect_id,runtime_id,workflow,metadata) VALUES(?,?,?,?,?)""",
                (host_id,effect_id,runtime_id,raw,json.dumps(prepared,sort_keys=True)))
        return HostDecision("saved", "comfy_workflow_saved_disabled_no_execution")

    def define_effect(self, host_id, owner_id, effect_id, description, enabled):
        """Metadata only. No arbitrary commands, paths, endpoints or execution."""
        if (not ident(host_id) or not ident(owner_id) or not ident(effect_id)
                or type(description) is not str or len(description)>256
                or type(enabled) is not bool):
            return HostDecision("denied","invalid_effect_definition")
        with self.authority.store._tx() as db:
            if db.execute("""SELECT 1 FROM sec01_host_owners\n                WHERE host_id=? AND owner_id=?""",(host_id,owner_id)).fetchone() is None:
                return HostDecision("denied","not_host_owner")
            db.execute("""INSERT INTO sec01_host_effect_definitions VALUES(?,?,?,?)
                ON CONFLICT(host_id,effect_id) DO UPDATE SET
                description=excluded.description,enabled=excluded.enabled""",
                (host_id,effect_id,description,int(enabled)))
            return HostDecision("saved","effect_metadata_only")

    def claim_comfy_execution(self, host_id, owner_id, job_id):
        """Atomically claim one reserved job for one explicit local submission."""
        with self.authority.store._tx() as db:
            row=db.execute("""SELECT j.effect_id,j.state,w.workflow,w.metadata,r.config,
                p.workflow_sha256,p.parameters
                FROM sec01_host_jobs j
                JOIN sec01_host_comfy_workflows w ON w.host_id=j.host_id
                    AND w.effect_id=j.effect_id
                JOIN sec01_host_runtimes r ON r.host_id=w.host_id
                    AND r.runtime_id=w.runtime_id
                JOIN sec01_host_job_parameters p ON p.job_id=j.job_id
                WHERE j.host_id=? AND j.job_id=? AND EXISTS
                (SELECT 1 FROM sec01_host_owners o WHERE o.host_id=j.host_id
                 AND o.owner_id=?)""",(host_id,job_id,owner_id)).fetchone()
            if row is None or row[1]!="reserved":
                return None
            effect_id,state,workflow,metadata,runtime,sha,parameters=row
            runtime=json.loads(runtime)
            if not runtime.get("enabled") or runtime.get("type")!="comfyui":
                return None
            if db.execute("""SELECT enabled FROM sec01_host_effect_definitions
                WHERE host_id=? AND effect_id=?""",(host_id,effect_id)).fetchone()!=(1,):
                return None
            if db.execute("""SELECT active FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()!=(1,):
                return None
            if db.execute("""SELECT 1 FROM sec01_host_active_slots
                WHERE host_id=? AND effect_key=?""",(host_id,job_id)).fetchone() is None:
                return None
            if db.execute("""UPDATE sec01_host_jobs SET state='submitting'
                WHERE host_id=? AND job_id=? AND state='reserved'""",
                (host_id,job_id)).rowcount!=1:
                return None
            return {"workflow":json.loads(workflow),"metadata":json.loads(metadata),
                    "runtime":runtime,"workflow_sha256":sha,
                    "parameters":json.loads(parameters)}

    def record_comfy_submission(self, host_id, job_id, prompt_id, error=None):
        """Keep uncertain submissions distinct; never automatically resubmit."""
        with self.authority.store._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_comfy_executions(
                job_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                prompt_id TEXT, error TEXT)""")
            db.execute("""INSERT INTO sec01_host_comfy_executions
                (job_id,host_id,prompt_id,error) VALUES(?,?,?,?)
                ON CONFLICT(job_id) DO UPDATE SET
                prompt_id=excluded.prompt_id,error=excluded.error""",
                (job_id,host_id,prompt_id,error))
            db.execute("""UPDATE sec01_host_jobs SET state=?
                WHERE host_id=? AND job_id=? AND state='submitting'""",
                ("submitted" if prompt_id else "submission_unknown",host_id,job_id))

    def record_comfy_preflight_failure(self, host_id, job_id, error):
        """Finalize a failure before /prompt; no remote submission is possible."""
        with self.authority.store._tx() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_comfy_executions(
                job_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                prompt_id TEXT, error TEXT)""")
            updated=db.execute("""UPDATE sec01_host_jobs SET state='failed'
                WHERE host_id=? AND job_id=? AND state='submitting'""",
                (host_id,job_id)).rowcount
            if not updated:
                return False
            db.execute("""INSERT INTO sec01_host_comfy_executions
                (job_id,host_id,prompt_id,error) VALUES(?,?,NULL,?)
                ON CONFLICT(job_id) DO UPDATE SET
                prompt_id=NULL,error=excluded.error""",
                (job_id,host_id,error))
            db.execute("""DELETE FROM sec01_host_active_slots
                WHERE host_id=? AND effect_key=?""",(host_id,job_id))
            return True

    def comfy_execution_context(self, host_id, owner_id, job_id):
        with self.authority.store._tx() as db:
            if db.execute("""SELECT 1 FROM sec01_host_owners
                WHERE host_id=? AND owner_id=?""",(host_id,owner_id)).fetchone() is None:
                return None
            db.execute("""CREATE TABLE IF NOT EXISTS sec01_host_comfy_executions(
                job_id TEXT PRIMARY KEY, host_id TEXT NOT NULL,
                prompt_id TEXT, error TEXT)""")
            row=db.execute("""SELECT j.state,e.prompt_id,e.error,r.config
                FROM sec01_host_jobs j
                JOIN sec01_host_comfy_workflows w ON w.host_id=j.host_id
                    AND w.effect_id=j.effect_id
                JOIN sec01_host_runtimes r ON r.host_id=w.host_id
                    AND r.runtime_id=w.runtime_id
                LEFT JOIN sec01_host_comfy_executions e ON e.job_id=j.job_id
                WHERE j.host_id=? AND j.job_id=?""",(host_id,job_id)).fetchone()
            return ({"state":row[0],"prompt_id":row[1],"error":row[2],
                     "runtime":json.loads(row[3])} if row else None)

    def finish_comfy_execution(self, host_id, job_id, state):
        if state not in ("completed","failed"):
            return False
        with self.authority.store._tx() as db:
            updated=db.execute("""UPDATE sec01_host_jobs SET state=?
                WHERE host_id=? AND job_id=? AND state='submitted'""",
                (state,host_id,job_id)).rowcount
            if updated:
                db.execute("""DELETE FROM sec01_host_active_slots
                    WHERE host_id=? AND effect_key=?""",(host_id,job_id))
            return bool(updated)

    def comfy_file_parameter_context(self, host_id, owner_id, effect_id):
        """Owner-scoped file enum bindings and configured ComfyUI runtime."""
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?",
                          (host_id,owner_id)).fetchone() is None:
                return None
            row=db.execute("""SELECT w.runtime_id,w.metadata,r.config
                FROM sec01_host_comfy_workflows w JOIN sec01_host_runtimes r
                ON w.host_id=r.host_id AND w.runtime_id=r.runtime_id
                WHERE w.host_id=? AND w.effect_id=?""",(host_id,effect_id)).fetchone()
            if not row:
                return None
            runtime_id,raw,config=row
            metadata=json.loads(raw)
            specs=[p for p in metadata.get("parameters",[])
                   if p.get("type") in ("enum","file")]
            return {"runtime":json.loads(config),"parameters":specs}

    def manual_start_mock(self, host_id, owner_id, effect_id, parameters=None, current_file_choices=None):
        """Persist validated parameter snapshot as a queued mock intent; never execute."""
        import secrets
        if type(parameters) is not dict and parameters is not None:
            return HostDecision("denied","invalid_job_parameters")
        with self.authority.store._tx() as db:
            if db.execute("""SELECT 1 FROM sec01_host_owners
                WHERE host_id=? AND owner_id=?""",(host_id,owner_id)).fetchone() is None:
                return HostDecision("denied","not_host_owner")
            row=db.execute("""SELECT enabled FROM sec01_host_effect_definitions
                WHERE host_id=? AND effect_id=?""",(host_id,effect_id)).fetchone()
            if row!=(1,):
                return HostDecision("denied","effect_unavailable")
            workflow=db.execute("""SELECT metadata FROM sec01_host_comfy_workflows
                WHERE host_id=? AND effect_id=?""",(host_id,effect_id)).fetchone()
            values=parameters if parameters is not None else {}
            snapshot=None
            if workflow:
                metadata=json.loads(workflow[0])
                specs={p["binding"]:p for p in metadata.get("parameters",[])}
                if set(values)!=set(specs):
                    return HostDecision("denied","parameter_keys_mismatch")
                for key,value in values.items():
                    spec=specs[key]
                    kind=spec["type"]
                    if kind=="integer" and (type(value) is not int):
                        return HostDecision("denied","invalid_parameter_type")
                    if kind=="number" and (type(value) not in (int,float) or not -1e100<float(value)<1e100):
                        return HostDecision("denied","invalid_parameter_type")
                    if kind=="boolean" and type(value) is not bool:
                        return HostDecision("denied","invalid_parameter_type")
                    if kind in ("string","enum","file") and type(value) is not str:
                        return HostDecision("denied","invalid_parameter_type")
                    constraints=spec.get("constraints",spec.get("limits",{}))
                    if kind=="enum" and value not in ((current_file_choices or {}).get(key, constraints.get("choices",spec.get("choices",[])))):
                        return HostDecision("denied","invalid_parameter_choice")
                    if kind in ("integer","number"):
                        minimum=constraints.get("min")
                        maximum=constraints.get("max")
                        if type(minimum) in (int,float) and value<minimum:
                            return HostDecision("denied","parameter_below_minimum")
                        if type(maximum) in (int,float) and value>maximum:
                            return HostDecision("denied","parameter_above_maximum")
                    if kind not in ("integer","number","boolean","string","enum","file"):
                        return HostDecision("denied","invalid_parameter_type")
                snapshot=(metadata["workflow_sha256"],json.dumps(values,allow_nan=False,sort_keys=True))
            elif values:
                return HostDecision("denied","effect_has_no_parameters")
            job_id="hostjob."+secrets.token_hex(12)
            db.execute("""INSERT INTO sec01_host_jobs
                (job_id,host_id,effect_id,requested_by,state,created_at)
                VALUES(?,?,?,?,?,?)""",
                (job_id,host_id,effect_id,owner_id,"queued",
                 datetime.now(timezone.utc).isoformat()))
            if snapshot:
                db.execute("""INSERT INTO sec01_host_job_parameters
                    (job_id,host_id,effect_id,workflow_sha256,parameters)
                    VALUES(?,?,?,?,?)""",
                    (job_id,host_id,effect_id,snapshot[0],snapshot[1]))
            return HostDecision("queued_mock",job_id)

    def retry_cancelled_host_job(self, host_id, actor_id, job_id):
        """Create a new queued intent, keeping the cancelled original."""
        import secrets
        if not all(ident(v) for v in (host_id, actor_id, job_id)):
            return HostDecision("denied", "invalid_job")
        with self.authority.store._tx() as db:
            row = db.execute("SELECT effect_id, requested_by, state FROM sec01_host_jobs WHERE host_id=? AND job_id=?", (host_id, job_id)).fetchone()
            owner = db.execute("SELECT 1 FROM sec01_host_owners WHERE host_id=? AND owner_id=?", (host_id, actor_id)).fetchone()
            if row is None or (row[1] != actor_id and owner is None):
                return HostDecision("denied", "not_job_requester_or_host_owner")
            if row[2] != "cancelled":
                return HostDecision("denied", "job_not_cancelled")
            effect = db.execute("SELECT enabled FROM sec01_host_effect_definitions WHERE host_id=? AND effect_id=?", (host_id, row[0])).fetchone()
            if effect != (1,):
                return HostDecision("denied", "effect_unavailable")
            new_id = "hostjob." + secrets.token_hex(12)
            db.execute("INSERT INTO sec01_host_jobs(job_id,host_id,effect_id,requested_by,state,created_at) VALUES(?,?,?,?,?,?)", (new_id,host_id,row[0],actor_id,"queued",datetime.now(timezone.utc).isoformat()))
            return HostDecision("queued_mock", new_id)

    def list_host_jobs(self, host_id, owner_id):
        """Owner-scoped, read-only persisted manual intents."""
        with self.authority.store._tx() as db:
            if db.execute("""SELECT 1 FROM sec01_host_owners
                WHERE host_id=? AND owner_id=?""",(host_id,owner_id)).fetchone() is None:
                return None
            rows=db.execute("""SELECT job_id,effect_id,state,created_at
                FROM sec01_host_jobs WHERE host_id=?
                ORDER BY created_at DESC,job_id DESC LIMIT 200""",
                (host_id,)).fetchall()
            result=[]
            for job,effect,state,created in rows:
                param=db.execute("""SELECT workflow_sha256,parameters
                    FROM sec01_host_job_parameters WHERE job_id=?""",(job,)).fetchone()
                result.append(dict(job_id=job,effect_id=effect,state=state,
                    created_at=created,workflow_sha256=param[0] if param else None,
                    parameters=json.loads(param[1]) if param else {}))
            return result

    def cancel_queued_host_job(self, host_id, owner_id, job_id):
        """Atomic owner cancellation. A queued intent never reserves a slot."""
        if not all(ident(v) for v in (host_id,owner_id,job_id)):
            return HostDecision("denied","invalid_job")
        with self.authority.store._tx() as db:
            row=db.execute("""SELECT requested_by FROM sec01_host_jobs
                WHERE host_id=? AND job_id=?""",(host_id,job_id)).fetchone()
            owner=db.execute("""SELECT 1 FROM sec01_host_owners
                WHERE host_id=? AND owner_id=?""",(host_id,owner_id)).fetchone()
            if row is None or (row[0]!=owner_id and owner is None):
                return HostDecision("denied","not_job_requester_or_host_owner")
            updated=db.execute("""UPDATE sec01_host_jobs SET state='cancelled'
                WHERE host_id=? AND job_id=? AND state IN ('queued','waiting')""",
                (host_id,job_id)).rowcount
            if updated:
                return HostDecision("cancelled_mock","queued_intent_cancelled")
            row=db.execute("""SELECT state FROM sec01_host_jobs
                WHERE host_id=? AND job_id=?""",(host_id,job_id)).fetchone()
            if row==("cancelled",):
                return HostDecision("cancelled_mock","already_cancelled")
            return HostDecision("denied","job_not_cancellable")

    def evaluate_queued_host_job(self, host_id, owner_id, job_id, *, now):
        """Schedule preflight only: no reservation, approval or execution."""
        if (not all(ident(v) for v in (host_id,owner_id,job_id))
                or type(now) is not int):
            return HostDecision("denied","invalid_evaluation")
        with self.authority.store._tx() as db:
            if db.execute("""SELECT 1 FROM sec01_host_owners
                WHERE host_id=? AND owner_id=?""",(host_id,owner_id)).fetchone() is None:
                return HostDecision("denied","not_host_owner")
            row=db.execute("""SELECT effect_id,state FROM sec01_host_jobs
                WHERE host_id=? AND job_id=?""",(host_id,job_id)).fetchone()
            if row is None:
                return HostDecision("denied","job_missing")
            effect_id,state=row
            if state not in ("queued","waiting"):
                return HostDecision("denied","job_not_evaluable")
            host=db.execute("""SELECT active FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()
            effect=db.execute("""SELECT enabled FROM sec01_host_effect_definitions
                WHERE host_id=? AND effect_id=?""",(host_id,effect_id)).fetchone()
            reason="host_unavailable" if host!=(1,) else (
                "effect_unavailable" if effect!=(1,) else "no_enabled_rule")
            if host==(1,) and effect==(1,):
                rules=db.execute("""SELECT config FROM sec01_host_rules
                    WHERE host_id=? AND enabled=1 ORDER BY priority,rule_id""",
                    (host_id,)).fetchall()
                reason="outside_schedule" if rules else "no_enabled_rule"
                for (encoded,) in rules:
                    config=json.loads(encoded)
                    local=datetime.fromtimestamp(now,timezone.utc).astimezone(
                        ZoneInfo(config["timezone"]))
                    minute=local.hour*60+local.minute
                    if not _window_matches(config, local):
                        continue
                    if config["mode"]=="manual":
                        reason="manual_approval_required"
                    elif config["idle_only"] or config["gpu_max_percent"] is not None:
                        reason="trusted_telemetry_required"
                    else:
                        limit=config.get("max_parallel_effects")
                        active=db.execute("""SELECT COUNT(*) FROM sec01_host_active_slots
                            WHERE host_id=?""",(host_id,)).fetchone()[0]
                        reason=("parallel_limit_reached" if limit is not None
                                and active>=limit else "awaiting_final_authorization")
                    break
            db.execute("""UPDATE sec01_host_jobs SET state='waiting'
                WHERE host_id=? AND job_id=? AND state IN ('queued','waiting')""",
                (host_id,job_id))
            return HostDecision("waiting",reason)

    def reserve_waiting_host_job_mock(self, host_id, owner_id, job_id, *, now):
        """Atomic local slot accounting only; NOT final authorization."""
        if (not all(ident(v) for v in (host_id,owner_id,job_id))
                or type(now) is not int):
            return HostDecision("denied","invalid_reservation")
        with self.authority.store._tx() as db:
            if db.execute("""SELECT 1 FROM sec01_host_owners
                WHERE host_id=? AND owner_id=?""",(host_id,owner_id)).fetchone() is None:
                return HostDecision("denied","not_host_owner")
            row=db.execute("""SELECT effect_id,state FROM sec01_host_jobs
                WHERE host_id=? AND job_id=?""",(host_id,job_id)).fetchone()
            if row is None or row[1]!="waiting":
                return HostDecision("denied","job_not_waiting")
            effect_id=row[0]
            if db.execute("""SELECT active FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()!=(1,):
                return HostDecision("waiting","host_unavailable")
            if db.execute("""SELECT enabled FROM sec01_host_effect_definitions
                WHERE host_id=? AND effect_id=?""",(host_id,effect_id)).fetchone()!=(1,):
                return HostDecision("waiting","effect_unavailable")
            rules=db.execute("""SELECT config FROM sec01_host_rules
                WHERE host_id=? AND enabled=1 ORDER BY priority,rule_id""",
                (host_id,)).fetchall()
            if not rules:
                return HostDecision("waiting","no_enabled_rule")
            for (encoded,) in rules:
                config=json.loads(encoded)
                local=datetime.fromtimestamp(now,timezone.utc).astimezone(
                    ZoneInfo(config["timezone"]))
                minute=local.hour*60+local.minute
                if not _window_matches(config, local):
                    continue
                if config["mode"]!="automatic":
                    return HostDecision("waiting","manual_approval_required")
                if config["idle_only"] or config["gpu_max_percent"] is not None:
                    return HostDecision("waiting","trusted_telemetry_required")
                limit=config.get("max_parallel_effects")
                active=db.execute("""SELECT COUNT(*) FROM sec01_host_active_slots
                    WHERE host_id=?""",(host_id,)).fetchone()[0]
                if limit is not None and active>=limit:
                    return HostDecision("waiting","parallel_limit_reached")
                db.execute("""INSERT INTO sec01_host_active_slots(effect_key,host_id)
                    VALUES(?,?)""",(job_id,host_id))
                db.execute("""UPDATE sec01_host_jobs SET state='reserved'
                    WHERE host_id=? AND job_id=? AND state='waiting'""",
                    (host_id,job_id))
                return HostDecision("reserved_mock","slot_held_no_authorization_or_execution")
            return HostDecision("waiting","outside_schedule")

    def release_reserved_host_job_mock(self, host_id, owner_id, job_id):
        """Owner resolution of a mock reservation, without any effect."""
        if not all(ident(v) for v in (host_id,owner_id,job_id)):
            return HostDecision("denied","invalid_release")
        with self.authority.store._tx() as db:
            job=db.execute("""SELECT requested_by,state FROM sec01_host_jobs
                WHERE host_id=? AND job_id=?""",(host_id,job_id)).fetchone()
            owner=db.execute("""SELECT 1 FROM sec01_host_owners
                WHERE host_id=? AND owner_id=?""",(host_id,owner_id)).fetchone()
            if job is None or (job[0]!=owner_id and owner is None):
                return HostDecision("denied","not_job_requester_or_host_owner")
            row=(job[1],)
            if row!=("reserved",):
                return HostDecision("denied","job_not_reserved")
            db.execute("""UPDATE sec01_host_jobs SET state='waiting'
                WHERE host_id=? AND job_id=? AND state='reserved'""",
                (host_id,job_id))
            db.execute("""DELETE FROM sec01_host_active_slots
                WHERE host_id=? AND effect_key=?""",(host_id,job_id))
            return HostDecision("waiting_mock","reserved_mock_slot_released_job_retained")

    def add_admin_fixture(self, host_id, admin_id):
        """Trusted LOCAL provisioning; never expose to a requester."""
        if not ident(host_id) or not ident(admin_id):
            raise ValueError("invalid administrator")
        with self.authority.store._tx() as db:
            if db.execute("SELECT 1 FROM alpha_executor_hosts WHERE host_id=?",
                          (host_id,)).fetchone() is None:
                raise ValueError("unknown host")
            db.execute("INSERT INTO sec01_host_admins VALUES(?,?)",
                       (host_id,admin_id))

    @staticmethod
    def _validate(config):
        if type(config) is not dict or not {"mode","idle_only","gpu_max_percent","timezone","weekdays","start_minute","end_minute"} <= set(config) or set(config)-{"mode","idle_only","gpu_max_percent","timezone","weekdays","start_minute","end_minute","max_parallel_effects"}: 
            raise ValueError("invalid rule")
        limit=config.get("max_parallel_effects")
        if limit is not None and (type(limit) is not int or not 1<=limit<=1024):
            raise ValueError("invalid parallel limit")
        if config["mode"] not in ("automatic","manual"):
            raise ValueError("invalid mode")
        if type(config["idle_only"]) is not bool:
            raise ValueError("invalid idle policy")
        gpu=config["gpu_max_percent"]
        if gpu is not None and (type(gpu) is not int or not 0<=gpu<=100):
            raise ValueError("invalid GPU threshold")
        days=config["weekdays"]
        if (type(days) is not list or not days or len(set(map(str,days)))!=len(days)
                or any(type(d) is not int or not 0<=d<=6 for d in days)):
            raise ValueError("invalid weekdays")
        for key in ("start_minute","end_minute"):
            val=config[key]
            if type(val) is not int or not 0<=val<=1440:
                raise ValueError("invalid time window")
        if config["start_minute"]==config["end_minute"]:
            raise ValueError("empty time window")
        try:
            ZoneInfo(config["timezone"])
        except (TypeError,ZoneInfoNotFoundError,ValueError):
            raise ValueError("invalid timezone")

    def _admin(self, db, host_id, admin_id):
        """Host owner or explicitly provisioned legacy host admin.

        This is Minglefield host policy authority, not OS administrator status.
        """
        if not ident(host_id) or not ident(admin_id):
            return False
        owner=db.execute("""SELECT 1 FROM sec01_host_owners
            WHERE host_id=? AND owner_id=?""",(host_id,admin_id)).fetchone()
        if owner is not None:
            return True
        return db.execute("""SELECT 1 FROM sec01_host_admins
            WHERE host_id=? AND admin_id=?""",(host_id,admin_id)).fetchone() is not None

    def upsert_rule(self, host_id, admin_id, rule_id, *, priority, enabled, config):
        if (not all(ident(x) for x in (host_id,admin_id,rule_id))
                or type(priority) is not int or priority<0
                or type(enabled) is not bool):
            return HostDecision("denied","invalid_rule")
        try:
            self._validate(config)
        except ValueError:
            return HostDecision("denied","invalid_rule")
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return HostDecision("denied","not_host_admin")
            db.execute("""INSERT INTO sec01_host_rules VALUES(?,?,?,?,?)
                ON CONFLICT(host_id,rule_id) DO UPDATE SET
                priority=excluded.priority,enabled=excluded.enabled,
                config=excluded.config""",
                (host_id,rule_id,priority,int(enabled),
                 json.dumps(config,sort_keys=True)))
            return HostDecision("saved","rule_saved")

    def delete_rule(self, host_id, admin_id, rule_id):
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return HostDecision("denied","not_host_admin")
            count=db.execute("""DELETE FROM sec01_host_rules
                WHERE host_id=? AND rule_id=?""",(host_id,rule_id)).rowcount
            return HostDecision("deleted" if count else "denied",
                                "rule_deleted" if count else "rule_missing")

    def approve(self, host_id, admin_id, effect_key):
        if not all(ident(x) for x in (host_id,admin_id,effect_key)):
            return HostDecision("denied","invalid_approval")
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return HostDecision("denied","not_host_admin")
            db.execute("""INSERT INTO sec01_host_approvals VALUES(?,?,?)
                ON CONFLICT(host_id,effect_key) DO NOTHING""",
                (host_id,effect_key,admin_id))
            return HostDecision("approved","mock_approval_recorded")

    def decide(self, *, host_id, effect_key, binding, now,
               gpu_percent=None, running_effects=None):
        """Mock commit only. Telemetry and clock must be trusted by real host."""
        if (not ident(host_id) or not ident(effect_key)
                or type(binding) is not str or not 1<=len(binding)<=4096
                or type(now) is not int):
            return HostDecision("denied","invalid_intent")
        with self.authority.store._tx() as db:
            old=db.execute("""SELECT host_id,binding FROM sec01_host_commits
                WHERE effect_key=?""",(effect_key,)).fetchone()
            if old is not None:
                return HostDecision("duplicate" if old==(host_id,binding) else "denied",
                    "historical_mock_commit" if old==(host_id,binding)
                    else "idempotency_binding_mismatch")
            host=db.execute("""SELECT active FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()
            if host!=(1,):
                return HostDecision("denied","host_unavailable")
            admission=db.execute("""SELECT binding FROM alpha_sec01_admissions
                WHERE effect_key=?""",(effect_key,)).fetchone()
            if admission is None or admission[0]!=binding:
                return HostDecision("denied","admission_binding_missing")
            try:
                job,fingerprint,requester,agent,owner,executor,assigned_host,action=json.loads(binding)
            except (ValueError,TypeError):
                return HostDecision("denied","invalid_admission_binding")
            if assigned_host!=host_id or action!="demo.echo":
                return HostDecision("denied","admission_host_mismatch")
            agent_row=db.execute("""SELECT a.user_id,a.disabled,u.disabled
                FROM alpha_agents a JOIN alpha_users u ON u.user_id=a.user_id
                WHERE a.agent_id=?""",(agent,)).fetchone()
            if agent_row!=(owner,0,0):
                return HostDecision("denied","agent_or_owner_revoked")
            requester_row=db.execute("SELECT disabled FROM alpha_users WHERE user_id=?",
                (requester,)).fetchone()
            if requester_row!=(0,):
                return HostDecision("denied","requester_revoked")
            if requester!=owner and db.execute("""SELECT revoked FROM alpha_agent_grants
                WHERE agent_id=? AND grantee_user_id=? AND action='demo.echo'""",
                (agent,requester)).fetchone()!=(0,):
                return HostDecision("denied","grant_revoked")
            host_operator=db.execute("""SELECT operator_id FROM alpha_executor_hosts
                WHERE host_id=?""",(host_id,)).fetchone()
            if host_operator!=(executor,):
                return HostDecision("denied","executor_host_mismatch")
            if db.execute("""SELECT enabled FROM alpha_agent_host_assignments
                WHERE agent_id=? AND host_id=?""",(agent,host_id)).fetchone()!=(1,):
                return HostDecision("denied","host_assignment_revoked")
            rules=db.execute("""SELECT rule_id,config FROM sec01_host_rules
                WHERE host_id=? AND enabled=1 ORDER BY priority,rule_id""",
                (host_id,)).fetchall()
            if not rules:
                return HostDecision("waiting","no_enabled_rule")
            for rule_id,encoded in rules:
                config=json.loads(encoded)
                local=datetime.fromtimestamp(now,timezone.utc).astimezone(
                    ZoneInfo(config["timezone"]))
                minute=local.hour*60+local.minute
                if not _window_matches(config, local):
                    continue
                limit=config.get("max_parallel_effects")
                if limit is not None:
                    active=db.execute("""SELECT COUNT(*) FROM sec01_host_active_slots
                        WHERE host_id=?""",(host_id,)).fetchone()[0]
                    if active>=limit:
                        return HostDecision("waiting","parallel_limit_reached")
                if config["idle_only"]:
                    if type(running_effects) is not int or running_effects<0:
                        return HostDecision("waiting","telemetry_unavailable")
                    if running_effects!=0:
                        return HostDecision("waiting","host_busy")
                threshold=config["gpu_max_percent"]
                if threshold is not None:
                    if (type(gpu_percent) not in (int,float)
                            or not 0<=gpu_percent<=100):
                        return HostDecision("waiting","telemetry_unavailable")
                    if gpu_percent>=threshold:
                        return HostDecision("waiting","gpu_threshold_not_met")
                if config["mode"]=="manual" and db.execute(
                    """SELECT 1 FROM sec01_host_approvals
                    WHERE host_id=? AND effect_key=?""",
                    (host_id,effect_key)).fetchone() is None:
                    return HostDecision("waiting","manual_approval_required")
                db.execute("INSERT INTO sec01_host_commits VALUES(?,?,?,?)",
                           (effect_key,host_id,binding,rule_id))
                db.execute("INSERT INTO sec01_host_active_slots VALUES(?,?)",
                           (effect_key,host_id))
                return HostDecision("committed_mock","no_effect_performed")
            return HostDecision("waiting","outside_schedule")

    def finish_mock(self, host_id, admin_id, effect_key):
        """Trusted local completion simulation; no actual process is stopped."""
        if not all(ident(x) for x in (host_id,admin_id,effect_key)):
            return HostDecision("denied","invalid_completion")
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return HostDecision("denied","not_host_admin")
            count=db.execute("""DELETE FROM sec01_host_active_slots
                WHERE host_id=? AND effect_key=?""",(host_id,effect_key)).rowcount
            return HostDecision("finished_mock" if count else "denied",
                                "slot_released" if count else "slot_missing")

    def active_count(self, host_id):
        with self.authority.store._tx() as db:
            return db.execute("""SELECT COUNT(*) FROM sec01_host_active_slots
                WHERE host_id=?""",(host_id,)).fetchone()[0]

    def list_hosts(self, admin_id):
        """Only hosts administered by this authenticated Alpha user."""
        if not ident(admin_id):
            return []
        with self.authority.store._tx() as db:
            hosts=db.execute("""SELECT h.host_id,h.active FROM alpha_executor_hosts h
                WHERE EXISTS(SELECT 1 FROM sec01_host_admins a
                    WHERE a.host_id=h.host_id AND a.admin_id=?)
                  OR EXISTS(SELECT 1 FROM sec01_host_owners o
                    WHERE o.host_id=h.host_id AND o.owner_id=?)
                ORDER BY h.host_id""",(admin_id,admin_id)).fetchall()
            result=[]
            for host_id,active in hosts:
                rules=db.execute("""SELECT rule_id,priority,enabled,config
                    FROM sec01_host_rules WHERE host_id=?
                    ORDER BY priority,rule_id""",(host_id,)).fetchall()
                slots=db.execute("""SELECT effect_key FROM sec01_host_active_slots
                    WHERE host_id=? ORDER BY effect_key""",(host_id,)).fetchall()
                effects=db.execute("""SELECT effect_id,description,enabled
                    FROM sec01_host_effect_definitions WHERE host_id=?
                    ORDER BY effect_id""",(host_id,)).fetchall()
                workflows=db.execute("""SELECT effect_id,runtime_id,metadata
                    FROM sec01_host_comfy_workflows WHERE host_id=?""",(host_id,)).fetchall()
                workflow_info={eid:dict(runtime_id=rid,
                    parameters=json.loads(meta).get("parameters",[]),
                    selected_bindings=json.loads(meta).get("selected_bindings",[]),
                    workflow_sha256=json.loads(meta).get("workflow_sha256"))
                    for eid,rid,meta in workflows}
                result.append(dict(host_id=host_id,active=bool(active),
                    effects=[dict(effect_id=e,description=d,enabled=bool(on),
                                  comfy_workflow=workflow_info.get(e))
                             for e,d,on in effects],
                    active_effects=len(slots),slots=[x[0] for x in slots],
                    rules=[dict(rule_id=rid,priority=priority,enabled=bool(enabled),
                                config=json.loads(cfg))
                           for rid,priority,enabled,cfg in rules]))
            return result

    def restart_recovery_snapshot(self, host_id, admin_id):
        """Crash-safe conservative policy: all retained slots remain blocked.

        A restart NEVER converts a historical mock commit into a new one.
        Recovery is observational until an admin explicitly resolves a slot.
        """
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return None
            rows=db.execute("""SELECT effect_key FROM sec01_host_active_slots
                WHERE host_id=? ORDER BY effect_key""",(host_id,)).fetchall()
            return [dict(effect_key=key,state="uncertain_after_restart",
                         auto_retry_allowed=False) for (key,) in rows]

    def lifecycle(self, host_id, admin_id):
        """Read-only local mock lifecycle, scoped to a host admin."""
        with self.authority.store._tx() as db:
            if not self._admin(db,host_id,admin_id):
                return None
            rows=db.execute("""SELECT c.effect_key,c.rule_id,
                CASE WHEN s.effect_key IS NULL THEN 'finished_mock'
                     ELSE 'reserved_mock' END
                FROM sec01_host_commits c
                LEFT JOIN sec01_host_active_slots s ON s.effect_key=c.effect_key
                WHERE c.host_id=? ORDER BY c.effect_key""",(host_id,)).fetchall()
            return [dict(effect_key=key,rule_id=rid,state=state)
                    for key,rid,state in rows]

    def commit_count(self):
        with self.authority.store._tx() as db:
            return db.execute("SELECT count(*) FROM sec01_host_commits").fetchone()[0]
