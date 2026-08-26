# Stage 5 acceptance matrix

| # | Scenario | Coverage |
|---:|---|---|
| 1 | Active trial provision | `test_vpn_acceptance.py::test_active_trial_can_provision` |
| 2 | Expired trial denied | `test_expired_trial_cannot_provision` |
| 3 | Suspended user denied | `test_suspended_user_cannot_provision` |
| 4 | Offline rejected | `test_unavailable_server_rejected` |
| 5 | Maintenance rejected | `test_unavailable_server_rejected` |
| 6 | Invalid WG key | `test_invalid_public_key_rejected` |
| 7 | Valid credential | `test_active_trial_can_provision` |
| 8 | Unique IP | `test_real_postgres_concurrent_ip_allocation` |
| 9 | Concurrent allocation | `test_real_postgres_concurrent_ip_allocation` |
| 10 | Capacity exhaustion | `test_capacity_exhaustion` |
| 11 | Provision idempotency | `test_provision_is_idempotent` |
| 12 | Revoke ownership | `test_user_cannot_revoke_another_users_credential` |
| 13 | Revoke idempotency | `test_revoke_is_idempotent` |
| 14 | Provision failure rollback | `test_node_failure_rolls_back` |
| 15 | Token/secret privacy | `test_public_response_has_no_secrets` |
| 16 | No private key response | `test_public_response_has_no_secrets` |
| 17 | No server private key persistence | `test_server_model_has_no_private_key` |
| 18 | Injection rejection | `test_node_agent_rejects_injection` |
| 19 | Agent operation allow-list | `test_node_agent_rejects_injection` |
| 20 | Stage 1–4 regression | full existing suite (`39 tests`) |

Reconciliation A–E are covered by `test_revoke_reachable_node_clears_pending`, `test_revoke_unavailable_node_sets_pending`, `test_successful_reconciliation_clears_pending`, `test_failed_reconciliation_keeps_pending`, and `test_reconciliation_is_idempotent` in `test_vpn_acceptance.py`.
