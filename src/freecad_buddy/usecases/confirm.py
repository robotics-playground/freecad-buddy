"""The preview-token codec and the mutation confirm gate.

A ``preview_id`` is a self-authenticating token: ``preview_dry_run`` signs the operation, the
document handle, a digest of the arguments and the document's fingerprint at the moment it
measured them; the gate re-derives all four from the call it is asked to run and compares.

The one piece of state kept between the two calls is the set of token ids already spent. The
comparison above proves the document is still in the state the preview measured, which is not the
same as proving the token has not been used: a mutation writing a property the value it already
holds commits without moving the fingerprint, so its token would otherwise keep verifying. A
token authorizes one mutation.

The signing secret is minted once per process. A token therefore only verifies in the process
that issued it, which is the process that will run the mutation: the RPC listener and the
mutation use cases share one interpreter.

The auto-approve posture is an operator-set flag carried on ``Capabilities``, never a wire field.
A ``confirm`` object from the wire cannot request it.

Stdlib only.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time

from freecad_buddy.contracts.confirm import ApprovalRecord, Confirm, PreviewTokenPayload
from freecad_buddy.usecases.documents import ValidationError

_TOKEN_PREFIX = "fcb-preview:"
_SECRET = secrets.token_bytes(32)

# The operator posture for this process, set once at host startup from the capability record. It
# is process-wide because that is what it describes: one environment flag read once, applying to
# every call the host serves.
_AUTO_APPROVE = False

# The sink approval records and a bracketed mutation's own before/after records are written to,
# installed by the host once its audit log is open. The mutation use cases are reached through a
# handler that takes no sink argument, so the sink is held here rather than threaded through
# eighteen tool signatures.
_APPROVAL_SINK: object = None

# The active preview_exemption while a preview runs its operation on its own throwaway copy, else
# None. Thread-local rather than process-wide: a marshaled call that overruns its timeout keeps
# running on its own thread after the caller has already been handed a timeout envelope, so a
# process-wide slot would stay set by that abandoned body and exempt every later call from the
# gate. A thread-local slot confines an abandoned exemption to the thread that leaked it.
_EXEMPT_STATE = threading.local()

# The ``jti`` of every token an authorized mutation has already spent, mapped to the token's own
# expiry. A token is single-use: the state check refuses a REPLAY only when the mutation moved the
# document digest, and an op that writes a property the value it already holds commits without
# moving it, leaving the signed fingerprint still matching. Keyed on ``jti`` rather than on the
# token string because two previews of the same operation on an unchanged document produce equal
# payloads and therefore identical tokens, so spending one would pre-spend the other.
#
# The set is bounded by the expiry it stores rather than by a size cap: an entry past its own
# deadline can never authorize anything again, since verify_confirm refuses an expired token
# before it looks here. Sweeping on write keeps the set proportional to the tokens live in one
# TTL window, not to the tokens ever issued.
_SPENT_TOKENS: dict[str, float] = {}
_SPENT_LOCK = threading.Lock()

# The fields the wire ``confirm`` object declares; anything else is refused rather than ignored,
# so a client-supplied ``autoApprove`` is a rejection and not a silently dropped key.
_CONFIRM_FIELDS = frozenset(Confirm.__annotations__)


def _active_exemption() -> object:
    """Return the preview exemption active on this thread, or ``None``."""
    return getattr(_EXEMPT_STATE, "current", None)


def args_digest(args: dict) -> str:
    """Return the SHA-256 over ``args`` in canonical JSON form.

    ``default=repr`` keeps a non-JSON-serializable argument from raising, mirroring the audit
    sink's digest so the same arguments produce the same digest on both paths.
    """
    payload = json.dumps(args, sort_keys=True, ensure_ascii=False, default=repr).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def new_token_id() -> str:
    """Return a fresh token id, distinguishing two previews that would otherwise sign alike."""
    return secrets.token_urlsafe(16)


def spend_confirm(approval: ApprovalRecord, params: dict) -> None:
    """Consume the token that authorized this call, so it cannot authorize a second one.

    Called once the mutation is going ahead — after any precheck — so a call refused before it
    runs leaves its token usable and the caller can correct the arguments and re-send.

    Only the token path spends anything: an auto-approved call presented no token, and a preview
    runs against a throwaway copy and authorized nothing.
    """
    if approval["mode"] != "preview_token":
        return
    confirm_obj = params.get("confirm")
    token = confirm_obj.get("preview_id") if isinstance(confirm_obj, dict) else None
    try:
        payload = decode_preview_token(token)
    except ValidationError:
        # Unreachable from the gate, which decoded the same token to authorize the call; a token
        # that cannot be decoded also cannot be replayed, so there is nothing to record.
        return
    spend_token(payload["jti"], float(payload["exp"]))


def _is_spent(jti: object, now: float) -> bool:
    """Whether ``jti`` names a token an authorized mutation has already spent."""
    with _SPENT_LOCK:
        deadline = _SPENT_TOKENS.get(str(jti))
    return deadline is not None and now <= deadline


def spend_token(jti: object, expires_at: float, now: float | None = None) -> None:
    """Record ``jti`` as spent until ``expires_at``, dropping entries already past their own.

    Called once a mutation is authorized, so a refused call leaves its token usable: the caller
    fixes what was wrong and re-sends rather than re-previewing.
    """
    moment = time.time() if now is None else now
    with _SPENT_LOCK:
        for spent, deadline in list(_SPENT_TOKENS.items()):
            if moment > deadline:
                del _SPENT_TOKENS[spent]
        _SPENT_TOKENS[str(jti)] = expires_at


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body: bytes) -> bytes:
    return hmac.new(_SECRET, body, hashlib.sha256).digest()


def mint_preview_token(payload: PreviewTokenPayload) -> str:
    """Return a signed ``fcb-preview:<body>.<signature>`` token carrying ``payload``."""
    body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{_TOKEN_PREFIX}{_b64encode(body)}.{_b64encode(_sign(body))}"


def decode_preview_token(token: object) -> PreviewTokenPayload:
    """Return the payload of a well-formed, correctly signed ``token``.

    :raises ValidationError: the token is not a string, is not in the expected form, carries a
        signature that does not match this process's secret, or decodes to something other than a
        payload object with every field present.
    """
    if not isinstance(token, str) or not token.startswith(_TOKEN_PREFIX):
        raise ValidationError("confirm.preview_id is not a preview token")
    encoded_body, separator, encoded_signature = token[len(_TOKEN_PREFIX) :].partition(".")
    if not separator or not encoded_body or not encoded_signature:
        raise ValidationError("confirm.preview_id is malformed")
    try:
        body = _b64decode(encoded_body)
        signature = _b64decode(encoded_signature)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValidationError("confirm.preview_id is not decodable") from exc
    if not hmac.compare_digest(signature, _sign(body)):
        raise ValidationError("confirm.preview_id carries an invalid signature")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValidationError("confirm.preview_id payload is not readable") from exc
    if not isinstance(payload, dict):
        raise ValidationError("confirm.preview_id payload is not an object")
    missing = [key for key in PreviewTokenPayload.__annotations__ if key not in payload]
    if missing:
        raise ValidationError(f"confirm.preview_id payload is missing {missing}")
    return payload


def _payload_for(confirm: object) -> PreviewTokenPayload:
    """Validate the ``confirm`` object's shape and return its decoded token payload.

    :raises ValidationError: ``confirm`` is absent, is not an object, carries a field the wire
        shape does not declare, states an ``elicitation_action`` other than ``"accept"``, or
        carries no usable ``preview_id``.
    """
    if confirm is None:
        raise ValidationError(
            "this mutation requires a confirm; call preview_dry_run and pass the preview_id it "
            "returns as confirm.preview_id"
        )
    if not isinstance(confirm, dict):
        raise ValidationError("confirm must be an object")
    unknown = sorted(set(confirm) - _CONFIRM_FIELDS)
    if unknown:
        raise ValidationError(f"confirm carries field(s) the schema does not declare: {unknown}")
    action = confirm.get("elicitation_action", "accept")
    if action != "accept":
        raise ValidationError(f"confirm.elicitation_action must be 'accept', got {action!r}")
    return decode_preview_token(confirm.get("preview_id"))


def verify_confirm(
    confirm: object,
    *,
    tool: str,
    args: dict,
    doc_handle: str,
    fingerprint_now: str | None,
    auto_approve: bool = False,
    now: float | None = None,
) -> ApprovalRecord:
    """Authorize one mutation call; return the record the caller must audit.

    An operator-set ``auto_approve`` posture approves without a token. Otherwise ``confirm`` must
    carry a ``preview_id`` this process minted whose payload names this tool, these arguments,
    this document handle and this fingerprint, and whose expiry has not passed.

    :param tool: the tool being called, compared against the token's ``tool``.
    :param args: the caller's own arguments, digested and compared against ``args_digest``.
    :param doc_handle: the resolved document handle, compared against the token's ``doc``.
    :param fingerprint_now: the live document's current fingerprint digest, compared against the
        reading the preview took.
    :param auto_approve: the operator posture; a wire field can never set it.
    :param now: epoch seconds to check the expiry against; defaults to the current clock.
    :raises ValidationError: any comparison fails, or the confirm is absent or malformed.
    """
    digest = args_digest(args)
    if auto_approve:
        return {
            "mode": "auto_approve",
            "tool": tool,
            "doc": doc_handle,
            "args_digest": digest,
            "fingerprint_before": fingerprint_now,
        }

    payload = _payload_for(confirm)
    # The token path compares against a reading of the live document. Without one there is
    # nothing to compare, and stringifying both sides would let a payload carrying the literal
    # "None" verify against an unread document.
    if fingerprint_now is None:
        raise ValidationError("no live fingerprint to check confirm.preview_id against")
    deadline = payload["exp"]
    if not isinstance(deadline, (int, float)) or isinstance(deadline, bool):
        raise ValidationError("confirm.preview_id carries no readable expiry")
    moment = time.time() if now is None else now
    if moment > float(deadline):
        raise ValidationError("confirm.preview_id has expired; re-run preview_dry_run")
    # Checked after the expiry so a token past its deadline is refused as expired and never
    # consults the spent set, which is what lets that set be swept by expiry alone.
    if _is_spent(payload["jti"], moment):
        raise ValidationError(
            "confirm.preview_id has already authorized a mutation; re-run preview_dry_run"
        )
    if not hmac.compare_digest(str(payload["doc"]), doc_handle):
        raise ValidationError("confirm.preview_id was issued for a different document")
    if not hmac.compare_digest(str(payload["tool"]), tool):
        raise ValidationError(
            f"confirm.preview_id was issued for {payload['tool']!r}, not {tool!r}"
        )
    if not hmac.compare_digest(str(payload["args_digest"]), digest):
        raise ValidationError("confirm.preview_id was issued for different arguments")
    if not hmac.compare_digest(str(payload["fingerprint_before"]), str(fingerprint_now)):
        raise ValidationError(
            "the document has changed since the preview was taken; re-run preview_dry_run"
        )
    return {
        "mode": "preview_token",
        "tool": tool,
        "doc": doc_handle,
        "args_digest": digest,
        "fingerprint_before": fingerprint_now,
    }


def set_auto_approve(enabled: bool) -> bool:
    """Set this process's auto-approve posture; return the value it replaced."""
    global _AUTO_APPROVE
    previous = _AUTO_APPROVE
    _AUTO_APPROVE = bool(enabled)
    return previous


def auto_approve() -> bool:
    """Whether this process is configured to run mutations without a confirm."""
    return _AUTO_APPROVE


def gate_mutation(document: object, handle: str, tool: str, params: dict) -> ApprovalRecord:
    """Authorize the mutation ``tool`` is about to run on ``document``.

    The confirm is taken from ``params``, and the arguments the token is compared against are
    ``params`` minus the two fields the token never covered: the document handle, which is
    compared on its own, and the confirm itself. The live fingerprint is read on both the token
    and the auto-approve path: the token compares against it, and the approval record carries it
    either way, so the approval line names the same ``fingerprint_before`` as the mutation lines.

    :param document: the resolved document.
    :param handle: the resolved document handle.
    :raises ValidationError: the call is not authorized, including when the document's state
        cannot be read.
    """
    from freecad_buddy.usecases.fingerprint import fingerprint

    args = {k: v for k, v in params.items() if k not in ("doc", "confirm")}

    exemption = _active_exemption()
    if exemption is not None:
        exemption.args_digest = args_digest(args)
        return {
            "mode": "preview_copy",
            "tool": tool,
            "doc": handle,
            "args_digest": exemption.args_digest,
            "fingerprint_before": None,
        }

    # A gate that cannot read the state it must record refuses rather than raising past its own
    # boundary: an unreadable shape (SerializerUnavailable, or an OCCT error from a degenerate
    # B-rep) would otherwise leave the gate as an unexpected RECOMPUTE_ERROR instead of the
    # refusal every other gate failure produces.
    try:
        fingerprint_now = fingerprint(document)["digest"]
    except Exception as exc:  # noqa: BLE001 - any unreadable state is a refusal, not a crash
        raise ValidationError(
            f"cannot read the state of {handle} to authorize the mutation: {exc}"
        ) from exc

    return verify_confirm(
        params.get("confirm"),
        tool=tool,
        args=args,
        doc_handle=handle,
        fingerprint_now=fingerprint_now,
        auto_approve=auto_approve(),
    )


class preview_exemption:  # noqa: N801 - a context manager used as a statement, not a type
    """Exempt the mutation gate for a preview's run on its throwaway copy, capturing its digest.

    A preview is what mints the token a live apply presents, so it cannot present one itself. The
    exemption is scoped to the copy: it is entered immediately around the use-case call and left
    before anything touches the live document, and it never reaches an apply, which still runs
    the full gate against the live document's own fingerprint. It is also scoped to the calling
    thread, so a body abandoned after a marshal timeout cannot exempt any other call.

    While exempt the gate still computes the argument digest and records it here, so the token is
    signed over the same normalized view the gate will re-derive on the apply. Taking the digest
    from the preview's own ``args`` instead would compare a caller's sparse input against the
    tool's fully defaulted parameter set and never match.

    :ivar args_digest: the digest the gated call computed, or ``None`` if the op never reached
        the gate.
    """

    def __init__(self) -> None:
        self.args_digest: str | None = None

    def __enter__(self) -> "preview_exemption":
        self._previous = _active_exemption()
        _EXEMPT_STATE.current = self
        return self

    def __exit__(self, *exc_info) -> None:
        _EXEMPT_STATE.current = self._previous


def set_approval_sink(sink: object) -> object:
    """Install the sink approval records are written to; return the one it replaced."""
    global _APPROVAL_SINK
    previous = _APPROVAL_SINK
    _APPROVAL_SINK = sink
    return previous


def host_audit_sink() -> object:
    """The host's sink for a bracketed mutation's own audit lines, or ``None`` during a preview.

    A preview runs its operation on a throwaway copy; like its approval, that run authorized and
    applied no mutation, so it writes no mutation lines. The preview writes its own records.
    """
    if _active_exemption() is not None:
        return None
    return _APPROVAL_SINK


def audit_approval(sink: object, approval: ApprovalRecord, params: dict | None = None) -> None:
    """Append one ``approval`` audit line, preferring a caller-supplied sink over the host's.

    ``params`` are the authorized call's own parameters; passing them lets the approval line
    carry the same ``params_digest`` as the mutation's other audit lines, which is what joins
    an approval to the call it covered.

    A sink that cannot write must not convert an authorized mutation into a raised exception, so
    a write failure is swallowed here.

    The ``preview_copy`` mode writes nothing: the record covers a preview's run against a
    throwaway copy, which authorized no mutation and applied none, while the sink's contract is
    one approval line per authorized geometry mutation.
    """
    if approval["mode"] == "preview_copy":
        return
    target = sink if sink is not None else _APPROVAL_SINK
    if target is None:
        return
    try:
        target.approval(approval["tool"], approval["doc"], approval, params)
    except Exception:  # noqa: BLE001 - an unwritable audit sink must not abort the mutation
        pass
