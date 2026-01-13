# OSS Scout - Implementation Summary

## System Architecture

**Smart Funnel Approach** (not "fetch everything"):
1. **Candidate Generation** - Pull targeted high-quality projects (~1-2k)
2. **Quality Gates** - Filter out noise (forks, archived, inactive)
3. **Health Signals** - Compute comprehensive metrics with caching
4. **Enrichment** - Add 3 orthogonal scores
5. **User Filtering** - Let UI slicing do the heavy lifting

---

## Features Implemented

### 1. Comprehensive Health Signals (with Caching)

**Cache System:**
- Location: `data/cache/github_health.json`
- TTL: 12 hours
- Saves API calls and speeds up reruns

**Health Metrics per GitHub Repo:**
```json
{
  "days_since_push": 0,
  "days_since_release": 6,
  "commits_30d": 91,
  "commits_90d": 323,
  "contributors_90d": 26,
  "prs_merged_60d": 72,
  "issues_opened_60d": 13,
  "issues_closed_60d": 3,
  "health_score": 0.58 (0-1),
  "health_label": "steady" | "alive" | "decaying"
}
```

**Health Score Formula:**
- Recency: 30% (1 - days_since_push/60)
- Commits: 20% (log-normalized)
- Contributors: 20% (log-normalized)
- PR velocity: 15% (log-normalized)
- Issue resolution: 15% (closed/opened ratio)

**Health Labels:**
- `alive`: health_score >= 0.70
- `steady`: 0.40 <= health_score < 0.70
- `decaying`: health_score < 0.40

---

### 2. Quality Gates (GitHub)

**Automatic Filtering:**
- ❌ **Forks** - Excluded by default
- ❌ **Archived repos** - Excluded
- ❌ **No license** - Excluded
- ❌ **No description** - Excluded (proxy for no README)
- ❌ **Inactive** - < 5 commits in 90 days excluded

**Benefits:**
- Dramatically improves signal-to-noise
- Focuses on maintained, documented projects
- Reduces API load

---

### 3. Quality Gates (Hugging Face)

**Minimum Thresholds:**
- Downloads >= 100
- Likes >= 2
- Age <= 365 days

**Configurable per use case**

---

### 4. Three Orthogonal Scores

Instead of one opaque "score", we compute:

**Popularity Score (0-100):**
- GitHub: Stars + forks
- HF: Downloads + likes

**Health Score (0-100):**
- GitHub: From comprehensive health signals
- HF: Recency-based estimate

**People Score (0-100):**
- GitHub: Contributor count + strength + diversity (bus factor)
- HF: Downloads as proxy

**Discovery Patterns Unlocked:**
- **Early Gems**: High health, low popularity
- **Zombies**: High popularity, low health
- **Future Leaders**: High people score, moderate popularity
- **Sustainable**: High people score, high health

---

### 5. Smart Corpus Management

**Configurable Scale:**
```json
{
  "max_total_repos": 2000,
  "github": {
    "topics": [...10 topics],
    "per_topic_limit": 150,
    "min_stars": 100
  },
  "huggingface": {
    "per_query_limit": 80
  }
}
```

**Target Scale:**
- GitHub: 10 topics × 150 repos = ~1,500 repos (after filtering)
- HF: 9 queries × 80 models = ~720 models
- Total: ~1,500-2,000 high-quality items

**Why This Scale:**
- Large enough for discovery
- Small enough to rank meaningfully
- Fast to fetch and update
- Manageable corpus size

---

### 6. Efficient API Usage

**Techniques:**
- **Caching**: 12-hour TTL for health signals
- **Link Header Parsing**: Count commits without fetching all
- **Sampling**: Approximate contributors from first page
- **Rate Limiting**: Sleep between calls
- **Deduplication**: Track seen repos

**API Calls per Repo:**
- Search: 1 call per topic
- Contributors: 1 call per repo
- Health signals: ~4-5 calls per repo (cached)
- Total: ~6-7 calls per repo (first run), ~2 calls (cached runs)

---

### 7. Feed ↔ Graph Integration

**Bidirectional Navigation:**
- Graph → Feed: Double-click contributor → See their projects
- Feed → Graph: Click project → View in network
- Top Contributors sidebar in feed
- URL params: `?contributor=username`

**Discovery Loop:**
1. Filter feed by use case
2. View in graph → See contributors
3. Click contributor → Back to feed with their work
4. Find related projects via shared maintainers

---

### 8. UI Features

**Sorting:**
- Popularity
- Health
- People
- Newest

**Filtering:**
- Health: Alive / Steady / Decaying
- Source: GitHub / HF / All
- Use cases: agents, llm, inference, etc.
- Activity: Days since update slider
- Contributor: Filter by specific person

**Visual Indicators:**
- 3-score mini display on cards (POP/HLT/PPL)
- Health label badges (ALIVE/STEADY/DECAYING)
- Color-coded health bars
- Health metrics in detail panel

---

## Configuration

**Main Config** (`pipeline/config.json`):
```json
{
  "since_days": 90,
  "max_total_repos": 2000,
  "github": {
    "topics": ["llm", "diffusion", "inference", "agents", "eval", "multimodal", "transformers", "rag", "vector-database", "mlops"],
    "min_stars": 100,
    "per_topic_limit": 150,
    "top_contributors": 10,
    "quality_gates": {
      "exclude_forks": true,
      "exclude_archived": true,
      "require_license": true,
      "require_readme": true,
      "min_commits_90d": 5
    }
  },
  "huggingface": {
    "queries": ["llm", "diffusion", "agent", "embedding", "vlm", "text-generation", "image-generation", "vision", "audio"],
    "per_query_limit": 80,
    "quality_gates": {
      "min_downloads": 100,
      "min_likes": 2,
      "max_age_days": 365
    }
  }
}
```

---

## Usage

### One-Command Refresh:
```bash
./pipeline/build.sh
```

This:
1. Fetches projects from GitHub (with quality gates)
2. Fetches models from HuggingFace (with quality gates)
3. Computes health signals (with caching)
4. Computes 3 scores
5. Generates contributor graph
6. Copies data to web UI
7. Saves health cache for next run

### First Run:
- ~10-15 minutes (fetching health signals)
- Creates cache

### Subsequent Runs:
- ~3-5 minutes (uses cache for repos fetched < 12h ago)
- Only fetches health for new repos

---

## Data Files

**Generated:**
- `data/projects.json` - All projects with scores
- `data/cache/github_health.json` - Health signal cache
- `web/public/data/projects.json` - Copy for web UI
- `web/public/data/graph.json` - Contributor network

**Cached:**
- Health signals (12h TTL)
- Persists across runs

---

## Why This Beats Other Tools

**Most discovery tools:**
- ❌ One blended "score" (opaque)
- ❌ Static metrics only (stars, forks)
- ❌ No health/velocity signals
- ❌ Try to fetch "everything" (noisy)

**OSS Scout:**
- ✅ 3 independent scores (transparent)
- ✅ Velocity metrics (commits, PRs, issues in 60d)
- ✅ People quality (not just count, but diversity)
- ✅ Quality gates (high signal-to-noise)
- ✅ Actionable filters (find gems, spot zombies)
- ✅ Graph integration (discover via people)

---

## Next Steps

**Potential Enhancements:**
1. **Semantic Search** - Embed descriptions, search by intent
2. **Rolling Crawler** - Update top 200/day, maintain 20k corpus
3. **GraphQL Batching** - Faster health signal fetching
4. **SQLite Storage** - Better than JSON for large corpus
5. **Trend Detection** - Track score changes over time
6. **Export/Share** - Save queries, share filtered views

**Current State:**
- ✅ Production-ready for 1-2k projects
- ✅ Fast refresh with caching
- ✅ High-quality signal
- ✅ Ready for daily use

