"""The Glyphh sign-in from a terminal: the device flow (RFC 8628) against the Glyphh server, as the plugin's sign-in
card runs it (plugins/glyphh/mcp/src/flow.ts), and the install it gives kept in ~/.glyphh/install.json, the file the
plugin keeps. One sign-in per machine, whichever signed it in: the same machine id (plugins/glyphh/hooks/glyphh/
machine.ts) reuses the same install. The Ada API takes the install's token as it takes an API key, with full
clearance; `Ada()` reads it when no key is set."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from .errors import AdaError

#: The Glyphh account API. GLYPHH_SERVER_URL moves it, as it moves the plugin's.
DEFAULT_SERVER = "https://api.glyphh.ai"

#: Sends one request: (method, url, body, bearer) -> (status, body text).
Http = Callable[[str, str, Optional[Mapping[str, Any]], Optional[str]], Tuple[int, str]]

_sleep, _now = time.sleep, time.monotonic  # the tests' seams


def server_url(url: Optional[str] = None) -> str:
    return (url or os.environ.get("GLYPHH_SERVER_URL", "").strip() or DEFAULT_SERVER).rstrip("/")


def glyphh_home(home: Optional[Path] = None) -> Path:
    return (home or Path.home()) / ".glyphh"


def install_path(home: Optional[Path] = None) -> Path:
    return glyphh_home(home) / "install.json"


@dataclass(frozen=True)
class Install:
    install_id: str
    token: str


def read_install(path: Optional[Path] = None) -> Optional[Install]:
    """The install this machine is signed in with; None when it is not."""
    try:
        v = json.loads((path or install_path()).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(v, dict) or not v.get("token") or not v.get("install_id"):
        return None
    return Install(str(v["install_id"]), str(v["token"]))


def write_install(install: Install, path: Optional[Path] = None) -> None:
    """Kept as the plugin keeps it: mode 0600 from the first byte, written to a temporary name and renamed into
    place, so no reader ever sees half a file."""
    path = path or install_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.unlink(missing_ok=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(json.dumps({"install_id": install.install_id, "token": install.token}, indent=2) + "\n")
        f.flush()
        os.fsync(f.fileno())
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def forget_install(path: Optional[Path] = None) -> None:
    try:
        (path or install_path()).unlink()
    except FileNotFoundError:
        pass


# the machine's id, as machine.ts works it out: only sha256("glyphh:" + value) leaves the machine

_ZERO_MAC = re.compile(r"^(00[:-]){5}00$")
_PRIMARY_MAC = "\n".join(
    [
        "i=$(route -n get default 2>/dev/null | awk '/interface:/{print $2; exit}')",
        "[ -n \"$i\" ] || i=$(ip route show default 2>/dev/null | awk '{for(k=1;k<NF;k++) if($k==\"dev\"){print $(k+1);"
        " exit}}')",
        '[ -n "$i" ] || exit 1',
        "cat \"/sys/class/net/$i/address\" 2>/dev/null || ifconfig \"$i\" 2>/dev/null | awk '/ether /{print $2; exit}'",
    ]
)


def _run(argv: list) -> Optional[str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _hardware_id(system: str) -> Optional[str]:
    if system in ("darwin", ""):
        out = _run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice"]) or ""
        m = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out)
        if m and m.group(1).strip():
            return m.group(1).strip()
    if system in ("linux", ""):
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                found = Path(p).read_text("utf-8").strip()
            except OSError:
                continue
            if found:
                return found
    if system in ("win32", ""):
        reg = _run(["reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Cryptography", "/v", "MachineGuid"]) or ""
        m = re.search(r"MachineGuid\s+REG_SZ\s+(\S+)", reg)
        if m:
            return m.group(1)
        for line in (_run(["wmic", "csproduct", "get", "uuid"]) or "").splitlines():
            line = line.strip()
            if re.fullmatch(r"[0-9A-Fa-f-]{32,36}", line) and not re.fullmatch(r"[Ff-]+", line):
                return line
    return None


def _primary_mac(system: str) -> Optional[str]:
    out = _run(["getmac", "/fo", "csv", "/nh"]) if system == "win32" else _run(["/bin/sh", "-c", _PRIMARY_MAC])
    m = re.search(r"([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", out or "")
    mac = m.group(0).lower().replace("-", ":") if m else None
    return mac if mac and not _ZERO_MAC.match(mac) else None


def _saved_id(home: Optional[Path]) -> str:
    path = glyphh_home(home) / "machine.json"
    try:
        kept = json.loads(path.read_text("utf-8")).get("id")
        if isinstance(kept, str) and kept:
            return kept
    except (OSError, ValueError, AttributeError):
        pass
    made = str(uuid.uuid4())
    try:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_text(json.dumps({"id": made}, indent=2) + "\n", "utf-8")
        os.chmod(path, 0o600)
    except OSError:
        pass
    return made


def _system() -> str:
    s = platform.system().lower()
    return {"darwin": "darwin", "linux": "linux", "windows": "win32"}.get(s, "")


def machine_id(home: Optional[Path] = None) -> str:
    """sha256("glyphh:" + the hardware id, else the primary MAC, else a random id kept once), hex: what the plugin
    sends for this machine, so either signs in the same install."""
    system = _system()
    value = _hardware_id(system) or _primary_mac(system) or _saved_id(home)
    return hashlib.sha256(f"glyphh:{value}".encode()).hexdigest()


# the flow


def _urllib(method: str, url: str, body: Optional[Mapping[str, Any]], bearer: Optional[str]) -> Tuple[int, str]:
    # api.glyphh.ai's edge turns away Python's own User-Agent
    headers = {"Accept": "application/json", "User-Agent": f"glyphh-python/{_version()}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)  # noqa: S310  # https by default
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def _parse(text: str) -> Dict[str, Any]:
    try:
        v = json.loads(text)
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}


def _code(status: int, text: str) -> str:
    """A refusal's code: `{"error": {"code"}}`, or RFC 8628's `{"error": "code"}`."""
    err = _parse(text).get("error")
    code = err if isinstance(err, str) else str((err or {}).get("code") or f"http_{status}")
    return re.sub(r"^e_", "", code.lower())


@dataclass(frozen=True)
class Pending:
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    interval: float
    expires_in: float


class SignIn:
    """The device flow, one step at a time: `start()` a code, show it, `wait()` for its approval."""

    def __init__(
        self,
        server: Optional[str] = None,
        *,
        http: Optional[Http] = None,
        path: Optional[Path] = None,
        machine: Optional[Callable[[], str]] = None,
        name: Optional[str] = None,
        version: str = "",
    ) -> None:
        self.server = server_url(server)
        self._http = http or _urllib
        self.path = path or install_path()
        self._machine = machine or machine_id
        self.name = (name or socket.gethostname().split(".")[0] or "terminal")[:80]
        self.version = version or f"glyphh-python-{_version()}"

    def _call(self, method: str, path: str, body: Optional[Mapping[str, Any]] = None, bearer: Optional[str] = None):
        try:
            return self._http(method, f"{self.server}{path}", body, bearer)
        except OSError as e:
            raise AdaError("E_UNREACHABLE", f"Cannot reach the Glyphh server at {self.server}: {e}") from e

    def whoami(self, token: Optional[str] = None) -> Optional[str]:
        """The signed-in account's email, per /v1/me; None when this machine is not signed in."""
        bearer = token or getattr(read_install(self.path), "token", None)
        if not bearer:
            return None
        status, text = self._call("GET", "/v1/me", None, bearer)
        if status == 401:
            return None
        if status >= 400:
            raise AdaError("E_SERVER", f"The Glyphh server refused /v1/me ({_code(status, text)}).", status)
        me = _parse(text)
        user = me.get("user") if isinstance(me.get("user"), dict) else me
        return str(user.get("email") or "your Glyphh account")

    def start(self) -> Pending:
        body = {"name": self.name, "surface": "cli", "mod_version": self.version, "machine_id": self._machine()}
        status, text = self._call("POST", "/v1/device/code", body)
        if status >= 400:
            raise AdaError("E_SERVER", f"The Glyphh server would not start a sign-in ({_code(status, text)}).", status)
        b = _parse(text)
        return Pending(
            device_code=str(b["device_code"]),
            user_code=str(b["user_code"]),
            verification_uri=str(b["verification_uri"]),
            verification_uri_complete=str(b.get("verification_uri_complete") or b["verification_uri"]),
            interval=float(b.get("interval") or 5),
            expires_in=float(b.get("expires_in") or 600),
        )

    def wait(self, p: Pending) -> str:
        """Polls no faster than the server allows until the code is approved: the install kept, its email answered.
        Refused, expired or denied: AdaError."""
        interval, deadline = p.interval, _now() + p.expires_in
        while True:
            _sleep(interval)
            if _now() >= deadline:
                raise AdaError("E_EXPIRED", "The sign-in code expired before it was approved: sign in again.")
            try:
                status, text = self._call("POST", "/v1/device/token", {"device_code": p.device_code})
            except AdaError:
                continue  # the server is away for now: ask again at the next interval
            b = _parse(text)
            if status < 400 and isinstance(b.get("access_token"), str):
                write_install(Install(str(b.get("install_id") or ""), b["access_token"]), self.path)
                return self.whoami(b["access_token"]) or "your Glyphh account"
            code = "authorization_pending" if status < 400 else _code(status, text)
            if code == "slow_down":
                interval += 5
            elif code == "expired_token":
                raise AdaError("E_EXPIRED", "The sign-in code expired before it was approved: sign in again.")
            elif code == "access_denied":
                raise AdaError("E_DENIED", "The sign-in was denied on the approval page.")
            elif code != "authorization_pending":
                raise AdaError("E_SERVER", f"The sign-in failed ({code}).", status)

    def sign_out(self) -> bool:
        """Revokes this machine's install on the server and forgets it here; False when it was not signed in. The
        plugin on this machine shares the install, so it is signed out too."""
        found = read_install(self.path)
        if found is None:
            return False
        try:
            self._call("POST", "/v1/sign-out", None, found.token)
        finally:
            forget_install(self.path)
        return True


def _version() -> str:
    from . import __version__

    return __version__
