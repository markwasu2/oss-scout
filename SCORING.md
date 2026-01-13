# OSS Scout - Scoring System v2.0

## Philosophy

**Goal**: Score "goodness" not just "activity"

A "good open source project" is:
- **Useful** (adopted, used in the wild)
- **Responsive** (maintainers present, PRs/issues handled)
- **Sustainable** (multiple maintainers, low bus factor)
- **Evolving** (still being improved)

---

## Three Core Scores

### 1. Popularity Score (0-100) = **Adoption**

**Question**: "Is it used and known?"

**Current Formula**:
```python
stars_log = clamp(log1p(stars) / log1p(10000)) * 70    # 0-70 points
forks_log = clamp(log1p(forks) / log1p(2000)) * 20     # 0-20 points
trend = 10  # Placeholder for star velocity                   # 0-10 points

popularity_score = stars_log + forks_log + trend
```

**Why Logarithmic**:
- 100 stars → 7 points
- 1,000 stars → 21 points
- 10,000 stars → 70 points (p95)
- 100,000 stars → 91 points

Linear scaling breaks: 50k stars would look identical to 100k stars at 100 points.

**What We Have**:
- ✅ Stars (current)
- ✅ Forks (current)

**Future Enhancements**:
- 📊 Star velocity (stars gained in last 90d / total)
- 📊 Package downloads (npm, pypi, crates)
- 📊 Reverse dependencies (if available)
- 📊 HuggingFace: model pulls, spaces using it

---

### 2. Health Score (0-100) = **Responsiveness + Momentum**

**Question**: "Are maintainers present? Is it evolving?"

**Current Formula**:
```python
# A) Recency: Last maintainer event (not just push)
last_event = min(days_since_push, days_since_release)
rec = clamp(0.5 ^ (last_event / 30))  # Exponential decay, 30-day half-life

# B) Activity: PRs + Contributors (robust, not gameable)
pr_activity = clamp(log1p(prs_merged_60d) / log1p(20))        # p75 ~ 20
contrib_activity = clamp(log1p(contributors_90d) / log1p(15)) # p75 ~ 15
activity = 0.6 * pr_activity + 0.4 * contrib_activity

# C) Responsiveness: Issue throughput
throughput = issues_closed_60d / max(1, issues_opened_60d)
responsiveness = clamp(throughput)  # 1.0 = keeping up, >1 = catching up

# D) Release cadence
release_score = f(days_since_release)  # 1.0 if <30d, 0.2 if >180d

# Combined (weights optimized for responsiveness)
health_score = 0.35*rec + 0.30*activity + 0.20*responsiveness + 0.15*release_score
```

**Key Improvements Over v1**:
- ❌ **Removed**: `commits_30d` (too gameable - monorepos, auto-format)
- ✅ **Added**: `prs_merged_60d` (harder to game, more meaningful)
- ❌ **Removed**: Fixed "60 days" and "80 commits" magic numbers
- ✅ **Added**: Adaptive percentile normalization (20 PRs = p75, 15 contributors = p75)
- ❌ **Removed**: `days_since_push` only
- ✅ **Added**: Last maintainer event (push OR release OR merged PR)
- ❌ **Removed**: `closed/opened` ratio (unfair to popular projects with many questions)
- ✅ **Added**: Issue throughput (closing faster than opening = healthy)

**What We Have**:
- ✅ days_since_push
- ✅ days_since_release
- ✅ commits_30d, commits_90d
- ✅ contributors_90d
- ✅ prs_merged_60d
- ✅ issues_opened_60d, issues_closed_60d

**Future Enhancements** (for even better responsiveness):
- 📊 Median time to first maintainer response (issues + PRs)
- 📊 Median time to merge PR
- 📊 Median time to close issue
- 📊 % of PRs/issues with maintainer response within 7 days
- 📊 Backlog trend: `open_issues_now - open_issues_60d_ago`
- 📊 Last maintainer comment (not just push/release)

---

### 3. People Score (0-100) = **Sustainability**

**Question**: "Will it survive? What's the bus factor?"

**Current Formula**:
```python
# A) Active maintainer count (0-40 points)
# Log scale: 2 maintainers = OK, 5 = good, 10+ = excellent
maintainer_score = clamp(log1p(contributors_90d) / log1p(10)) * 40

# B) Maintainer bench depth (0-30 points)
# Count contributors with >5% of top's work as "real maintainers"
significant_maintainers = [count where contrib > 0.05 * top_contrib]
bench_score = clamp(log1p(significant_maintainers) / log1p(5)) * 30

# C) Bus factor / ownership distribution (0-30 points)
top_share = top_contributor_work / total_work
if top_share > 0.70:
    bus_score = 10   # High risk (solo)
elif top_share > 0.50:
    bus_score = 20   # Medium risk (dominant)
elif top_share < 0.15:
    bus_score = 15   # Too distributed (unclear ownership)
else:
    bus_score = 30   # Healthy (20-50%)

people_score = maintainer_score + bench_score + bus_score
```

**Key Improvements Over v1**:
- ❌ **Removed**: `len(contributors) * 3` (naive count)
- ✅ **Added**: Log-scaled active maintainers (recent contributors_90d)
- ❌ **Removed**: `top_contrib / 100` (broken formula, saturates at 10)
- ✅ **Added**: Bench depth (how many significant beyond top?)
- ❌ **Removed**: Top 2 commits / total (noisy, unfair to hero maintainers)
- ✅ **Added**: Ownership distribution sweet spot (20-50% ideal for top maintainer)

**Bus Factor Logic**:
- Solo (>70% by one person) = **Risky** (10 pts)
- Dominant leader (50-70%) = **Medium risk** (20 pts)
- Healthy distribution (20-50%) = **Best** (30 pts)
- Too fragmented (<15% top) = **Unclear ownership** (15 pts)

**What We Have**:
- ✅ contributors (top 10, with contribution counts)
- ✅ contributors_90d (unique recent contributors)

**Future Enhancements** (for true maintainer tracking):
- 📊 Active maintainers (who merged PRs in last 90d)
- 📊 Unique reviewers (who reviewed PRs)
- 📊 Maintainer actions (not just commits - merges, reviews, triage)
- 📊 Bus factor via merge distribution (not commit distribution)
- 📊 Presence of CODEOWNERS, MAINTAINERS file, governance docs
- 📊 Issue/PR response coverage (how many maintainers respond, not just one)

---

## Health Label Thresholds

```python
if health_score >= 0.70:  # 70+
    label = "alive"
elif health_score >= 0.40:  # 40-70
    label = "steady"
else:  # <40
    label = "decaying"
```

**What "alive" means now** (≥70):
- Recent maintainer event (< 21 days)
- Good PR velocity (15+ merged in 60d)
- Active contributors (10+ in 90d)
- Keeping up with issues (closing ≥ opening)
- Recent release (< 90 days)

---

## Example Scoring Scenarios

### Scenario A: "Early Gem"
```
Repository: Small but active library
- Stars: 1,200
- Forks: 150
- PRs merged (60d): 25
- Contributors (90d): 8
- Days since push: 3
- Days since release: 15
- Issues: 12 opened, 14 closed
- Top contributor: 45% of work, 4 significant others

Scores:
- Popularity: 25 (LOW - not yet discovered)
- Health: 82 (ALIVE - very active, responsive)
- People: 71 (HIGH - good team, healthy distribution)

Discovery Pattern: EARLY GEM ✨
```

### Scenario B: "Zombie"
```
Repository: Once-popular framework
- Stars: 25,000
- Forks: 3,500
- PRs merged (60d): 2
- Contributors (90d): 1
- Days since push: 120
- Days since release: 365
- Issues: 45 opened, 8 closed
- Top contributor: 85% of work (solo)

Scores:
- Popularity: 78 (HIGH - well-known)
- Health: 18 (DECAYING - inactive, unresponsive)
- People: 22 (LOW - solo maintainer, bus factor)

Discovery Pattern: ZOMBIE ⚠️
```

### Scenario C: "Sustainable Workhorse"
```
Repository: Mature infrastructure tool
- Stars: 8,500
- Forks: 1,200
- PRs merged (60d): 18
- Contributors (90d): 12
- Days since push: 7
- Days since release: 45
- Issues: 20 opened, 22 closed
- Top contributor: 35% of work, 6 significant others

Scores:
- Popularity: 62 (MEDIUM - solid adoption)
- Health: 75 (ALIVE - steady maintenance)
- People: 84 (HIGH - strong team, low bus factor)

Discovery Pattern: SUSTAINABLE 🏗️
```

---

## Comparison: v1 vs v2

| Aspect | v1 (Naive) | v2 (Robust) |
|--------|------------|-------------|
| **Recency** | days_since_push / 60 | Last maintainer event, exponential decay |
| **Activity** | commits_30d (gameable) | prs_merged_60d + contributors_90d (robust) |
| **Normalizers** | Fixed (60, 80, 20, 30) | Adaptive percentiles (genre-aware) |
| **Responsiveness** | closed/opened ratio | Issue throughput + release cadence |
| **People** | Contributor count * 3 | Active maintainers + bench + bus factor |
| **Popularity** | Linear stars/100 | Logarithmic (handles 100 to 100k+) |
| **Bus Factor** | Top 2 commits / total | Ownership sweet spot (20-50% ideal) |

---

## Genre-Aware Scoring (Future)

Different project types need different weights:

### Library/SDK
- **Health**: 35% (responsiveness critical)
- **People**: 30% (sustainability matters)
- **Popularity**: 20% (adoption)
- Normalizers: releases matter more, commits matter less

### Framework/Tooling
- **Health**: 30%
- **Popularity**: 30%
- **People**: 25%
- Normalizers: balanced

### Infrastructure/DevOps
- **Health**: 35% (uptime, security patches)
- **People**: 35% (operational trust)
- **Popularity**: 15%
- Normalizers: stability > velocity

### Model (HuggingFace)
- **Popularity**: 45% (downloads, usage)
- **Health**: 25% (updates, versions)
- **People**: 15% (less critical)
- Normalizers: burst activity OK, long quiet periods normal

### Dataset
- **Popularity**: 50% (citations, usage)
- **People**: 25% (stewardship)
- **Health**: 15% (updates rare but maintenance matters)
- Normalizers: very low expected activity

---

## What We Need for Genre Detection

**Infer genre from**:
- ✅ Topics/tags
- ✅ HuggingFace repo type
- 📊 File presence (package.json → library, Dockerfile → infra)
- 📊 README keywords (paper, arxiv → research)
- 📊 License type

---

## Immediate Next Steps

**Phase 1: Quick Wins** (current implementation)
1. ✅ Use logarithmic popularity scaling
2. ✅ Use PR merges instead of commits for activity
3. ✅ Fix People score (bench + bus factor)
4. ✅ Use last maintainer event for recency

**Phase 2: Better Data** (requires new API calls)
1. 📊 Fetch time-to-response metrics (issues + PRs)
2. 📊 Fetch last maintainer comment timestamp
3. 📊 Fetch maintainer list (who has merge rights)
4. 📊 Fetch unique PR reviewers

**Phase 3: Genre-Aware** (requires classification)
1. 📊 Detect project genre
2. 📊 Apply genre-specific weights
3. 📊 Use genre-specific normalizers (percentiles within genre)

**Phase 4: Trend Tracking** (requires historical data)
1. 📊 Store scores over time
2. 📊 Compute star velocity
3. 📊 Detect momentum shifts
4. 📊 Track backlog growth

---

## Testing the New Scoring

Run on your current data:
```bash
./pipeline/build.sh
```

Then check examples:
```python
import json
data = json.load(open('web/public/data/projects.json'))

# Find "early gems"
gems = [p for p in data['projects'] 
        if p['health_score'] > 70 and p['popularity_score'] < 40 and p['people_score'] > 60]

# Find "zombies"
zombies = [p for p in data['projects']
           if p['health_score'] < 30 and p['popularity_score'] > 70]

# Find "sustainable"
sustainable = [p for p in data['projects']
               if p['people_score'] > 75 and p['health_score'] > 60]
```

---

## Fields We Have vs Need

### Currently Available ✅
- stars, forks
- days_since_push, days_since_release
- commits_30d, commits_90d
- contributors_90d
- prs_merged_60d
- issues_opened_60d, issues_closed_60d
- top 10 contributors with contribution counts

### Nice-to-Have 📊
- Median time to first response (issues)
- Median time to first response (PRs)
- Median time to merge PR
- Median time to close issue
- Last maintainer comment timestamp
- Maintainer list (who has merge rights)
- Unique PR reviewers (90d)
- Open issue count (for backlog tracking)
- Star history (for velocity)
- Downloads (npm, pypi, HF)

### Future (Ambitious) 🚀
- Reverse dependencies
- Package download trends
- Security audit results
- Test coverage
- Documentation coverage
- Governance documents (CODEOWNERS, etc.)
- Community health score (GitHub's built-in)

