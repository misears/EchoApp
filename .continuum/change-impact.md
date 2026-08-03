---
continuum_type: change_impact
project: EchoApp
---

# Change Impact Checklist

Before deploying any change, verify:

## API Changes

- [ ] Backwards compatible? Or is a version bump needed?
- [ ] Are all consumers of this API updated?
- [ ] Is the API documentation updated?

## Database Changes

- [ ] Migration script written and tested?
- [ ] Rollback plan in place?
- [ ] Indexes added for new query patterns?

## Cross-Service Changes

- [ ] Which other services depend on this change?
- [ ] Are those services updated and deployed first?

## Observability

- [ ] Logs added for new code paths?
- [ ] Metrics/alerts updated if behaviour changes?
