"""A Kubernetes issue, as it reads the moment it is opened, turned into
an Ada situation. Everything a reporter wrote that names a SIG is cut
first (/sig commands, the "Relevant SIG(s)" section, [sig-x] tags in
test names), so routing has to come from what the issue is about.
"""

import re

# canonical component -> patterns (lowercase text)
COMPONENTS = {
    "kubelet": r"\bkubelet\b",
    "apiserver": r"\bkube-apiserver\b|\bapi ?server\b|\bapiserver\b",
    "scheduler": r"\bkube-scheduler\b|\bscheduler\b|\bscheduling\b|\bpreemption\b|\btaint|\btoleration|\baffinity\b",
    "controller_manager": r"\bkube-controller-manager\b|\bcontroller[- ]manager\b",
    "kube_proxy": r"\bkube-proxy\b|\biptables\b|\bipvs\b|\bnftables\b",
    "kubectl": r"\bkubectl\b",
    "kubeadm": r"\bkubeadm\b",
    "etcd": r"\betcd\b",
    "dns": r"\bcoredns\b|\bkube-dns\b|\bdns\b",
    "storage": r"\bcsi\b|\bvolume|\bpvc?\b|\bpersistentvolume|\bstorageclass|\bmount",
    "network": r"\bcni\b|\bnetworkpolic|\bservice ?cidr|\bendpointslice|\bendpoints?\b|\bloadbalancer\b|\bingress\b|\bipv6\b|\bdual-?stack",
    "runtime": r"\bcri\b|\bcontainerd\b|\bcri-o\b|\bcrio\b|\bruntime\b|\bimage pull|\bsandbox\b",
    "cgroup": r"\bcgroups?\b|\boom\b|\bmemory limit|\bcpu manager|\btopology manager|\bswap\b",
    "device": r"\bdra\b|\bdynamic resource|\bresourceclaim|\bdevice plugin|\bgpu\b",
    "autoscaling": r"\bhpa\b|\bvpa\b|\bautoscal",
    "workloads": r"\bdeployment|\bstatefulset|\bdaemonset|\breplicaset|\bcronjob|\bjob controller|\bbatch/v1",
    "pod_lifecycle": r"\bpod lifecycle|\bprobe|\bliveness|\breadiness|\bstartup probe|\bgraceful|\bterminat|\bevict|\bpreStop",
    "crd": r"\bcrds?\b|\bcustomresource|\bapiextensions|\bconversion webhook",
    "admission": r"\badmission|\bwebhook|\bvalidatingadmissionpolicy|\bcel\b",
    "auth": r"\brbac\b|\bauthn|\bauthz|\bauthenticat|\bauthoriz|\bserviceaccount|\btoken\b|\boidc\b|\bcertificate",
    "client_go": r"\bclient-go\b|\binformer|\bwatch\b|\breflector|\blister",
    "apimachinery": r"\bapimachinery\b|\bserializ|\bprotobuf|\bmanagedfields|\bserver-side apply|\bssa\b|\bfield manager|\bopenapi",
    "metrics": r"\bmetrics?\b|\bprometheus|\binstrumentation|\btracing|\bklog\b|\blogging\b",
    "windows": r"\bwindows\b",
    "node_lifecycle": r"\bnode lifecycle|\bnotready|\bnode status|\blease\b|\bheartbeat",
    "scale": r"\bscalability|\bperf(ormance)?\b|\blatency\b|\b5k\b|\bdensity\b|\bload test",
    "feature_gate": r"\bfeature ?gates?\b|\bbeta\b|\balpha\b|\bkep\b|\bga\b",
    "test_infra": r"\bprow\b|\btestgrid\b|\bci-kubernetes|\bpull-kubernetes|\bkind cluster|\bginkgo\b",
    "build_release": r"\bgo\.mod\b|\bgolang\b|\bgo 1\.\d+|\bdependenc|\bbump\b|\brelease (branch|notes|blocking)",
    "cloud_provider": r"\bcloud[- ]provider|\bccm\b|\bcloud-controller",
    "security": r"\bcve\b|\bvulnerab|\bsecurity\b|\bseccomp|\bapparmor|\bselinux|\bpod security",
    "gc_quota": r"\bgarbage collect|\bownerreference|\bfinalizer|\bresourcequota|\blimitrange|\bnamespace deletion",
}
PATH = re.compile(r"\b((?:pkg|cmd|plugin|test/e2e|test/integration|staging/src/k8s\.io)/[\w.-]+)")
STATED = [
    re.compile(r"^\s*/(?:sig|area|kind|wg|triage|priority)\b.*$", re.M | re.I),
    re.compile(r"\[sig-[\w-]+\]", re.I),
    re.compile(r"\bsig[-/ ](?:node|network|storage|api-machinery|scheduling|apps|cli|auth|windows|"
               r"instrumentation|scalability|autoscaling|release|testing|architecture|"
               r"cloud-provider|cluster-lifecycle|security|etcd|k8s-infra|docs)\b", re.I),
]
SECTION = re.compile(r"^#{2,4} ?Relevant SIG\(s\).*?(?=^#{2,4} |\Z)", re.M | re.S)
# the environment block every bug template carries: incidental (rule 2)
ENVIRONMENT = re.compile(
    r"^#{2,4} ?(Kubernetes version|Cloud provider|OS version|Install tools|"
    r"Container runtime|Related plugins).*?(?=^#{2,4} |\Z)", re.M | re.S)
HEADING = re.compile(r"^#{1,4} .*$", re.M)


def clean(text: str) -> str:
    text = SECTION.sub("", text or "")
    text = ENVIRONMENT.sub("", text)
    text = HEADING.sub("", text)
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)
    for rx in STATED:
        text = rx.sub(" ", text)
    return text


def kind_of(body: str) -> str:
    if "Which tests are flaking?" in body or "Which jobs are flaking?" in body:
        return "flake"
    if "Which tests are failing?" in body or "Which jobs are failing?" in body:
        return "failing_test"
    if "What would you like to be added?" in body:
        return "feature"
    if "What happened?" in body:
        return "bug"
    return "other"


def situation(issue: dict) -> dict:
    body = issue.get("body") or ""
    title = clean(issue["title"]).lower()
    text = (title + "\n" + clean(body)).lower()
    found = sorted(c for c, rx in COMPONENTS.items() if re.search(rx, text))
    in_title = sorted(c for c, rx in COMPONENTS.items() if re.search(rx, title))
    paths = sorted({"/".join(p.split("/")[:4 if p.startswith("staging") else 2])
                    for p in PATH.findall(text)})
    s = {"kind": kind_of(body)}
    if found:
        s["components"] = found
    if in_title:
        s["title"] = in_title
    if paths:
        s["paths"] = paths[:6]
    return s


def stated_sigs(issue: dict) -> list:
    body = issue.get("body") or ""
    sigs = re.findall(r"^\s*/sig\s+([\w-]+)", body, re.M)
    sigs += re.findall(r"\[sig-([\w-]+)\]", body + " " + issue["title"])
    return sorted({f"sig/{s.lower()}" for s in sigs})


def fix_dirs(prs: list) -> list:
    """Directories a fix touched: first two path segments (four under
    staging), vendor and module files left out."""
    out = set()
    for pr in prs:
        for f in pr["files"]:
            if f.startswith(("vendor/", "go.")) or "/" not in f:
                continue
            parts = f.split("/")
            out.add("/".join(parts[:4] if parts[0] == "staging" else parts[:2]))
    return sorted(out)
