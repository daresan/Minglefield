"""Authenticated HTTP cleanup, dependency isolation and rollback regressions."""
import json
import re
import unittest
import test_private_alpha_host_owner_ui as fixtures
from private_alpha_delete import delete_resource
from private_alpha_gateway import PAGE


class DeleteTests(unittest.TestCase):
    setUp = fixtures.OwnerUiTests.setUp
    req = fixtures.OwnerUiTests.req
    claim = fixtures.OwnerUiTests.claim

    def resources(self):
        self.claim(self.owner)
        self.policy.define_effect("host.local", "user.owner", "effect.demo", "demo", True)
        self.store.create_agent("Bearer " + self.owner, "agent.demo")
        _, job = self.store.submit_agent("Bearer " + self.owner,
            dict(agent_id="agent.demo", action="demo.echo", idempotency_key="test"))
        host_job = self.policy.manual_start_mock("host.local", "user.owner", "effect.demo").reason
        self.policy.cancel_queued_host_job("host.local", "user.owner", host_job)
        return [('/api/jobs/delete', dict(job_id=job['job_id'])),
            ('/api/host/jobs/delete', dict(host_id='host.local', job_id=host_job)),
            ('/api/host/effects/delete', dict(host_id='host.local', effect_id='effect.demo')),
            ('/api/agents/delete', dict(agent_id='agent.demo')),
            ('/api/hosts/delete', dict(host_id='host.local'))]

    def snapshot(self):
        with self.store._tx() as db:
            return list(db.iterdump())

    def test_success_and_repeated_requests_all_resources(self):
        for path, body in self.resources():
            with self.subTest(path=path):
                self.assertEqual(self.req(path, self.owner, body)[0], 200)
                before = self.snapshot()
                self.assertEqual(self.req(path, self.owner, body)[0], 404)
                self.assertEqual(before, self.snapshot())

    def test_unauthenticated_and_foreign_access_are_atomic(self):
        for path, body in self.resources():
            for token, expected in [(None, 401), (self.other, 403)]:
                with self.subTest(path=path, expected=expected):
                    before = self.snapshot()
                    self.assertEqual(self.req(path, token, body)[0], expected)
                    self.assertEqual(before, self.snapshot())

    def test_missing_objects_all_resources(self):
        for path, body in self.resources():
            body = {key: 'missing' for key in body}
            self.assertEqual(self.req(path, self.owner, body)[0], 404)

    def test_invalid_payloads(self):
        for path, _ in self.resources():
            for body in ([], {}, {'host_id': []}, {'host_id': 'x', 'owner_id': 'user.owner'}):
                self.assertEqual(self.req(path, self.owner, body)[0], 400)

    def test_parent_jobs_block_without_changes(self):
        resources = self.resources()
        for path, body in resources[2:]:
            before = self.snapshot()
            self.assertEqual(self.req(path, self.owner, body)[0], 409)
            self.assertEqual(before, self.snapshot())

    def test_every_non_cancelled_host_job_state_blocks(self):
        path, body = self.resources()[1]
        for state in ('queued', 'waiting', 'reserved', 'running', 'unknown'):
            with self.store._tx() as db:
                db.execute('UPDATE sec01_host_jobs SET state=?', (state,))
            before = self.snapshot()
            self.assertEqual(self.req(path, self.owner, body)[0], 409)
            self.assertEqual(before, self.snapshot())

    def test_slot_blocks_even_cancelled_job(self):
        path, body = self.resources()[1]
        with self.store._tx() as db:
            db.execute('INSERT INTO sec01_host_active_slots VALUES (?,?)', (body['job_id'], body['host_id']))
        before = self.snapshot()
        self.assertEqual(self.req(path, self.owner, body)[0], 409)
        self.assertEqual(before, self.snapshot())

    def test_orphan_slot_blocks_host_and_effect(self):
        resources = self.resources()
        for path, body in resources[:2]:
            self.req(path, self.owner, body)
        with self.store._tx() as db:
            db.execute("INSERT INTO sec01_host_active_slots VALUES ('orphan','host.local')")
        for path, body in (resources[2], resources[4]):
            self.assertEqual(self.req(path, self.owner, body)[0], 409)

    def test_grant_does_not_allow_delete_and_owner_removes_grants(self):
        self.store.create_agent('Bearer ' + self.owner, 'agent.demo')
        self.store.grant_agent('Bearer ' + self.owner, agent_id='agent.demo', grantee_user_id='user.other')
        self.claim(self.owner)
        self.policy.authority.assign_agent('agent.demo', 'host.local')
        body = dict(agent_id='agent.demo')
        self.assertEqual(self.req('/api/agents/delete', self.other, body)[0], 403)
        self.assertEqual(self.req('/api/agents/delete', self.owner, body)[0], 200)
        with self.store._tx() as db:
            for table in ('alpha_agent_grants', 'alpha_agent_host_assignments'):
                self.assertEqual(db.execute(f'SELECT count(*) FROM {table}').fetchone()[0], 0)

    def test_foreign_demo_jobs_are_never_cascaded(self):
        self.store.create_agent('Bearer ' + self.owner, 'agent.demo')
        self.store.grant_agent('Bearer ' + self.owner, agent_id='agent.demo', grantee_user_id='user.other')
        _, job = self.store.submit_agent('Bearer ' + self.other,
            dict(agent_id='agent.demo', action='demo.echo', idempotency_key='other'))
        before = self.snapshot()
        self.assertEqual(self.req('/api/agents/delete', self.owner, dict(agent_id='agent.demo'))[0], 409)
        self.assertEqual(self.req('/api/jobs/delete', self.owner, dict(job_id=job['job_id']))[0], 403)
        self.assertEqual(before, self.snapshot())

    def test_host_cascades_only_its_metadata(self):
        self.claim(self.owner)
        self.policy.claim_local_host('host.other', 'user.other')
        for host, user in [('host.local', 'user.owner'), ('host.other', 'user.other')]:
            self.policy.define_effect(host, user, 'effect.shared', 'metadata', True)
        self.assertEqual(self.req('/api/hosts/delete', self.owner, dict(host_id='host.local'))[0], 200)
        with self.store._tx() as db:
            self.assertEqual(db.execute('SELECT host_id FROM sec01_host_effect_definitions').fetchall(), [('host.other',)])

    def test_rollback_after_dependent_deletion(self):
        self.claim(self.owner)
        self.policy.define_effect('host.local', 'user.owner', 'effect.demo', 'test', True)
        with self.store._tx() as db:
            db.execute("CREATE TRIGGER fail_delete BEFORE DELETE ON alpha_executor_hosts BEGIN SELECT RAISE(ABORT, 'failure'); END")
        before = self.snapshot()
        status, data = self.req('/api/hosts/delete', self.owner, dict(host_id='host.local'))
        self.assertEqual((status, data['error']), (409, 'delete_transaction_failed'))
        self.assertEqual(before, self.snapshot())

    def test_revoked_session_rechecked_inside_transaction(self):
        self.resources()
        self.store.revoke_session('Bearer ' + self.owner)
        before = self.snapshot()
        self.assertEqual(delete_resource(self.store, 'Bearer ' + self.owner, 'agent', dict(agent_id='agent.demo'))[0], 401)
        self.assertEqual(before, self.snapshot())

    def test_admission_history_blocks_identity_removal(self):
        resources = self.resources()
        binding = json.dumps([resources[0][1]['job_id'], 'fp', 'user.owner', 'agent.demo',
                              'user.owner', 'user.owner', 'host.local', 'demo.echo'])
        with self.store._tx() as db:
            db.execute('INSERT INTO alpha_sec01_admissions VALUES (?,?)', ('effect.key', binding))
        for index in (0, 3, 4):
            before = self.snapshot()
            self.assertEqual(self.req(resources[index][0], self.owner, resources[index][1])[0], 409)
            self.assertEqual(before, self.snapshot())

    def test_b1_b2_rows_untouched_and_references_block(self):
        resources = self.resources()
        with self.store._tx() as db:
            db.execute('CREATE TABLE action_jobs(job_id TEXT, agent_id TEXT, state TEXT)')
            db.execute("INSERT INTO action_jobs VALUES ('b1.job','agent.demo','queued')")
            db.execute('CREATE TABLE action_audit(job_id TEXT, event TEXT)')
            db.execute("INSERT INTO action_audit VALUES ('b1.job','audit')")
            db.execute('CREATE TABLE grants(agent_id TEXT, spent_minor INTEGER)')
            db.execute("INSERT INTO grants VALUES ('agent.demo',123)")
            db.execute('CREATE TABLE b2_results(job_id TEXT, result TEXT)')
            db.execute("INSERT INTO b2_results VALUES ('b1.job','retained')")
        before = self.snapshot()
        self.assertEqual(self.req('/api/agents/delete', self.owner, dict(agent_id='agent.demo'))[0], 409)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.req(resources[0][0], self.owner, resources[0][1])[0], 200)
        with self.store._tx() as db:
            self.assertEqual(db.execute('SELECT spent_minor FROM grants').fetchone(), (123,))
            self.assertEqual(db.execute('SELECT result FROM b2_results').fetchone(), ('retained',))

    def test_ui_controls_unique_and_confirmation_shared(self):
        ids = re.findall(r'id="([^"]+)"', PAGE.split('<script>')[0])
        self.assertEqual(len(ids), len(set(ids)))
        for control in ('hostDelete', 'agentDelete', 'effectDelete', 'allJobDelete', 'deleteStatus', 'hostRuleDelete'):
            self.assertIn(control, ids)
        self.assertIn('async function deleteSelected(', PAGE)
        self.assertIn('if(!confirm(name+', PAGE)
        self.assertIn('await refresh();', PAGE)


if __name__ == '__main__':
    unittest.main()
