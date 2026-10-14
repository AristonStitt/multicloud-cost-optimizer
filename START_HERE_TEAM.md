# START HERE — Team kickoff (Oct 14–16, 2026)

## Situation
Your team has no earlier source repository. This project is a tested **starter implementation**, not a cloud deployment. It uses fictional September 2026 AWS/Azure/GCP-shaped billing, resource, and utilization CSV files. The browser dashboard shows computed spending and optimization **candidates**, not savings actually earned. Any course-specific cloud-deployment requirements still need to be checked against the grading rubric.

## First 20 minutes: prove it runs on one laptop
From the directory containing this document:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000** and **http://127.0.0.1:8000/docs**.
If port 8000 is busy, change it to `8010` in the command and URL.

What to expect:
- **8 automated tests pass** (tested Oct 14 in the provided environment).
- Dashboard: **$5,356.80** total compute, **18 VMs**, **$1,041.60** potential (not realized) savings.
- Select `Demo Cedar Retail` to see **$1,785.60** and **$347.20** potential savings.
- Analysis Activity > **Run analysis now**: five stages successfully execute.
- Recommendations > **Why this recommendation?**: actual measurements and constraint checks.

## First hour: one GitHub repository
1. One owner creates a **new empty** GitHub repository `multicloud-cost-optimizer` (do not tick auto-README or auto-.gitignore).
2. From this directory, run:

```bash
git init
git add .
git commit -m "Initial tested CloudScope MVP"
git branch -M main
git remote add origin https://github.com/REPLACE_WITH_OWNER/multicloud-cost-optimizer.git
git push -u origin main
```

3. Repository owner invites teammates under Settings > Collaborators.
4. Teammates clone the repository and run the quick-start commands; use separate branches and pull requests for changes.
5. Designate one person to merge changes and test `main`. Do not each create a competing backend or dashboard.

## Division of responsibility (adapt to three or four people)
| Owner | Focus | Completion evidence |
|---|---|---|
| Integration / lead | GitHub repo, environment setup, merge/resolve issues, final clean install | `main` launches on demo laptop |
| Backend / algorithm | Explain billing normalization and CPU/memory/rule logic, run unit tests, verify totals | `python -m pytest -q` shows 8 passing |
| Frontend / user experience | Test navigation, customer filter, graphs, recommendation evidence, fix browser bugs | 3-minute end-to-end UI demo works |
| QA / submission | Inspect rubric, write project summary, get screenshots, record backup demo, submit | Complete correct portal artifacts on time |

With **three people**, combine Integration and QA. No one should add major frameworks without a team decision.

## Daily milestones
**Wed Oct 14:** Run the starter on 2 computers, establish GitHub ownership, assign tasks, verify rubric. Report blockers to group today.

**Thu Oct 15:** Complete bug fixes, run tests, rehearse the entire flow on the presentation laptop, record a backup demo. Freeze changes Thursday night.

**Fri Oct 16:** Re-run clean installation and tests, check all deliverables, submit early enough for upload issues. Confirm what was actually submitted.

## Definition of done
- A new teammate can clone repo and run the README commands without editing code.
- Spending totals, cloud provider breakdown, and customer filter work.
- `Run analysis now` returns completed real stages; recommendations show evidence.
- Missing measurements are not treated as zeros; fictional prices are clearly identified.
- Automated tests pass; demo screenshot/video and submission artifacts satisfy the **actual** course requirements.

## Scope freeze
**Don't add before Friday:** provider account credential collection, live migrations, Terraform automation, Prometheus/Grafana, React rewrite, authentication system, PostgreSQL rewrite, or provider-specific real-price claims.

Only change these priorities if the course rubric explicitly mandates them. 
