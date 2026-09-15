# RBAC Core Design

Date: 2026-09-15
Branch: `feature/rbac-core`
Base: `d6aee41097dde3110f9e47be6b3cc53738eb2ee9`

## 1. Purpose

The bot needs a centralized authorization subsystem that can support the
Technical Reviewer and future privileged features without scattering role
checks throughout individual cogs.

The subsystem uses Role-Based Access Control (RBAC) with:

- native Discord Owner and Administrator authority;
- application-defined RBAC roles;
- application-defined capabilities;
- role inheritance;
- Discord-role bindings;
- direct user-role assignments;
- explicit per-user capability overrides;
- append-only security audit history;
- deterministic, fail-closed authorization decisions.

The design is intentionally more general than the first Technical Reviewer
feature because authorization is expected to become shared infrastructure
across the bot.

The initial authority hierarchy is:

    OWNER
      |
      v
    ADMIN
      |
      v
    OPERATOR
      |
      v
    REVIEWER
      |
      v
    MEMBER

This hierarchy describes the default authority model. Effective authorization
is capability-based rather than being determined only by rank.

The bot does not currently have a finalized personal name. Any earlier
references such as `@HorizonBot` were illustrative only. RBAC must not encode a
specific bot name.

## 2. Scope

This design covers the complete RBAC architecture and its staged integration.

The first implementation PR, RBAC Core, is limited to:

- capability definitions and registry;
- authorization models;
- pure authorization resolver;
- inheritance evaluation and cycle protection;
- override semantics;
- persistence primitives and RBAC schema;
- audit primitives;
- cache infrastructure where required by the core;
- comprehensive unit and security tests.

Later PRs add:

1. Discord administration integration and `/access`;
2. bootstrap, repair, role binding, and administration UX;
3. the Technical Reviewer;
4. deliberate migration of existing privileged features.

Existing challenge, bounty, moderation, and other authorization behavior must
not change as a side effect of introducing RBAC Core.

## 3. Non-Goals

RBAC Core does not:

- replace Discord's guild ownership model;
- replace Discord's native Administrator permission;
- grant native Discord permissions automatically;
- migrate every existing bot command to RBAC;
- implement a general policy language;
- execute arbitrary administrator-provided policy code;
- permit administrators to invent new capability identifiers at runtime;
- implement the Technical Reviewer itself;
- give RBAC roles native Discord permissions merely because they are bound;
- use Discord role names as stable identity.

## 4. Native Authority

### 4.1 Owner

`OWNER` means the actual Discord guild owner identified by `guild.owner_id`.

It is not a Discord role named `Owner`.

The guild owner is the highest application authority and cannot be denied by
ordinary RBAC configuration.

### 4.2 Administrator

`ADMIN` means a guild member for whom Discord reports the native
`administrator` permission.

It is not dependent on a role literally named `Admin`.

Administrators bypass ordinary RBAC allow/deny resolution.

RBAC configuration cannot artificially downgrade a native Discord
Administrator.

### 4.3 Owner versus Administrator

Owner remains conceptually above Administrator. The design leaves room for a
future operation that is intentionally guild-owner-only.

Until such an operation is explicitly defined, Owner and Administrator both
bypass ordinary RBAC restrictions.

## 5. Application Roles

Initial application roles are:

- `member`
- `reviewer`
- `operator`

Their keys are stable application identifiers.

Display names may change without changing identity.

### 5.1 Member

`member` is a virtual baseline role.

Every ordinary guild member receives it automatically. No Discord role named
`Member` is required.

### 5.2 Reviewer

`reviewer` is a system RBAC role.

Default inheritance:

    reviewer -> member

### 5.3 Operator

`operator` is a system RBAC role.

Default inheritance:

    operator -> reviewer -> member

### 5.4 Custom Roles

The architecture supports future guild-scoped roles such as:

- `security-reviewer`
- `release-manager`
- `challenge-manager`
- `mentor`

Custom roles receive authority only through registered capability grants and
inheritance.

### 5.5 System Role Protection

The system keys:

- `member`
- `reviewer`
- `operator`

are reserved.

Ordinary administration commands must not destructively delete these roles.

## 6. Capabilities

Capabilities describe actions rather than ranks.

Example identifiers include:

    review.submit
    review.approve
    review.reject
    review.queue.view
    review.queue.manage

    access.view
    access.explain
    access.audit.view

Application code is the authority for which capabilities exist.

Guild administrators may distribute registered capabilities, but may not
create arbitrary new capability identifiers.

A database row by itself must never make an unknown capability valid.

### 6.1 Capability Metadata

Each capability has application-owned metadata conceptually equivalent to:

    key
    description
    grantable

`grantable=True` means it may be distributed through normal RBAC grants.

`grantable=False` means it is protected and cannot be assigned through normal
role grants or user overrides.

Security-model administration operations such as bootstrap, role-model
configuration, and override administration remain native Owner/Admin
operations and must not be obtainable by self-granting an RBAC capability.

### 6.2 Unknown Capabilities

Unknown capabilities always fail closed.

Neither a role grant nor a user override can manufacture a capability that is
not present in the application registry.

## 7. Authority Resolution

For Owner:

    allow

For Administrator:

    allow

For every other member, effective authorization is derived from:

    member baseline
    + bound Discord RBAC roles
    + direct user RBAC roles
    + inherited role capabilities
    + explicit user ALLOW overrides
    - explicit user DENY overrides

An explicit user `DENY` is evaluated last and wins over every ordinary RBAC
ALLOW source.

### 7.1 Role Grants

Role capability grants are positive-only.

A role either grants a capability or does not grant it.

Role-level DENY rules are intentionally excluded from RBAC v1 because DENY
inside an inheritance graph creates ambiguous precedence.

### 7.2 User Overrides

A user override may be:

- `ALLOW`
- `DENY`

for a registered, grantable capability.

For non-Owner/non-Admin users:

    explicit DENY > explicit ALLOW > role-derived ALLOW > absence

The practical evaluation is:

1. collect all positive role-derived grants;
2. add explicit user ALLOW overrides;
3. remove capabilities having explicit user DENY overrides.

## 8. Role Inheritance

Inheritance is additive.

If:

    A inherits B
    B inherits C
    C grants capability X

then A receives capability X.

Inheritance must remain acyclic.

These are rejected:

    A -> A

and:

    A -> B
    B -> C
    C -> A

Cycle validation occurs before persistence of a new inheritance edge.

The resolver must also defend against corrupt cyclic state by refusing unsafe
resolution rather than looping indefinitely.

## 9. Discord Role Bindings

An RBAC role is distinct from a Discord role.

A binding means:

    Discord role ID -> RBAC role

The binding establishes an identity source only.

It does not alter the Discord role's native permission bitset.

Role IDs, never role names, are the stable binding identity.

A single RBAC role may eventually be backed by multiple Discord roles.

One particular Discord role may map to only one RBAC role within the same
guild unless a later approved design explicitly changes that rule.

The database therefore enforces uniqueness of:

    (guild_id, discord_role_id)

## 10. Direct User-Role Assignments

RBAC supports assigning an application role directly to a member without
requiring a visible Discord role.

Conceptually:

    guild_id
    user_id
    rbac_role_id

A direct assignment and a Discord-role-derived assignment have identical
meaning once they enter the resolver.

Discord-role bindings remain the preferred normal mechanism because they are
visible to guild administrators.

## 11. Persistence Model

The persistence model is guild-scoped.

### 11.1 `rbac_roles`

Fields:

    id
    guild_id
    key
    display_name
    is_system
    priority
    created_by
    created_at
    updated_at

Constraints:

    UNIQUE(guild_id, key)
    UNIQUE(guild_id, id)

`priority` is for ordering and presentation. It does not independently grant
authority.

### 11.2 `rbac_capabilities`

Fields:

    key
    description
    grantable

This table is a persisted mirror/catalog of application capability metadata.

Application code remains authoritative. A database row not known to the code
registry must still be rejected.

At startup or an explicit synchronization point, known application
capabilities may be upserted into this catalog. Database-only capability rows
that are unknown to the application registry remain invalid for authorization,
are ignored by the resolver, and are surfaced diagnostically. They are not
silently trusted or automatically deleted.

### 11.3 `rbac_role_capabilities`

Fields:

    role_id
    capability_key
    created_by
    created_at

Constraint:

    PRIMARY KEY(role_id, capability_key)

Role grants are ALLOW-only.

### 11.4 `rbac_role_inheritance`

Fields:

    guild_id
    role_id
    parent_role_id
    created_by
    created_at

Meaning:

    role_id inherits parent_role_id

Database integrity must enforce that both `role_id` and `parent_role_id`
belong to `guild_id`, using composite foreign-key constraints against
`rbac_roles(guild_id, id)`.

Direct and transitive cycles are forbidden.

### 11.5 `rbac_discord_role_bindings`

Fields:

    guild_id
    discord_role_id
    rbac_role_id
    created_by
    created_at

Constraints:

    UNIQUE(guild_id, discord_role_id)

`(guild_id, rbac_role_id)` must reference
`rbac_roles(guild_id, id)` so a Discord-role binding cannot point at an RBAC
role owned by a different guild.

### 11.6 `rbac_user_roles`

Fields:

    guild_id
    user_id
    rbac_role_id
    assigned_by
    created_at

`(guild_id, rbac_role_id)` must reference
`rbac_roles(guild_id, id)` so a direct assignment cannot reference an RBAC
role owned by another guild.

A user may hold multiple direct RBAC roles.

### 11.7 `rbac_user_overrides`

Fields:

    guild_id
    user_id
    capability_key
    effect
    created_by
    reason
    created_at
    updated_at

`effect` is:

    ALLOW
    DENY

Constraint:

    UNIQUE(guild_id, user_id, capability_key)

### 11.8 `rbac_audit_log`

Fields:

    id
    guild_id
    actor_user_id
    action
    target_type
    target_id
    capability_key
    old_value
    new_value
    reason
    created_at

Audit history is append-only at the application boundary.

The implementation should additionally enforce immutability at the PostgreSQL
layer so ordinary application operations cannot UPDATE or DELETE audit rows.

## 12. Audit Events

Expected audit actions include:

    ROLE_CREATED
    ROLE_DELETED
    ROLE_BOUND
    ROLE_UNBOUND

    CAPABILITY_GRANTED
    CAPABILITY_REVOKED

    INHERITANCE_ADDED
    INHERITANCE_REMOVED

    USER_ROLE_ASSIGNED
    USER_ROLE_REMOVED

    OVERRIDE_ALLOWED
    OVERRIDE_DENIED
    OVERRIDE_CLEARED

    BOOTSTRAP_COMPLETED
    REPAIR_COMPLETED

Security-state changes must record:

- guild;
- actor;
- action;
- affected target;
- relevant capability where applicable;
- old and new values where meaningful;
- timestamp.

There is no ordinary `/access audit delete` operation.

## 13. Atomicity

Where a database operation changes RBAC state and produces an audit event, the
state change and audit append must commit atomically.

The implementation must not emulate this guarantee with unrelated sequential
client writes if that permits one write to succeed while the other fails.

The PostgreSQL layer should provide the transaction boundary, for example
through an appropriate database function/RPC or equivalent transactional
repository operation.

Discord API operations and PostgreSQL cannot share one distributed
transaction, so Discord-side bootstrap operations use explicit compensation
and partial-failure reporting.

## 14. Bootstrap

A fresh guild may run:

    /access bootstrap

Only native Owner/Admin authority may invoke it.

Preconditions include:

- guild context;
- native Owner/Admin caller;
- RBAC persistence available;
- bot has required Discord role-management permissions;
- bot's own Discord role is high enough to manage roles it creates;
- guild is not already successfully bootstrapped.

Bootstrap creates:

- virtual `member` system RBAC role;
- `reviewer` system RBAC role;
- `operator` system RBAC role;
- default inheritance;
- Discord Reviewer role;
- Discord Operator role;
- bindings between created Discord role IDs and RBAC roles;
- required initial capability grants;
- audit history.

Automatically created Operator and Reviewer Discord roles receive no dangerous
native Discord permissions merely because of their RBAC meaning.

The expected physical Discord ordering is:

    <bot-managed Discord role>
    Operator
    Reviewer
    ordinary member roles

The finalized bot name is irrelevant to this ordering.

## 15. Bootstrap Idempotency

Bootstrap is idempotent.

A second successful invocation must not create duplicate:

- RBAC roles;
- Discord roles;
- bindings;
- inheritance edges;
- grants.

If a stored configuration exists but is damaged, bootstrap must not silently
guess or recreate authority.

Damaged state is handled by explicit repair.

## 16. Bootstrap Failure Compensation

Bootstrap crosses Discord and PostgreSQL, so the operation uses this ordering:

    preflight
        |
        v
    create and position Discord roles
        |
        v
    one PostgreSQL transaction:
        RBAC roles
        inheritance
        bindings
        grants
        audit
        |
        v
    transaction succeeds?
        |
        +-- no  -> compensate Discord roles created by this invocation
        |
        +-- yes -> verify required postconditions
                       |
                       +-- pass -> SUCCESS
                       |
                       +-- fail -> PARTIAL_FAILURE and explicit repair

If the bot process terminates or compensation fails after Discord role
creation, a later bootstrap must not adopt an existing Discord role merely
because its name is `Operator` or `Reviewer`. Such orphaned or inconsistent
state is diagnosed explicitly by `/access repair`.

Example failure:

    create Operator Discord role       success
    create Reviewer Discord role       success
    persist RBAC state                 failure

The implementation attempts to delete only the Discord roles created by that
invocation.

Possible outcomes are:

    SUCCESS
    CLEAN_FAILURE
    PARTIAL_FAILURE

`PARTIAL_FAILURE` must report enough identifiers for an administrator to
understand the remaining state.

The bot must never report bootstrap success unless all required postconditions
are satisfied.

## 17. Repair

`/access repair` is conservative and diagnostic-first.

It first evaluates:

- system RBAC roles;
- Discord bindings;
- existence of bound Discord roles;
- required inheritance;
- capability registry consistency;
- persistence health.

It reports the detected problem before destructive or authority-changing
repair.

Repair does not mean reset.

It must not silently erase the guild's RBAC configuration.

## 18. Administration Surface

The planned command family is:

    /access bootstrap
    /access repair
    /access status

    /access role create
    /access role delete
    /access role bind
    /access role unbind

    /access grant
    /access revoke

    /access inherit
    /access uninherit

    /access user-role add
    /access user-role remove

    /access override allow
    /access override deny
    /access override clear

    /access me
    /access explain
    /access audit

Not every command must land in the same pull request.

### 18.1 Protected Mutations

The following security-model mutations are native Owner/Admin operations:

- bootstrap;
- repair;
- role creation/deletion;
- Discord-role binding/unbinding;
- capability grant/revoke;
- inheritance mutation;
- direct user-role mutation;
- user override mutation.

An Operator or Reviewer cannot obtain these administrative powers by granting
themselves an RBAC capability.

### 18.2 Inspection

A member may inspect their own effective authorization with `/access me`.

Inspection of another member or security audit history may be governed by
registered inspection capabilities such as:

    access.explain
    access.audit.view

## 19. Role Deletion

Custom RBAC roles may be deleted only when no dependent state remains.

Deletion fails rather than silently cascading if the role still has:

- member assignments;
- Discord-role bindings;
- capability grants;
- inheritance relationships.

The administrator must remove dependencies explicitly first.

System roles are protected from ordinary deletion.

## 20. Runtime Architecture

Cogs do not query RBAC tables directly.

They call a central authorization boundary.

Conceptual public API:

    resolve_authorization(subject)
    can(subject, capability)
    require(subject, capability)

Discord command integration may expose:

    @requires_capability(...)

The Technical Reviewer and later features depend on this API rather than
checking role names themselves.

## 21. Authorization Subject

Discord-specific state is translated into a small authorization subject:

    guild_id
    user_id
    is_owner
    is_admin
    discord_role_ids

The pure resolver operates on this representation rather than on complex
Discord objects.

This keeps the policy engine independently testable.

## 22. Authorization Decision

The resolver returns a structured decision rather than only a Boolean.

Representative reasons include:

    ALLOWED_OWNER
    ALLOWED_ADMIN
    ALLOWED_CAPABILITY

    DENIED_EXPLICIT
    DENIED_MISSING_CAPABILITY
    DENIED_UNKNOWN_CAPABILITY
    DENIED_PROTECTED_CAPABILITY
    DENIED_RBAC_UNAVAILABLE

The exact reason is available for diagnostics and logs.

User-facing responses may translate these reasons into safer, friendlier
messages.

## 23. Runtime Failure Policy

For Owner/Admin, native authority can be established without RBAC storage.

For everyone else, when RBAC-derived privilege cannot be established because
persistence is unavailable or state is invalid:

    fail closed

Operational failure is distinguished from ordinary missing permission.

For example:

    authorization identity: valid Admin
    requested database-backed mutation: cannot execute because persistence is unavailable

must not be presented as though the caller lacked permission.

## 24. Current Authorization at Action Time

Authority is evaluated when the action executes.

Persistent Discord buttons or queued workflow objects must not cache a
historical verdict such as:

    user_was_reviewer = true

When a member clicks an approval button, the bot resolves their current
authorization again.

Removing a Reviewer role before the click therefore removes review authority
for that click.

## 25. Caching

The system may cache guild RBAC configuration snapshots.

It must not cache permanent per-user authorization verdicts.

Cached state may contain:

- RBAC roles;
- bindings;
- grants;
- inheritance;
- overrides.

Discord role membership itself is read from the current `discord.Member`
state when an action occurs.

Successful RBAC mutations immediately invalidate the affected guild's cache.

Other guild caches remain unaffected.

Mutation-driven invalidation is the primary freshness mechanism. A short,
finite TTL is also used as a secondary safeguard, but its concrete duration is
an implementation or configuration decision rather than part of this design
contract.

External direct database edits are not a supported administration path, but
the finite TTL prevents indefinitely stale in-process configuration if they
occur.

## 26. Per-Guild Mutation Serialization

RBAC configuration mutations are serialized per guild within the bot process.

Guild A and Guild B may mutate independently.

Two simultaneous mutations for the same guild must not race through bootstrap
or configuration changes.

Database constraints remain the final integrity guard across processes.

## 27. Runtime Logging versus Audit History

Permanent RBAC audit history records security-state mutation.

Normal runtime security logging records events such as:

- denied authorization attempt;
- RBAC persistence unavailable;
- unknown capability requested by application code;
- corrupt resolver state.

Ordinary permission checks do not flood the permanent audit table.

## 28. Security Invariants

The implementation must preserve the following invariants.

### RBAC-01

Guild Owner always has ultimate bot authority.

### RBAC-02

Native Discord Administrator bypasses ordinary RBAC restrictions.

### RBAC-03

A normal member receives only authority proven through valid baseline roles,
bindings, direct assignments, inheritance, and registered overrides.

### RBAC-04

Explicit user DENY wins for every non-Owner/non-Admin user.

### RBAC-05

Unknown capabilities fail closed.

### RBAC-06

Unavailable or invalid RBAC state fails closed for RBAC-derived privilege.

### RBAC-07

Role inheritance remains acyclic.

### RBAC-08

Protected/non-grantable capabilities cannot be obtained by ordinary grants or
user overrides.

### RBAC-09

Successful RBAC mutation invalidates the affected guild cache.

### RBAC-10

Authorization is reevaluated at action time.

### RBAC-11

Discord-role bindings use Discord role IDs rather than role names.

### RBAC-12

RBAC role bindings never implicitly alter Discord-native permissions.

### RBAC-13

Database security mutations and their audit events are atomic where PostgreSQL
provides the transaction boundary.

### RBAC-14

Bootstrap is idempotent.

### RBAC-15

Failed or partial bootstrap is never reported as successful.

### RBAC-16

System RBAC roles cannot be destructively removed through ordinary role
administration.

## 29. Test Strategy

The majority of RBAC verification is fast and independent of a live Discord
server or live Supabase project.

Planned test organization:

    tests/auth/test_capabilities.py
    tests/auth/test_resolver.py
    tests/auth/test_inheritance.py
    tests/auth/test_overrides.py
    tests/auth/test_discord_adapter.py
    tests/auth/test_repository.py
    tests/auth/test_security.py
    tests/test_access.py

PR scope determines which files are introduced at each stage.

## 30. Resolver Test Matrix

At minimum, tests cover:

    Owner + no grant + DENY override        -> ALLOW
    Admin + no grant + DENY override        -> ALLOW
    Member + no grant                       -> DENY
    Member + baseline grant                 -> ALLOW
    Reviewer + inherited grant              -> ALLOW
    Operator + Reviewer inheritance         -> ALLOW
    Operator + inherited grant + DENY       -> DENY
    Member + registered ALLOW override      -> ALLOW
    Member + unknown capability override    -> DENY/reject

User overrides cannot manufacture unregistered or protected capabilities.

## 31. Inheritance Tests

Tests prove:

    reviewer -> member                        valid
    operator -> reviewer -> member            valid
    A -> A                                    rejected
    A -> B -> C -> A                          rejected

Transitive capabilities resolve exactly once and traversal terminates safely.

## 32. Privilege-Escalation Tests

Security tests explicitly verify that:

- Reviewer cannot grant itself Operator;
- Operator cannot modify its own inheritance;
- Operator cannot bind itself to stronger authority;
- Operator cannot clear a restrictive user DENY;
- Reviewer cannot grant itself protected access-management authority;
- non-Admin users cannot invoke security-model mutation endpoints;
- unknown capability keys are rejected;
- cross-guild roles or assignments never leak authority.

## 33. Guild Isolation

Every guild-scoped query and resolver input must preserve guild isolation.

A role, binding, assignment, override, or grant in Guild A must never affect
Guild B.

Guild isolation receives explicit regression tests.

## 34. Discord Adapter Tests

The Discord adapter tests prove that:

    actual guild owner
        -> is_owner true

    native Discord Administrator
        -> is_admin true

    member has bound Discord role ID
        -> binding participates in RBAC

    same role name with different Discord ID
        -> no identity match

## 35. Persistence Tests

Persistence tests cover:

- role creation;
- registered capability grants;
- inheritance storage;
- Discord bindings;
- direct user roles;
- user overrides;
- audit insertion;
- audit immutability;
- guild isolation;
- uniqueness constraints;
- protected/system state.

## 36. Cache Tests

Tests prove:

1. Guild A configuration loads.
2. Alice is authorized from that state.
3. Guild A mutates.
4. Guild A cache invalidates.
5. Alice is resolved again.
6. New authorization is observed.
7. Guild B cache remains untouched.

## 37. Bootstrap Qualification

Successful bootstrap postconditions include:

- `member` system RBAC role exists;
- `reviewer` system RBAC role exists;
- `operator` system RBAC role exists;
- Reviewer inherits Member;
- Operator inherits Reviewer;
- Discord Reviewer role exists;
- Discord Operator role exists;
- bindings use the created role IDs;
- required grants exist;
- audit record exists;
- second bootstrap creates nothing additional.

Failure injection covers:

- Operator role creation failure;
- Reviewer role creation failure;
- persistence failure;
- audit transaction failure;
- compensation failure;
- missing Manage Roles permission;
- bot Discord role positioned too low.

Results distinguish:

    SUCCESS
    CLEAN_FAILURE
    PARTIAL_FAILURE

## 38. TDD Requirement

Production implementation follows RED -> GREEN -> REFACTOR.

For each behavior:

1. write the smallest meaningful failing test;
2. run it and verify the expected failure;
3. implement the minimum production behavior;
4. run the focused test until green;
5. run the relevant wider suite;
6. refactor only while tests remain green.

Security behavior must not be implemented first and tested afterward.

## 39. Existing Bot Behavior

Introducing RBAC does not automatically rewrite existing authorization.

Existing challenge, bounty, moderation, and other commands retain their current
checks until a separate migration is designed, tested, and reviewed.

The first consumers are:

1. `/access`;
2. Technical Reviewer.

Older features may later migrate one bounded subsystem at a time.

## 40. Staged Delivery

### PR 8 - RBAC Core

Contains:

- capability registry;
- models;
- pure resolver;
- inheritance;
- overrides;
- persistence schema/primitives;
- audit primitives;
- caching required by the core;
- core/security tests.

It does not alter existing command authorization behavior.

### PR 9 - Discord RBAC Integration

Contains:

- Discord adapter integration;
- `/access`;
- bootstrap;
- repair;
- status and inspection;
- Discord-role bindings;
- administrative mutation UX;
- persistent audit UX.

### PR 10 - Technical Reviewer

Contains:

- `/review` pasted-code input;
- message-context review input;
- TXT/ZIP human approval workflow;
- Reviewer/Operator authorization through RBAC;
- archive and text-input security validation;
- structured technical review output.

### Later PRs

May migrate:

- challenge administration;
- bounty administration;
- other privileged bot workflows.

Each migration is independently scoped and tested.

## 41. Technical Reviewer RBAC Expectations

The later Technical Reviewer uses capabilities rather than checking role names.

Initial intended capability relationship:

    MEMBER
      review.submit

    REVIEWER
      inherits MEMBER
      review.approve
      review.reject
      review.queue.view

    OPERATOR
      inherits REVIEWER
      review.queue.manage

Human approval does not replace technical validation.

TXT and ZIP review submissions remain subject to security controls after human
approval.

ZIP validation will include, at minimum:

- ZIP-slip/path traversal protection;
- compressed and extracted size limits;
- file-count limits;
- rejection of nested archives;
- rejection of executable/binary material;
- an allowlist of supported source/text content.

Direct source-file attachments such as `.js`, `.c`, `.py`, and similar formats
are outside the first reviewer attachment policy.

## 42. Acceptance Gate for RBAC Core

RBAC Core is not ready for review until:

- all pre-existing repository tests pass;
- all new RBAC tests pass;
- no unrelated production feature changes behavior;
- unknown capabilities fail closed;
- explicit DENY precedence is proven;
- Owner/Admin precedence is proven;
- cyclic inheritance is rejected;
- cross-guild isolation is proven;
- protected capabilities cannot be granted;
- persistence invariants are verified;
- audit behavior is verified;
- tracked changes match the approved PR scope.

## 43. Design Principles

The implementation should optimize for:

- least privilege;
- separation of duties;
- deterministic policy evaluation;
- explicit authority boundaries;
- guild isolation;
- inspectability;
- auditability;
- fail-closed security behavior;
- small, independently testable components;
- compatibility with existing Discord-native authority;
- staged adoption rather than a repository-wide authorization rewrite.

The public authorization API should remain substantially simpler than the
internal persistence model.

A feature author should be able to ask:

    "May this member perform capability X?"

without knowing how RBAC roles, inheritance, bindings, caching, or persistence
are implemented.


## 44. Team-Owned Database Authorization Boundary

RBAC development does not require access to the team's live Supabase project.

Development may proceed without production credentials for:

- architecture and schema design;
- SQL or migration-file development;
- pure authorization logic;
- repository interfaces;
- mocks and fakes;
- unit and security tests;
- review of repository-managed database contracts.

Any operation against a team-owned live Supabase environment requires explicit
maintainer authorization and verification of the intended target environment
before execution.

This includes:

- creating or altering live tables;
- creating live functions, triggers, or policies;
- applying migrations;
- running tests that mutate team-owned database state;
- using production or privileged Supabase credentials.

A development or staging Supabase environment is preferred for integration
qualification before production application.

Credentials such as Supabase keys, service-role keys, database passwords, or
connection URIs must never be committed to Git, included in pull requests, or
posted in public/team chat.

The RBAC Core design and implementation must remain testable without requiring
production database credentials.
