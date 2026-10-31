"""B2.3c one-shot fake coordinator and crash boundary tests."""
import unittest
from concurrent.futures import ThreadPoolExecutor

import test_action_submission as fixture
from b2_worker import ClaimWorker
from b2_prestart import PrestartGate
from b2_prestart_schema import migrate_b2_prestart
from b2_dispatch_schema import migrate_b2_dispatch
from b2_fake_coordinator import FakeSimulationCoordinator


class FakeCoordinatorTests(unittest.TestCase):
    setUp = fixture.SubmissionTests.setUp
    issue = fixture.SubmissionTests.issue
    new_service = fixture.SubmissionTests.new_service
    query = fixture.SubmissionTests.query
    counts = fixture.SubmissionTests.counts

    def ready(self):
        self.service.submit(**self.args)
        claim = ClaimWorker(self.service).claim_next("worker.one")
        migrate_b2_prestart(self.db)
        self.assertEqual(PrestartGate(self.service).authorize(
            job_id=claim.job_id, worker_id="worker.one",
            claim_token=claim.claim_token).state, "ready")
        migrate_b2_dispatch(self.db)
        return dict(job_id=claim.job_id, worker_id="worker.one",
                    claim_token=claim.claim_token)

    def test_success_and_no_replay(self):
        args = self.ready()
        coordinator = FakeSimulationCoordinator(self.new_service())
        self.assertEqual(coordinator.run_once(**args, scenario="success").state, "succeeded")
        self.assertEqual(FakeSimulationCoordinator(self.new_service()).run_once(
            **args, scenario="success").state, "rejected")
        self.assertEqual(self.counts(), (1, 5, 100))

    def test_timeout_is_unknown(self):
        args = self.ready()
        result = FakeSimulationCoordinator(self.new_service()).run_once(
            **args, scenario="timeout")
        self.assertEqual(result.state, "outcome_unknown")
        self.assertEqual(self.counts(), (1, 5, 100))

    def test_crash_boundaries_do_not_replay(self):
        for point, state, events in (("before_commit", "ready", 3),
                                     ("after_commit", "dispatch_committed", 4),
                                     ("after_call", "dispatch_committed", 4)):
            with self.subTest(point=point):
                self.setUp()
                args = self.ready()
                with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                    FakeSimulationCoordinator(self.new_service()).run_once(
                        **args, scenario="success", crash_at=point)
                self.assertEqual(self.query("SELECT state FROM action_jobs"), [(state,)])
                self.assertEqual(self.counts(), (1, events, 100))
                if point != "before_commit":
                    self.assertEqual(FakeSimulationCoordinator(self.new_service()).run_once(
                        **args, scenario="success").state, "rejected")
                    self.assertEqual(self.counts(), (1, events, 100))

    def test_parallel_coordinators_only_one_terminal_result(self):
        args = self.ready()
        def run(_):
            return FakeSimulationCoordinator(self.new_service()).run_once(
                **args, scenario="success").state
        with ThreadPoolExecutor(max_workers=2) as pool:
            states = sorted(pool.map(run, range(2)))
        self.assertEqual(states, ["rejected", "succeeded"])
        self.assertEqual(self.counts(), (1, 5, 100))

    def test_invalid_scenario_leaves_ready(self):
        args = self.ready()
        self.assertEqual(FakeSimulationCoordinator(self.new_service()).run_once(
            **args, scenario="untrusted").state, "rejected")
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("ready",)])
        self.assertEqual(self.counts(), (1, 3, 100))
