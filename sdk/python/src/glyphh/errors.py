"""Ada's refusals, typed: every one an `AdaError` with the server's `code`, `message`, HTTP `status` and `detail` (the
rest of the refusal's body: `reason`, `used`, `max`, `plan`, `limit`, `path`, `job`, `trace_id`, ...). Branch on the
class or on `code`; a code the SDK does not know is a plain `AdaError`."""

from __future__ import annotations

from typing import Any, Dict, Optional, Type


class AdaError(Exception):
    """Ada refused, or could not be reached. `code` is the server's (E_AUTH, E_LIMIT, E_MODEL_MISSING, E_SPEC, ...),
    or E_UNREACHABLE / E_CONFIG from the SDK itself; `status` is the HTTP status, 0 when there was none."""

    def __init__(
        self,
        code: str,
        message: str,
        status: int = 0,
        detail: Optional[Dict[str, Any]] = None,
        retry_after: Optional[float] = None,
    ) -> None:
        super().__init__(message)
        self.code, self.message, self.status = code, message, status
        self.detail = detail or {}
        self.retry_after = retry_after  # seconds, when the server said when to ask again

    @property
    def trace_id(self) -> Optional[str]:
        """Quote it to support."""
        return self.detail.get("trace_id")

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.code!r}, {self.message!r}, status={self.status})"


class AuthError(AdaError):
    """E_AUTH (401): no key, or not a live API key. Make one on the platform's API Keys page (or ask Claude, through
    the Glyphh connector) and set GLYPHH_API_KEY."""


class LimitError(AdaError):
    """E_LIMIT (403): the plan's limit is reached. `reason` names it: `requests` (the month's reads are used on a plan
    that is not metered, Free: `plan`, the plan to `upgrade` to, None when only a contract reads more, and `resets_at`,
    YYYY-MM-DD, when they start again), `precedents` (a write past the plan's precedents: `adding`), or `cases` (413,
    record_many past 1,000). `used` and `max` say where the org stands."""

    @property
    def reason(self) -> Optional[str]:
        return self.detail.get("reason")

    @property
    def used(self) -> Optional[int]:
        return self.detail.get("used")

    @property
    def max(self) -> Optional[int]:
        return self.detail.get("max")

    @property
    def plan(self) -> Optional[str]:
        return self.detail.get("plan")

    @property
    def upgrade(self) -> Optional[str]:
        """The self-serve plan that reads more (Billing on the platform, or the connector's upgrade tool); None: talk
        to sales@glyphh.ai."""
        return self.detail.get("upgrade")

    @property
    def resets_at(self) -> Optional[str]:
        """When the month's requests start again, YYYY-MM-DD (UTC)."""
        return self.detail.get("resets_at")


class RateError(AdaError):
    """E_RATE (429): more calls a second than the plan allows (Free 5, Pro 50, Team 200), the org's together. The client
    waits `retry_after` seconds (the Retry-After header, else the body's `retry_after`) and asks again while its
    deadline allows; raised after that. `max` is the plan's calls a second."""

    @property
    def max(self) -> Optional[int]:
        return self.detail.get("max")


class InvalidError(AdaError):
    """E_INVALID: the request is not valid (`detail["problems"]` names each), or a string holds NUL."""


class TooLargeError(AdaError):
    """E_TOO_LARGE (413): a body over its bound (1 MB; record_many and a file in an import's body 5 MB)."""


class ModelMissingError(AdaError):
    """E_MODEL_MISSING (404): no model of that name in the key's org."""


class JobMissingError(AdaError):
    """E_JOB_MISSING (404): no job of that id in the key's org."""


class PrecedentMissingError(AdaError):
    """E_PRECEDENT_MISSING (404): no precedent of that id (grade, forget)."""


class VersionMissingError(AdaError):
    """E_VERSION_MISSING (404): the model has no such version."""


class SpecError(AdaError):
    """E_SPEC (422): the kernel refused the spec, or data that does not fit it; `detail["path"]` says where."""

    @property
    def path(self) -> Optional[str]:
        return self.detail.get("path")


class SpecLimitError(SpecError):
    """E_SPEC_LIMIT: past a cloud bound on a spec (64 KB of JSON; `limit` names the bound, `max` its value)."""


class SpecReadingError(SpecError):
    """E_SPEC_READING (422): the new spec reads a role's values differently (`numeric_config`, `text_encoding`,
    `key_part`). The stored cases cannot be read again another way: make a new model and import into it."""


class FewRolesError(AdaError):
    """E_FEW_ROLES (422): a model over 100,000 precedents asked with under half its voting roles, which a shortlist
    answers badly. Give more of the roles (the detail names those given and those it could)."""


class MappingError(AdaError):
    """E_MAPPING (422): an import's CSV header the spec cannot take (`column`, `target`)."""


class ImportRefusedError(AdaError):
    """E_IMPORT (422): the import's file is not what its format says (an SQLite store of another dimension, ...)."""


class BacktestError(AdaError):
    """E_BACKTEST (422): nothing to hold out (no graded precedents for the output)."""


class BusyError(AdaError):
    """E_BUSY (409): an import or re-encode is open on the model (`detail["job"]`): wait for it to end."""


class NotReadyError(AdaError):
    """E_NOT_READY (409): that version is still being made: wait for its job."""


class NoChangeError(AdaError):
    """E_NO_CHANGE (409): the spec or settings are the active version's already."""


class IdempotencyError(AdaError):
    """E_IDEMPOTENCY (409): this Idempotency-Key was sent before with another body."""


class ConflictError(AdaError):
    """E_CONFLICT (409): e.g. deleting a model without confirming its name, or an upload link already used."""


class VersionGoneError(AdaError):
    """E_VERSION_GONE (410): the version's store was dropped (7 days after it stopped being read)."""


class ExpiredError(AdaError):
    """E_EXPIRED: an import whose file never came while its upload link worked (an hour)."""


class AdaTimeoutError(AdaError):
    """E_TIMEOUT (504): no answer in time (10 s a read, 30 s a big write). A read is sent again by the client; a write
    with the same Idempotency-Key (the SDK sends one) is made once even if it landed."""


class UnavailableError(AdaError):
    """E_UNAVAILABLE (503): Ada is unreachable for a moment; retried while the deadline allows."""


class JobFailedError(AdaError):
    """A job ended `failed`: `code` and `message` are its error's; `detail["job"]` is the job."""


# Ada versions (contract 5): every model version runs one Ada version, chosen by name (ada-1-0, ada-1-1-beta)


class AdaVersionError(AdaError):
    """An Ada version refused. `ada` is the name asked for, `latest` the latest stable, which the server names as the
    fix: `client.ada.versions()` lists them all."""

    @property
    def ada(self) -> Optional[str]:
        return self.detail.get("ada")

    @property
    def latest(self) -> Optional[str]:
        return self.detail.get("latest")


class AdaVersionUnknownError(AdaVersionError):
    """E_ADA_UNKNOWN (422): no Ada version has that name. Never substituted: choose one `client.ada.versions()` lists,
    or leave `ada` out for the latest stable."""


class AdaVersionRetiredError(AdaVersionError):
    """E_ADA_RETIRED (410): that Ada version is retired, so it cannot be chosen or made live again (its models were
    moved to the latest stable, `latest`)."""


class AdaVersionDeprecatedError(AdaVersionError):
    """E_ADA_DEPRECATED (422): that Ada version is deprecated: it still answers for the models on it, but cannot be
    chosen for a new model or as an upgrade's target. Choose `latest`."""


class AdaBetaClosedError(AdaVersionError):
    """E_ADA_BETA (422): that beta is closed to new models (its models run on). Choose `latest`, or another beta."""


class AdaVersionUnavailableError(AdaVersionError):
    """E_ADA_UNAVAILABLE (503): the model's Ada version is not on this deploy. Not retried: tell support, quoting
    `trace_id`."""


class ClientTooOldError(AdaError):
    """E_CLIENT_TOO_OLD: the server speaks a newer contract (`contract`) than this SDK (`supported`): upgrade the SDK
    (`pip install -U glyphh`). Raised rather than reading answers whose shape the SDK does not know."""

    @property
    def contract(self) -> Optional[int]:
        return self.detail.get("contract")

    @property
    def supported(self) -> Optional[int]:
        return self.detail.get("supported")


class AdaDeprecationWarning(FutureWarning):
    """A model runs a deprecated Ada version, or was just moved off a retired one (the server's `Glyphh-Ada-Notice`).
    A FutureWarning, so it shows by default; once per client and notice. `warnings.simplefilter("error",
    AdaDeprecationWarning)` makes it raise."""


# A clustered self-hosted runtime's refusals (SDK 3.1 for rrotor): kept so code that catches them still imports.
class NoHeadError(AdaError):
    """E_NO_HEAD (503): a self-hosted cluster has no head. Retried; raised once retries are spent."""


class HeadLostError(AdaError):
    """E_HEAD_LOST (503): a self-hosted cluster's head went while it had the write. Never resent."""


class NotCommittedError(AdaError):
    """E_NOT_COMMITTED (503): a self-hosted cluster kept the write but most voters do not hold it yet."""


class RunLostError(AdaError):
    """E_RUN_LOST (410): a self-hosted cluster's node that held the run left."""


class ReadOnlyError(AdaError):
    """E_READ_ONLY: on a self-hosted cluster's follower, a function marked `"writes": false` wrote."""


TYPED: Dict[str, Type[AdaError]] = {
    "E_AUTH": AuthError,
    "E_UNAUTHORIZED": AuthError,
    "E_LIMIT": LimitError,
    "E_RATE": RateError,
    "E_INVALID": InvalidError,
    "E_TOO_LARGE": TooLargeError,
    "E_MODEL_MISSING": ModelMissingError,
    "E_JOB_MISSING": JobMissingError,
    "E_PRECEDENT_MISSING": PrecedentMissingError,
    "E_VERSION_MISSING": VersionMissingError,
    "E_SPEC": SpecError,
    "E_SPEC_LIMIT": SpecLimitError,
    "E_SPEC_READING": SpecReadingError,
    "E_FEW_ROLES": FewRolesError,
    "E_MAPPING": MappingError,
    "E_IMPORT": ImportRefusedError,
    "E_BACKTEST": BacktestError,
    "E_BUSY": BusyError,
    "E_NOT_READY": NotReadyError,
    "E_NO_CHANGE": NoChangeError,
    "E_IDEMPOTENCY": IdempotencyError,
    "E_CONFLICT": ConflictError,
    "E_VERSION_GONE": VersionGoneError,
    "E_EXPIRED": ExpiredError,
    "E_TIMEOUT": AdaTimeoutError,
    "E_UNAVAILABLE": UnavailableError,
    "E_ADA_UNKNOWN": AdaVersionUnknownError,
    "E_ADA_RETIRED": AdaVersionRetiredError,
    "E_ADA_DEPRECATED": AdaVersionDeprecatedError,
    "E_ADA_BETA": AdaBetaClosedError,
    "E_ADA_UNAVAILABLE": AdaVersionUnavailableError,
    "E_CLIENT_TOO_OLD": ClientTooOldError,
    "E_NO_HEAD": NoHeadError,
    "E_HEAD_LOST": HeadLostError,
    "E_NOT_COMMITTED": NotCommittedError,
    "E_RUN_LOST": RunLostError,
    "E_READ_ONLY": ReadOnlyError,
}


def error(
    code: str, message: str, status: int = 0, detail: Optional[Dict[str, Any]] = None, retry_after: Optional[float] = None
) -> AdaError:
    """The typed error for a code (AdaError for one the SDK does not know). A refusal that says when to ask again in
    its body (E_RATE's `retry_after`) and not in a header is read from the body."""
    if retry_after is None and detail and isinstance(detail.get("retry_after"), (int, float)):
        retry_after = float(detail["retry_after"])
    return TYPED.get(code, AdaError)(code, message, status, detail, retry_after)
