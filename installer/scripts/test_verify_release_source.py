"""Offline tests for the GitHub provenance build-check helper."""
import unittest

from verify_release_source import ProvenanceError, parse_source, verify_source


SHA = "0123456789abcdef0123456789abcdef01234567"
HEAD = "abcdef0123456789abcdef0123456789abcdef01"
SOURCE = (
    "version=1\n"
    "repository_id=1440772489\n"
    "repository=daresan/Minglefield\n"
    "commit=" + SHA + "\n"
)


def github_fixture(repo_id=1440772489, name="daresan/Minglefield", protected=True,
                   comparison_status="ahead", behind_by=0, branch="main"):
    responses = {
        "repos/daresan/Minglefield": {
            "id": repo_id, "full_name": name, "default_branch": branch,
        },
        "repos/daresan/Minglefield/commits/" + SHA: {"sha": SHA},
        "repos/daresan/Minglefield/branches/" + branch: {
            "name": branch, "protected": protected, "commit": {"sha": HEAD},
        },
        "repos/daresan/Minglefield/compare/" + SHA + "..." + HEAD: {
            "status": comparison_status,
            "behind_by": behind_by,
            "base_commit": {"sha": SHA},
            "head_commit": {"sha": HEAD},
        },
    }

    def get(path):
        return responses[path]

    return get


class SourceParsingTests(unittest.TestCase):
    def test_valid_metadata(self):
        source = parse_source(SOURCE)
        self.assertEqual(source["repository_id"], 1440772489)
        self.assertEqual(source["commit"], SHA)

    def test_rejects_invalid_and_ambiguous_metadata(self):
        alternatives = [
            SOURCE.replace("version=1", "version=2"),
            SOURCE + "commit=" + SHA + "\n",
            SOURCE.replace("repository_id=1440772489", "repository_id=0"),
            SOURCE.replace("repository=daresan/Minglefield", "repository=../Minglefield"),
            SOURCE.replace("repository=daresan/Minglefield", "repository=daresan/.."),
            SOURCE.replace("repository=daresan/Minglefield", "repository=daresan/Minglefield/extra"),
            SOURCE.replace("commit=" + SHA, "commit=abc"),
            SOURCE.replace("version=1\n", ""),
        ]
        for candidate in alternatives:
            with self.subTest(candidate=candidate), self.assertRaises(ProvenanceError):
                parse_source(candidate)


class GitHubEvidenceTests(unittest.TestCase):
    def test_official_source_requires_protected_main_ancestry(self):
        result = verify_source(parse_source(SOURCE), github_fixture())
        self.assertEqual(result["distribution"], "official_upstream")
        self.assertTrue(result["source_verified_via_github"])
        self.assertFalse(result["artifact_authenticated"])
        self.assertFalse(result["installation_authorized"])

    def test_wrong_repository_id_rejected(self):
        with self.assertRaises(ProvenanceError):
            verify_source(parse_source(SOURCE), github_fixture(repo_id=3))

    def test_unprotected_main_rejected_for_official(self):
        with self.assertRaises(ProvenanceError):
            verify_source(parse_source(SOURCE), github_fixture(protected=False))

    def test_diverging_or_non_ancestor_commit_rejected(self):
        for status, behind in [("diverged", 1), ("behind", 1), ("ahead", 1)]:
            with self.subTest(status=status), self.assertRaises(ProvenanceError):
                verify_source(parse_source(SOURCE), github_fixture(
                    comparison_status=status, behind_by=behind
                ))

    def test_identity_mismatch_rejected(self):
        with self.assertRaises(ProvenanceError):
            verify_source(parse_source(SOURCE), github_fixture(name="other/Minglefield"))

    def test_independent_fork_not_mislabeled_as_upstream(self):
        source = parse_source(SOURCE)
        source["repository_id"] = 555
        source["repository"] = "forker/Minglefield"

        upstream = github_fixture()
        def fork_get(path):
            response = upstream(path.replace("repos/forker/Minglefield", "repos/daresan/Minglefield"))
            if path == "repos/forker/Minglefield":
                return {"id": 555, "full_name": "forker/Minglefield", "default_branch": "main"}
            return response

        result = verify_source(source, fork_get)
        self.assertEqual(result["distribution"], "independent_fork")
        self.assertFalse(result["installation_authorized"])


if __name__ == "__main__":
    unittest.main()
