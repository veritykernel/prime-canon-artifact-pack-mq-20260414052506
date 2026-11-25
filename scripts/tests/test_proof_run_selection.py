import importlib.util
from datetime import datetime, timezone
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "select_proof_run.py"
spec = importlib.util.spec_from_file_location("select_proof_run", SCRIPT)
proof = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proof)

HEAD = "a" * 40
QUEUE_HEAD = "b" * 40
MERGE_HEAD = "c" * 40
BEFORE = datetime(2026, 11, 25, 18, 0, tzinfo=timezone.utc)


def run(*, branch, sha=QUEUE_HEAD, created="2026-11-25T18:00:02Z", status="completed", conclusion="success", event="merge_group"):
    return {"event": event, "headBranch": branch, "headSha": sha, "createdAt": created,
            "status": status, "conclusion": conclusion, "url": "https://github.com/owner/repo/actions/runs/1"}


def queue_branch(number=7, source_head=HEAD):
    return f"gh-readonly-queue/main/pr-{number}-{source_head}"


class ProofRunSelectionTests(unittest.TestCase):
    def test_unrelated_success_never_satisfies_this_pr(self):
        runs = [run(branch=queue_branch(71)),
                run(branch=queue_branch(), status="in_progress", conclusion="")]
        selected = proof.select_run(runs, event="merge_group", merge_pr=7, not_before=BEFORE)
        self.assertEqual(selected["status"], "in_progress")

    def test_old_same_pr_run_does_not_satisfy_new_enqueue(self):
        self.assertIsNone(proof.select_run([run(branch=queue_branch(), created="2026-11-25T17:59:59Z")],
                                            event="merge_group", merge_pr=7, not_before=BEFORE))

    def test_exact_commit_selection_does_not_fallback_to_first_run(self):
        self.assertIsNone(proof.select_run([run(branch="main", sha=QUEUE_HEAD, event="push")],
                                            event="push", head_sha=HEAD))

    def test_matching_merge_group_requires_a_full_sha(self):
        matching = run(branch=queue_branch(), sha="short")
        self.assertIsNone(proof.select_run([matching], event="merge_group", merge_pr=7, not_before=BEFORE))

    def test_same_second_queue_runs_are_ambiguous(self):
        runs = [run(branch=queue_branch(source_head="a" * 40)),
                run(branch=queue_branch(source_head="b" * 40))]
        self.assertIsNone(proof.select_run(runs, event="merge_group", merge_pr=7, not_before=BEFORE))

    def test_real_github_merge_queue_branch_is_selected(self):
        branch = "gh-readonly-queue/main/pr-2-4a578b53aaceec38bab0dfb21f0b26f31db073a7"
        selected = proof.select_run([run(branch=branch)], event="merge_group", merge_pr=2,
                                    not_before=BEFORE)
        self.assertIsNotNone(selected)
        self.assertEqual(selected["headBranch"], branch)

    def test_legacy_or_malformed_queue_refs_are_rejected(self):
        branches = [
            "main/pr-7-" + "a" * 40,
            "gh-readonly-queue/release/pr-7-" + "a" * 40,
            "gh-readonly-queue/main/pr-7-short",
            "gh-readonly-queue/main/pr-7-" + "g" * 40,
            "refs/heads/gh-readonly-queue/main/pr-7-" + "a" * 40,
        ]
        for branch in branches:
            with self.subTest(branch=branch):
                self.assertIsNone(proof.select_run([run(branch=branch)], event="merge_group",
                                                    merge_pr=7, not_before=BEFORE))

    def test_merged_state_is_bound_to_exact_pr_head_and_request(self):
        pr = {"number": 7, "state": "MERGED", "headRefOid": HEAD, "mergedAt": "2026-11-25T18:00:03Z",
              "mergeCommit": {"oid": MERGE_HEAD}}
        self.assertTrue(proof.merged_pr_matches(pr, number=7, head_sha=HEAD, not_before=BEFORE))
        self.assertFalse(proof.merged_pr_matches({**pr, "headRefOid": QUEUE_HEAD}, number=7, head_sha=HEAD, not_before=BEFORE))
        self.assertFalse(proof.merged_pr_matches({**pr, "mergedAt": "2026-11-25T17:59:59Z"}, number=7, head_sha=HEAD, not_before=BEFORE))


if __name__ == "__main__":
    unittest.main()
