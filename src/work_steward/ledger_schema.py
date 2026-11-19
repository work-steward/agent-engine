"""Engine storage, separate from the provider database."""

APPLICATION_ID = 0x57534C44  # WSLD
SCHEMA_VERSION = 2

SCHEMA = (
    """CREATE TABLE ledger_meta (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), organization_id TEXT NOT NULL,
        mode TEXT NOT NULL CHECK(mode IN ('reference','governed'))
    ) STRICT""",
    """CREATE TABLE operations (
        operation_id TEXT PRIMARY KEY, intent BLOB NOT NULL, intent_digest TEXT NOT NULL,
        account TEXT NOT NULL, provider_key TEXT NOT NULL,
        idempotency TEXT NOT NULL CHECK(idempotency IN ('none','permanent','finite')),
        supported_consistency BLOB NOT NULL, max_attempts INTEGER NOT NULL
            CHECK(max_attempts BETWEEN 1 AND 64),
        UNIQUE(account,provider_key)
    ) STRICT""",
    """CREATE TABLE reservations (
        namespace TEXT NOT NULL, business_key TEXT NOT NULL,
        operation_id TEXT NOT NULL UNIQUE REFERENCES operations(operation_id),
        PRIMARY KEY(namespace,business_key)
    ) STRICT""",
    """CREATE TABLE action_state (
        operation_id TEXT PRIMARY KEY REFERENCES operations(operation_id),
        version INTEGER NOT NULL CHECK(version>=0),
        generation INTEGER NOT NULL CHECK(generation>=0),
        authorized INTEGER NOT NULL CHECK(authorized IN (0,1)),
        evidence_valid INTEGER NOT NULL CHECK(evidence_valid IN (0,1)),
        disposition TEXT NOT NULL CHECK(disposition IN
            ('proposed','blocked','eligible','attempt_admitted','paused','closed')),
        effect TEXT NOT NULL CHECK(effect IN
            ('not_attempted','unknown','pending','no_effect_confirmed','effect_confirmed','conflicting')),
        reconciliation TEXT NOT NULL CHECK(reconciliation IN
            ('idle','scheduled','investigating','awaiting_human'))
    ) STRICT""",
    """CREATE TABLE attempts (
        operation_id TEXT NOT NULL REFERENCES operations(operation_id),
        ordinal INTEGER NOT NULL CHECK(ordinal>=0), attempt_id TEXT NOT NULL,
        generation INTEGER NOT NULL CHECK(generation>=0), repetition_covered BLOB NOT NULL,
        phase TEXT NOT NULL CHECK(phase IN ('admitted','closed_without_send','send_possible')),
        assessment TEXT NOT NULL CHECK(assessment IN
            ('not_attempted','unknown','pending','no_effect_confirmed','effect_confirmed','conflicting')),
        CHECK((phase='send_possible') = (assessment!='not_attempted')),
        PRIMARY KEY(operation_id,attempt_id), UNIQUE(operation_id,ordinal)
    ) STRICT""",
    """CREATE TABLE observations (
        operation_id TEXT NOT NULL, ordinal INTEGER NOT NULL CHECK(ordinal>=0),
        observation_id TEXT NOT NULL, attempt_id TEXT NOT NULL, intent_digest TEXT NOT NULL,
        assessment TEXT NOT NULL CHECK(assessment IN
            ('unknown','pending','no_effect_confirmed','effect_confirmed','conflicting')),
        provider_effect_id TEXT,
        PRIMARY KEY(operation_id,ordinal),
        FOREIGN KEY(operation_id,attempt_id) REFERENCES attempts(operation_id,attempt_id)
    ) STRICT""",
    """CREATE TABLE journal (
        sequence INTEGER PRIMARY KEY,
        operation_id TEXT NOT NULL REFERENCES operations(operation_id),
        command TEXT NOT NULL, previous_version INTEGER, version INTEGER NOT NULL CHECK(version>=0),
        generation INTEGER NOT NULL, disposition TEXT NOT NULL, effect TEXT NOT NULL,
        reconciliation TEXT NOT NULL, data BLOB NOT NULL, UNIQUE(operation_id,version)
    ) STRICT""",
    """CREATE TRIGGER immutable_attempt_binding BEFORE UPDATE ON attempts
        WHEN NEW.operation_id IS NOT OLD.operation_id OR NEW.ordinal IS NOT OLD.ordinal
          OR NEW.attempt_id IS NOT OLD.attempt_id OR NEW.generation IS NOT OLD.generation
          OR NEW.repetition_covered IS NOT OLD.repetition_covered
          OR (OLD.phase!='admitted' AND NEW.phase IS NOT OLD.phase)
        BEGIN SELECT RAISE(ABORT,'immutable attempt binding'); END""",
    """CREATE TRIGGER advancing_state BEFORE UPDATE ON action_state
        WHEN NEW.operation_id IS NOT OLD.operation_id OR NEW.version<=OLD.version
          OR NEW.generation<OLD.generation
        BEGIN SELECT RAISE(ABORT,'non-advancing state'); END""",
    """CREATE TRIGGER retain_attempts BEFORE DELETE ON attempts
        BEGIN SELECT RAISE(ABORT,'retained attempts'); END""",
    """CREATE TRIGGER retain_state BEFORE DELETE ON action_state
        BEGIN SELECT RAISE(ABORT,'retained state'); END""",
)

# Fixed identifiers; triggers guard accidental edits, not a privileged database editor.
IMMUTABLE_TABLES = ("ledger_meta", "operations", "reservations", "observations", "journal")

AUTHORITY_SCHEMA = (
    """CREATE TABLE authority_config (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), administrators BLOB NOT NULL,
        last_tick INTEGER NOT NULL CHECK(last_tick>=0)
    ) STRICT""",
    """CREATE TABLE policies (
        revision INTEGER PRIMARY KEY CHECK(revision>0), value BLOB NOT NULL,
        actor TEXT NOT NULL, at INTEGER NOT NULL CHECK(at>=0)
    ) STRICT""",
    """CREATE TABLE approvals (
        sequence INTEGER PRIMARY KEY, approval_id TEXT NOT NULL UNIQUE,
        operation_id TEXT NOT NULL REFERENCES operations(operation_id), intent_digest TEXT NOT NULL,
        policy_revision INTEGER NOT NULL REFERENCES policies(revision), actor TEXT NOT NULL,
        issued_at INTEGER NOT NULL, expires_at INTEGER NOT NULL CHECK(expires_at>issued_at)
    ) STRICT""",
    """CREATE TABLE revocations (
        approval_id TEXT PRIMARY KEY REFERENCES approvals(approval_id), actor TEXT NOT NULL,
        reason TEXT NOT NULL, at INTEGER NOT NULL CHECK(at>=0)
    ) STRICT""",
    "CREATE INDEX approvals_operation ON approvals(operation_id,sequence DESC)",
    """CREATE TABLE evidence (
        sequence INTEGER PRIMARY KEY, account TEXT NOT NULL, capability TEXT NOT NULL,
        subject TEXT NOT NULL, predicate TEXT NOT NULL,
        material_version TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0),
        expires_at INTEGER NOT NULL, actor TEXT NOT NULL, at INTEGER NOT NULL,
        UNIQUE(account,capability,subject,predicate,revision), CHECK(expires_at>at)
    ) STRICT""",
    """CREATE TABLE authority_denials (
        sequence INTEGER PRIMARY KEY, at INTEGER NOT NULL CHECK(at>=0), reason TEXT NOT NULL
    ) STRICT""",
    """CREATE TRIGGER retain_authority_admins BEFORE UPDATE ON authority_config
        WHEN NEW.singleton IS NOT OLD.singleton OR NEW.administrators IS NOT OLD.administrators
          OR NEW.last_tick<OLD.last_tick
        BEGIN SELECT RAISE(ABORT,'immutable authority configuration'); END""",
    """CREATE TRIGGER retain_authority_config BEFORE DELETE ON authority_config
        BEGIN SELECT RAISE(ABORT,'retained authority configuration'); END""",
)

AUTHORITY_IMMUTABLE = ("policies", "approvals", "revocations", "evidence", "authority_denials")
