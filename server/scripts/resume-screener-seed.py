"""The Resume Screener's past applicants (src/glyphh_server/ops/bots/library/seeds/resume-screener.json): generated,
labelled applications to a small software company's five open roles, the precedents its three gates start from.

Every applicant is made up (names, employers, schools, numbers). Each is labelled the way a hiring manager there
would: `source` (a real applicant, or spam: staffing pitches, resume mills, scams), `fit` (strong, borderline or
poor, from how the resume meets the role, with a few judgment calls that go against the grain, as people's do) and
`made` (how much of a generated application was generated: some, mostly or fully; the text is written in that
voice). The applicants written by people carry no `made` label: there is no human class, a human application is one
with no close generated precedent when the gate is probed. One in five is `split` test: never recorded, it is what
the gates are scored on and the probe's reference is measured over. Run it again to remake the file (the same seed
makes the same file):

    uv run python scripts/resume-screener-seed.py
"""

import json
import random
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "src/glyphh_server/ops/bots/library/seeds/resume-screener.json"
R = random.Random(20261122)
FITS = ["strong", "borderline", "poor"]  # a judgment call goes one level the other way

ROLES = {
    "Senior Backend Engineer": {
        "core": ["python", "postgres", "kubernetes", "distributed systems", "aws"],
        "nice": ["go", "kafka", "redis", "terraform", "grpc"],
        "titles": [
            "Backend Engineer",
            "Software Engineer",
            "Senior Software Engineer",
            "Platform Engineer",
            "Site Reliability Engineer",
        ],
        "years": (5, 15),
        "work": [
            "cut p99 latency on the payments API from {n}ms to {m}ms",
            "moved {n} services off a monolith",
            "ran the on-call rotation for a {n}-node Postgres cluster",
            "built the event pipeline that handles {n}k messages a second",
            "wrote the migration tooling we used for {n} schema changes",
        ],
    },
    "Product Designer": {
        "core": ["figma", "user research", "prototyping", "design systems", "interaction design"],
        "nice": ["accessibility", "motion design", "html", "css", "usability testing"],
        "titles": ["Product Designer", "UX Designer", "UI Designer", "Senior Product Designer", "Interaction Designer"],
        "years": (3, 12),
        "work": [
            "redesigned onboarding and lifted activation {n}%",
            "ran {n} usability sessions for the checkout flow",
            "built the {n}-component design system our three apps share",
            "cut support tickets about billing by {n}% with a new settings page",
        ],
    },
    "Data Analyst": {
        "core": ["sql", "python", "dashboards", "statistics", "excel"],
        "nice": ["dbt", "looker", "tableau", "a/b testing", "bigquery"],
        "titles": [
            "Data Analyst",
            "Business Analyst",
            "Analytics Engineer",
            "Junior Data Analyst",
            "Reporting Analyst",
        ],
        "years": (1, 8),
        "work": [
            "built the weekly revenue dashboard {n} people read",
            "found a {n}% leak in the trial funnel",
            "set up the A/B test readouts for {n} experiments",
            "rewrote {n} reports in dbt",
        ],
    },
    "Customer Success Manager": {
        "core": ["customer onboarding", "renewals", "salesforce", "account management", "churn reduction"],
        "nice": ["zendesk", "gainsight", "saas", "training", "upselling"],
        "titles": [
            "Customer Success Manager",
            "Account Manager",
            "Customer Support Lead",
            "Onboarding Specialist",
            "Client Services Manager",
        ],
        "years": (2, 10),
        "work": [
            "kept net retention at {n}% across {m} accounts",
            "onboarded {n} customers in a quarter",
            "cut churn in my book by {n}%",
            "ran the renewal calls for {n} enterprise accounts",
        ],
    },
    "Frontend Engineer": {
        "core": ["typescript", "react", "css", "accessibility", "testing"],
        "nice": ["next.js", "graphql", "webpack", "storybook", "performance"],
        "titles": ["Frontend Engineer", "Web Developer", "Software Engineer", "UI Engineer", "Full Stack Developer"],
        "years": (2, 12),
        "work": [
            "took our bundle from {n} KB to {m} KB",
            "rebuilt the dashboard in React with {n} components",
            "got the app to a {n} Lighthouse score",
            "fixed {n} accessibility bugs our audit found",
        ],
    },
}
OFF_SKILLS = [
    "photoshop",
    "seo",
    "copywriting",
    "cold calling",
    "event planning",
    "quickbooks",
    "autocad",
    "java",
    "c++",
    "php",
    "wordpress",
    "social media",
    "bookkeeping",
    "retail",
    "logistics",
    "teaching",
]
OFF_TITLES = [
    "Marketing Coordinator",
    "Store Manager",
    "Teacher",
    "Office Manager",
    "Sales Associate",
    "Mechanical Engineer",
    "Barista",
    "Recruiter",
    "Paralegal",
]
FIRST = [
    "Maya",
    "Jonas",
    "Priya",
    "Diego",
    "Aisha",
    "Tomás",
    "Hana",
    "Kwame",
    "Lena",
    "Rafael",
    "Sofia",
    "Oluwaseun",
    "Mei",
    "Arjun",
    "Clara",
    "Ibrahim",
    "Noor",
    "Elias",
    "Grace",
    "Mateo",
    "Yuki",
    "Fatima",
    "Liam",
    "Zara",
    "Daniel",
    "Amara",
    "Chen",
    "Isabel",
    "Samir",
    "Ana",
    "Kofi",
    "Ines",
    "Marcus",
    "Leila",
    "Ravi",
    "Emma",
]
LAST = [
    "Okafor",
    "Lindqvist",
    "Raman",
    "Herrera",
    "Bello",
    "Novak",
    "Sato",
    "Mensah",
    "Fischer",
    "Costa",
    "Rossi",
    "Adeyemi",
    "Wang",
    "Mehta",
    "Dubois",
    "Haddad",
    "Karimi",
    "Berg",
    "Walsh",
    "Silva",
    "Tanaka",
    "Nasser",
    "Murphy",
    "Ali",
    "Kowalski",
    "Nwosu",
    "Li",
    "Moreno",
    "Khan",
    "Pereira",
    "Asante",
    "Martins",
    "Reed",
]
COMPANY_MAIL = ["fastmail.com", "proton.me", "gmail.com", "outlook.com", "icloud.com", "hey.com", "yahoo.com"]
EMPLOYERS = [
    "Brightline",
    "Northwind Labs",
    "Kestrel Health",
    "Parcelwise",
    "Lumen Bank",
    "Ostara",
    "Tidepool",
    "Quarry Analytics",
    "Fernway",
    "Holloway Retail",
    "Cobalt Freight",
    "Pinecrest Software",
    "Muni Transit",
]
SCHOOLS = [
    "State University",
    "City College",
    "Institute of Technology",
    "University of Leeds",
    "McGill University",
    "University of Lagos",
    "IIT Bombay",
    "Universidad de Chile",
    "a coding bootcamp",
]
DEGREES = {"bachelors": "B.Sc.", "masters": "M.Sc.", "phd": "Ph.D.", "none": ""}
STOCK = [
    "I am writing to express my keen interest in",
    "I am confident that my skills make me an ideal candidate",
    "proven track record",
    "results-driven professional",
    "passionate about leveraging",
    "in today's fast-paced environment",
    "I would welcome the opportunity to",
    "dynamic team",
    "thrive in collaborative environments",
    "spearheaded cross-functional initiatives",
    "detail-oriented",
    "drive impactful results",
    "align perfectly with your mission",
    "a unique blend of",
    "I am eager to bring my expertise",
    "delve into",
    "robust and scalable solutions",
    "commitment to excellence",
    "hit the ground running",
    "synergy",
]
CASUAL = [
    "Saw the post on your careers page and wanted to throw my hat in.",
    "A friend who used to work there said the team is great, so here I am.",
    "Short version: I like hard problems and small teams.",
    "Honestly the job description read like my last two years.",
    "I'll keep this brief.",
]
SPAM = [
    (
        "Top offshore developers at $15/hr",
        "partnerships@devstaff-global.biz",
        "fail",
        True,
        "Hi Hiring Manager, We noticed you are hiring. Our agency provides 500+ vetted offshore developers at $15/hr. "
        "Book a call: http://devstaff-global.biz/book http://devstaff-global.biz/rates http://devstaff-global.biz/cases",
    ),
    (
        "Your resume screening, automated - free trial",
        "growth@hirebotz.io",
        "pass",
        True,
        "Stop wasting time on resumes! HireBotz screens 10,000 applicants a minute. Start your free trial today: "
        "https://hirebotz.io/trial https://hirebotz.io/pricing Unsubscribe here.",
    ),
    (
        "Professional resume writing for your candidates",
        "sales@cv-masters.net",
        "fail",
        True,
        "Dear Sir/Madam, we write ATS-beating resumes for job seekers. Partner with us and earn 20% commission. "
        "Visit http://cv-masters.net/partner",
    ),
    (
        "Re: Application - urgent payment needed",
        "hr.department@secure-payroll-verify.com",
        "fail",
        False,
        "Dear applicant manager, to process the candidate's background check please wire the $250 fee to the account "
        "below within 24 hours. http://secure-payroll-verify.com/pay",
    ),
    (
        "Staff augmentation partnership",
        "bd@nearshore-talent.co",
        "pass",
        True,
        "Hello! We are a nearshore staff augmentation firm with engineers ready to start Monday. Can I send our deck? "
        "https://nearshore-talent.co/deck https://nearshore-talent.co/calendly",
    ),
    (
        "Job Application",
        "noreply@mass-apply-pro.com",
        "pass",
        True,
        "This application was submitted on behalf of a candidate by MassApply Pro. View 1,200 more candidates at "
        "https://mass-apply-pro.com/candidates Unsubscribe.",
    ),
    (
        "Crypto opportunity for your team",
        "invest@coinyield-max.xyz",
        "fail",
        False,
        "Make 40% a month! Your employees can join our crypto yield program. https://coinyield-max.xyz/join",
    ),
    (
        "We placed 300 engineers last year",
        "hello@recruitfast-agency.com",
        "pass",
        True,
        "Hi there, we're a contingency recruiting agency. 25% fee, 90-day guarantee. Reply YES to see profiles. "
        "https://recruitfast-agency.com/profiles",
    ),
]


def pick(xs: list, k: int) -> list:
    return R.sample(xs, min(k, len(xs)))


def skills_for(role: dict, fit: str) -> list[str]:
    if fit == "strong":
        got = pick(role["core"], R.randint(3, 5)) + pick(role["nice"], R.randint(1, 3))
    elif fit == "borderline":  # a near miss: some of the role, not enough
        got = pick(role["core"], R.randint(0, 2)) + pick(role["nice"], R.randint(0, 2)) + pick(OFF_SKILLS, 2)
    else:  # another career
        got = pick(OFF_SKILLS, R.randint(3, 6)) + pick(role["nice"], R.randint(0, 1))
    return sorted(set(got))


def history(role: dict, fit: str, years: int) -> list[tuple[str, str, int, int]]:
    jobs, end = [], 2026
    left = max(1, years)
    while left > 0 and len(jobs) < 4:
        span = min(left, R.randint(1, 5))
        on_role = fit == "strong" or R.random() < (0.6 if fit == "borderline" else 0.1)
        title = R.choice(role["titles"]) if on_role else R.choice(OFF_TITLES)
        jobs.append((title, R.choice(EMPLOYERS), end - span, end))
        end -= span
        left -= span
    return jobs


def human_line(role: dict) -> str:
    n = R.randint(4, 60)
    return R.choice(role["work"]).format(n=n, m=R.randint(2, n - 1))


def cover(name: str, title: str, role: dict, made: str, years: int) -> str:
    first = name.split()[0]
    human = [
        R.choice(CASUAL),
        f"At my last job I {human_line(role)}.",
        f"Before that I {human_line(role)}.",
        f"I've done this for {years} year{'' if years == 1 else 's'}, mostly at small companies.",
        "Happy to share code or work samples.",
        f"Thanks for reading,\n{first}",
    ]
    stock = [
        f"{STOCK[0]} the {title} position.",
        f"As a {STOCK[3]} with a {STOCK[2]}, I am {STOCK[4]} my skills.",
        f"{STOCK[1]} for this role {STOCK[5]}.",
        f"I have {STOCK[9]} and delivered {STOCK[16]}.",
        f"My {STOCK[17]} and {STOCK[10]} nature {STOCK[12]}.",
        f"{STOCK[6]} discuss how I can {STOCK[11]}.",
        f"I am confident I can {STOCK[18]} and join your {STOCK[7]}.",
        f"Sincerely,\n{name}",
    ]
    if made == "none":
        lines = human
    elif made == "some":
        lines = [*human[:3], R.choice(stock[1:6]), *human[3:]]
    elif made == "mostly":
        lines = [*stock[:2], f"At my last job I {human_line(role)}.", *stock[2:]]
    else:
        lines = stock
    return "\n".join(lines)


def resume(name: str, email: str, role: dict, fit: str, made: str, years: int, school: tuple[str, str]) -> str:
    jobs = history(role, fit, years)
    skills = skills_for(role, fit)
    out = [name, f"{email} | +1 555 {R.randint(100, 999)} {R.randint(1000, 9999)}", ""]
    if made in ("mostly", "fully"):
        out.append(
            f"Summary: {STOCK[3].capitalize()} with a {STOCK[2]} of delivering {STOCK[16]}. "
            f"{STOCK[4].capitalize()} {STOCK[13]} skills to {STOCK[11]}."
        )
    out.append("Experience")
    for title, employer, start, end in jobs:
        out.append(f"{title}, {employer} ({start} - {'Present' if end == 2026 else end})")
        did = "Spearheaded initiatives that drove impactful results" if made == "fully" else human_line(role)
        out.append(f"- {did}")
    out += ["", "Skills: " + ", ".join(skills)]
    if school[0] != "none":
        out += ["", f"Education: {DEGREES[school[0]]} {school[1]}"]
    return "\n".join(out)


def applicant(i: int) -> dict:
    title = R.choice(list(ROLES))
    role = ROLES[title]
    fit = R.choices(FITS, [35, 30, 35])[0]
    made = R.choices(["none", "some", "mostly", "fully"], [40, 25, 20, 15])[0]
    low, high = role["years"]
    years = R.randint(low, high) if fit == "strong" else R.choice([R.randint(0, max(0, low - 1)), R.randint(low, high)])
    name = f"{R.choice(FIRST)} {R.choice(LAST)}"
    email = f"{name.lower().replace(' ', '.').replace('á', 'a')}{R.randint(1, 99)}@{R.choice(COMPANY_MAIL)}"
    school = (R.choice(["bachelors", "bachelors", "masters", "phd", "none"]), R.choice(SCHOOLS))
    subject = R.choice([f"Application: {title}", f"{title} - {name}", f"Applying for {title}", f"{title} role"])
    label = fit if R.random() > 0.06 else ("borderline" if fit != "borderline" else R.choice(["strong", "poor"]))
    return {
        "from": f"{name} <{email}>", "subject": subject, "auth": "spf=pass dkim=pass dmarc=pass", "bulk": False,
        "body": cover(name, title, role, made, years), "resume_kind": R.choice(["pdf", "pdf", "docx", "text"]),
        "resume": resume(name, email, role, fit, made, years, school),
        "labels": {"source": "real", "fit": label} | ({} if made == "none" else {"made": made}),
    }  # fmt: skip


def spam(i: int) -> dict:
    subject, sender, auth, bulk, body = SPAM[i % len(SPAM)]
    auth_line = (
        "spf=pass dkim=pass dmarc=pass"
        if auth == "pass"
        else R.choice(["spf=fail dkim=none dmarc=fail", "spf=softfail dkim=pass dmarc=fail"])
    )
    return {
        "from": f"{sender.split('@')[0].title()} <{sender}>",
        "subject": subject,
        "auth": auth_line,
        "bulk": bulk,
        "body": body,
        "resume_kind": "none",
        "resume": "",
        "labels": {"source": "spam"},
    }


def main() -> None:
    made = [applicant(i) for i in range(176)] + [spam(i) for i in range(24)]
    R.shuffle(made)
    for i, a in enumerate(made, 1):
        a["id"], a["split"] = f"seed-{i:03d}", "test" if i % 5 == 0 else "train"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {"about": __doc__.split("\n\n")[0].replace("\n", " "), "applicants": made}, indent=1, ensure_ascii=False
        )
        + "\n"
    )
    print(f"{len(made)} applicants written to {OUT}")


if __name__ == "__main__":
    main()
