# Private Alpha deletion

This is local SQLite Alpha cleanup, not a MAP protocol operation. No wire
schemas, B1 budgets, audit records, transactions or B2 execution records change.

All routes use authenticated JSON POST requests, matching the existing Alpha
management API. Session validity, ownership, dependencies and deletion are
checked in one `BEGIN IMMEDIATE` transaction. Responses: 200 deleted, 400 invalid
input, 401 invalid session, 403 unauthorized, 404 missing/already deleted,
409 dependency conflict or rolled-back database error.

| Route | Body | Authority / dependencies |
| --- | --- | --- |
| `/api/hosts/delete` | `host_id` | Owner only; no jobs, slots or protected references. Removes its effect definitions, rules, admin/owner rows and agent placements. |
| `/api/agents/delete` | `agent_id` | Owner only; no demo jobs or protected references. Removes grants and placements, never other users' jobs. |
| `/api/host/effects/delete` | `host_id`, `effect_id` | Host owner only; dependent jobs and host reservations block deletion. |
| `/api/host/jobs/delete` | `host_id`, `job_id` | Requester or host owner; must be cancelled and have no reservation or protected reference. |
| `/api/jobs/delete` | `job_id` | Requester only; isolated `demo.echo` simulation rows only. |

Execution delegation (`demo.echo`) is not management permission. The current
model has no explicit agent-management role, so only owners can delete agents.
Missing parents are not recreated and repeated requests return 404 without writes.
Existing weaker internal purge helpers have been replaced by the shared deletion
service; HTTP handlers cannot bypass its session/dependency checks.

Parents require explicit job cleanup, even for inactive jobs. This deliberately
prevents cascades into another requester's records. Historical admission bindings,
host commits and other protected identity references block cleanup. These records
must never be purged to make the delete succeed. Effect deletion conservatively
blocks on any active slot on its host because legacy slots do not reliably identify
an effect definition. B1/B2 databases outside this Alpha database are never opened.

The UI uses one confirmation/result flow for all resource types, showing the
selected ID and consequences. Successful deletion refreshes agents, demo jobs,
hosts, effects and the selected host's jobs. Selection and detail state is cleared
when the corresponding resource disappears. Database failures roll back all
dependent changes before returning a conflict response.

## Manual local acceptance

Use a disposable Alpha database, from the repository root:

```powershell
python -B server/private_alpha_admin.py --db alpha-delete-test.sqlite invite user.delete-test
python -B server/private_alpha_gateway.py --auth-db alpha-delete-test.sqlite --port 8766
```

1. Open `http://127.0.0.1:8766`, redeem the invitation in the Anmeldung tab and
   set a test password. Use the gateway console's local bootstrap code to claim
   `host.delete-test` in Hosts.
2. Create `agent.delete-test` in Agenten and an effect `effect.delete-test` in
   Effekte. Select each object and cancel its delete confirmation; it must remain.
3. Submit a demo job using that agent. Agent deletion must report a dependency
   conflict. Delete the demo job in Jobs, then delete the agent. Its selections
   and job details must disappear, while the user session remains usable.
4. Queue a host job using the effect. Direct job deletion must report that it
   needs cancellation. Effect/host deletion must report dependent jobs. Cancel
   the job, then delete it in Jobs. If reserved, release it before cancellation.
5. Delete the effect and then the host. Confirm each displayed ID and consequence.
   Inspect all four tabs: no deleted item should remain selected or in details.
6. Repeat with a second invited user. It must not see the first user's private
   objects; forged POST requests using their IDs must return 403. Repeated deletes
   by the original user return 404. Protected-history conflicts require retaining
   the resource, not deleting audit records.

## Automated checks

```powershell
python -B -m unittest discover -s tests/conformance -p 'test_private_alpha*py'
python -B -m unittest discover -s tests/conformance -p 'test_*.py'
python -B tests/conformance/validate_map_v01.py
git diff --check
```

Regression coverage includes every delete route, foreign/missing/repeated requests,
invalid bodies, active job states, orphan reservations, grants and placements,
foreign demo jobs, scoped host cascades, revoked sessions, protected history,
B1/B2-shaped records, a trigger-induced rollback after dependent deletion, and
unique visible controls sharing the confirmation flow. The full existing B1/B2
suite additionally validates its original mechanisms. UI JavaScript can be checked
with Node; browser rendering still requires the manual acceptance above.
