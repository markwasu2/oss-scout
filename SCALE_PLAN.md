# OSS Scout - Scale Architecture Plan

> **Current state:** ~119 items, single JSON (~6MB with cache)
> 
> **Question:** How big should this get, and what architecture changes are needed?

---

## Decision Tree: Pick Your Scale Tier

### Tier 1: Small (500-1,000 items)
**Characteristics:**
- Single `projects.json` file
- Client-side filtering only
- No pagination needed
- ~10-15 MB total
- Load time: < 3 seconds

**Architecture:** ✅ **CURRENT** (no changes needed)
```
web/public/data/projects.json  (all data, one file)
```

**Good for:**
- Curated, high-quality projects only
- Deep filtering within a manageable set
- Fast iteration without infrastructure

**Limits:**
- Must be selective about what gets included
- Quality gates must be strict

---

### Tier 2: Medium (1,000-5,000 items)
**Characteristics:**
- Single JSON still works but feels slow
- Need UI pagination
- ~30-50 MB
- Load time: 5-8 seconds

**Architecture:** Consider this when > 1k items
```
web/public/data/projects.json  (still one file)
+ Add virtual scrolling in UI
+ Add pagination (show 50 at a time)
```

**Changes needed:**
1. **UI: Virtual scrolling**
   ```tsx
   // Use react-window or similar
   import { FixedSizeList } from 'react-window';
   ```

2. **UI: Paginate lens results**
   ```tsx
   const pageSize = 50;
   const [page, setPage] = useState(1);
   const pagedResults = filteredProjects.slice((page-1)*pageSize, page*pageSize);
   ```

3. **Optional: Lazy-load images/avatars**

**Trade-offs:**
- Still simple (no build complexity)
- Works fine for most use cases
- But: initial load getting sluggish

---

### Tier 3: Large (5,000-20,000 items)
**Characteristics:**
- Single JSON too slow
- Need to split data
- ~100-300 MB if in one file
- Load time: 15+ seconds (unacceptable)

**Architecture:** Split into index + details
```
web/public/data/
  index.json              (lightweight: just id, name, scores, tags)
  details/
    {id}.json             (full project data per item)
```

**Migration steps:**

1. **Split fetch.py output:**
   ```python
   # pipeline/fetch.py
   def save_projects_scaled(projects):
       # Save lightweight index
       index = {
           "generated_at": datetime.utcnow().isoformat(),
           "count": len(projects),
           "items": [
               {
                   "id": p["id"],
                   "source": p["source"],
                   "name": p["name"],
                   "full_name": p.get("full_name"),
                   "popularity_score": p["popularity_score"],
                   "health_score": p["health_score"],
                   "people_score": p["people_score"],
                   "tags": p.get("tags", []),
                   "updated_at": p["updated_at"]
               }
               for p in projects
           ]
       }
       
       Path("web/public/data/index.json").write_text(json.dumps(index))
       
       # Save full details per project
       details_dir = Path("web/public/data/details")
       details_dir.mkdir(exist_ok=True)
       for p in projects:
           detail_file = details_dir / f"{p['id'].replace('/', '--')}.json"
           detail_file.write_text(json.dumps(p, indent=2))
   ```

2. **Update UI to lazy-load:**
   ```tsx
   // web/app/page.tsx
   
   // Load index on mount
   useEffect(() => {
       fetch("/data/index.json")
           .then(r => r.json())
           .then(d => setIndex(d.items));
   }, []);
   
   // Load details on selection
   const selectProject = async (id: string) => {
       const detailId = id.replace('/', '--');
       const detail = await fetch(`/data/details/${detailId}.json`).then(r => r.json());
       setSelectedProject(detail);
   };
   ```

**Trade-offs:**
- More complex build process
- But: fast initial load + progressive enhancement
- Good for: comprehensive coverage

---

### Tier 4: Very Large (20,000+ items)
**Characteristics:**
- Need database + API
- Real backend required
- Server-side filtering/sorting

**Architecture:** Next.js API routes + SQLite/PostgreSQL
```
web/
  app/
    api/
      projects/route.ts        (GET /api/projects?lens=hidden-gems&tag=video)
      projects/[id]/route.ts   (GET /api/projects/:id)
  lib/
    db.ts                      (SQLite connection)
```

**Migration steps:**

1. **Add database:**
   ```bash
   npm install better-sqlite3
   ```

2. **Create schema:**
   ```sql
   CREATE TABLE projects (
       id TEXT PRIMARY KEY,
       source TEXT,
       name TEXT,
       full_name TEXT,
       description TEXT,
       popularity_score REAL,
       health_score REAL,
       people_score REAL,
       tags TEXT,  -- JSON array
       data TEXT   -- JSON blob
   );
   CREATE INDEX idx_tags ON projects(tags);
   CREATE INDEX idx_scores ON projects(popularity_score, health_score, people_score);
   ```

3. **Ingest pipeline → DB:**
   ```python
   # pipeline/fetch.py
   import sqlite3
   
   def save_to_db(projects):
       conn = sqlite3.connect("web/data/scout.db")
       for p in projects:
           conn.execute("""
               INSERT OR REPLACE INTO projects VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           """, (
               p["id"], p["source"], p["name"], p.get("full_name"),
               p.get("description"), p["popularity_score"],
               p["health_score"], p["people_score"],
               json.dumps(p.get("tags")), json.dumps(p)
           ))
       conn.commit()
   ```

4. **API route:**
   ```typescript
   // web/app/api/projects/route.ts
   import Database from 'better-sqlite3';
   
   export async function GET(request: Request) {
       const { searchParams } = new URL(request.url);
       const lens = searchParams.get('lens');
       const tag = searchParams.get('tag');
       
       const db = new Database('data/scout.db', { readonly: true });
       
       let query = 'SELECT * FROM projects WHERE 1=1';
       if (tag) query += ` AND tags LIKE '%${tag}%'`;
       // Add lens logic...
       
       const results = db.prepare(query).all();
       return Response.json(results);
   }
   ```

**Trade-offs:**
- Full infrastructure (hosting, DB, backups)
- But: can scale to millions
- Good for: production SaaS

---

## Recommendation: Start at Tier 1-2, Plan for Tier 3

### Right Now (Phase 1)
- Stay at **Tier 1** (< 1k items)
- Focus on quality over quantity
- Strict quality gates
- Manual curation

### When You Hit 1k (Phase 2)
- Move to **Tier 2**
- Add pagination in UI
- Keep single JSON

### When You Hit 5k (Phase 3)
- Move to **Tier 3** (index + details split)
- This is the sweet spot for most tools
- Keeps deployment simple (static export)

### Only If Needed (Phase 4)
- Move to **Tier 4** (database + API)
- This is a big jump (requires hosting, not just GitHub Pages)
- Only do this if you're building a real product

---

## Current Bottlenecks (Tier 1 → Tier 2 Transition)

| Metric | Current | Tier 1 Limit | Tier 2 Limit |
|--------|---------|--------------|--------------|
| Items | ~119 | 1,000 | 5,000 |
| JSON size | ~6 MB | ~15 MB | ~50 MB |
| Load time | ~1s | ~3s | ~8s (needs pagination) |
| Render time | <100ms | ~500ms | ~2s (needs virtual scroll) |

**When to upgrade:**
- If `projects.json` > 10 MB → move to Tier 2
- If `projects.json` > 40 MB → move to Tier 3

---

## Action Plan

### This Month
- [ ] Stay at Tier 1
- [ ] Set max items in `config.json`: `"max_total_repos": 1000`
- [ ] Focus on quality gates

### When Approaching 1k
- [ ] Add pagination UI
- [ ] Test with 2k items locally
- [ ] Benchmark load time

### When Approaching 5k
- [ ] Implement index/details split
- [ ] Update `pipeline/fetch.py` to output split format
- [ ] Update UI to lazy-load details
- [ ] Deploy and test

### Only If Scaling to Production
- [ ] Evaluate Next.js hosting (Vercel, Railway, Fly.io)
- [ ] Choose DB (SQLite for simplicity, Postgres for scale)
- [ ] Implement API routes
- [ ] Add caching (Redis or similar)
- [ ] Monitor performance

---

## Cost Estimates (if you move to Tier 4)

| Component | Tier 1-3 | Tier 4 (SaaS) |
|-----------|----------|---------------|
| Hosting | Free (GitHub Pages) | $5-20/mo (Vercel/Railway) |
| Database | N/A | Free (SQLite) or $5-15/mo (Postgres) |
| Caching | N/A | $5/mo (Redis) |
| CDN | Free (GitHub) | Included or $5/mo |
| **Total** | **$0/mo** | **$15-50/mo** |

---

## Decision: Your Current Path

Based on your feedback, I recommend:

**Target: Tier 2 (1-5k projects)**
- Reason: Broad coverage without infrastructure complexity
- Timeline: Can stay here for months/years
- Exit strategy: If it takes off, Tier 3 is easy upgrade

**Quality over quantity:**
- Better to have 1,000 excellent projects than 10,000 mediocre ones
- Heavy manual curation via overrides
- Strict quality gates

**Implementation:**
Set this in `pipeline/config.json`:
```json
{
  "max_total_repos": 2000,
  "github": {
    "min_stars": 200,
    "per_topic_limit": 100
  },
  "huggingface": {
    "per_query_limit": 50
  }
}
```

Then add pagination in the UI once you hit 500+ items.

