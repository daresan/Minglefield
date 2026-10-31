"""B2.3c first slice: fake outcomes and terminal recording without invocation."""
import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor

from test_b2_dispatch_gate import DispatchGateTests
from b2_fake_adapter import DeterministicFakeAdapter, FakeOutcome, FakeOutcomeRecorder


class FakeOutcomeTests(DispatchGateTests):
    # Do not inherit the parent test methods as additional tests.
    __test__ = False

    def committed(self):
        claim = self.prepare()
        self.assertEqual(self.dispatch(claim).state, "dispatch_committed")
        return self.query("SELECT job_id,effect_idempotency_key FROM action_jobs")[0]

    def test_pure_fake_scenarios(self):
        fake = DeterministicFakeAdapter()
        for scenario, expected in (("success", "succeeded"), ("no_effect", "failed"),
                                   ("ambiguous", "outcome_unknown")):
            self.assertEqual(fake.invoke(scenario=scenario), FakeOutcome(expected))
        with self.assertRaises(TimeoutError):
            fake.invoke(scenario="timeout")

    def test_each_terminal_outcome_is_atomic(self):
        for scenario, expected in (("success", "succeeded"), ("no_effect", "failed"),
                                   ("ambiguous", "outcome_unknown")):
            with self.subTest(scenario=scenario):
                # Each subtest has a fresh independent DB.
                if scenario != "success":
                    self.tearDown() if hasattr(self, "tearDown") else None
                    self.setUp()
                job_id, key = self.committed()
                outcome = DeterministicFakeAdapter().invoke(scenario=scenario)
                result = FakeOutcomeRecorder(self.new_service()).record(
                    job_id=job_id, effect_idempotency_key=key, outcome=outcome)
                self.assertEqual(result.state, expected)
                self.assertEqual(self.query("SELECT state FROM action_jobs"), [(expected,)])
                self.assertEqual(self.counts(), (1, 5, 100))

    def test_invalid_or_duplicate_outcome_does_not_mutate(self):
        job_id, key = self.committed()
        recorder = FakeOutcomeRecorder(self.new_service())
        before = self.counts()
        self.assertEqual(recorder.record(job_id=job_id, effect_idempotency_key="effect."+"0"*64,
                                         outcome=FakeOutcome("succeeded")).state, "rejected")
        self.assertEqual(recorder.record(job_id=job_id, effect_idempotency_key=key,
                                         outcome=FakeOutcome("unexpected")).state, "rejected")
        self.assertEqual(self.counts(), before)
        self.assertEqual(recorder.record(job_id=job_id, effect_idempotency_key=key,
                                         outcome=FakeOutcome("succeeded")).state, "succeeded")
        after = self.counts()
        self.assertEqual(recorder.record(job_id=job_id, effect_idempotency_key=key,
                                         outcome=FakeOutcome("failed")).state, "rejected")
        self.assertEqual(self.counts(), after)

    def test_parallel_terminal_writes_only_one_wins(self):
        job_id, key = self.committed()
        def attempt(_):
            return FakeOutcomeRecorder(self.new_service()).record(
                job_id=job_id, effect_idempotency_key=key, outcome=FakeOutcome("succeeded"))
        with ThreadPoolExecutor(max_workers=2) as pool:
            states = sorted(result.state for result in pool.map(attempt, range(2)))
        self.assertEqual(states, ["rejected", "succeeded"])
        self.assertEqual(self.counts(), (1, 5, 100))

    def test_audit_failure_rolls_back_terminal_state(self):
        job_id, key = self.committed()
        self.execute("""CREATE TRIGGER fail_fake_audit BEFORE INSERT ON action_audit
            WHEN NEW.event_type='job.succeeded'
            BEGIN SELECT RAISE(ABORT, 'injected'); END""")
        with self.assertRaisesRegex(sqlite3.IntegrityError, "injected"):
            FakeOutcomeRecorder(self.new_service()).record(
                job_id=job_id, effect_idempotency_key=key, outcome=FakeOutcome("succeeded"))
        self.assertEqual(self.query("SELECT state FROM action_jobs"), [("dispatch_committed",)])
        self.assertEqual(self.counts(), (1, 4, 100))


if __name__ == "__main__":
    unittest.main()
