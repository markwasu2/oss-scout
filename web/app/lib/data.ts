/**
 * Data loading abstraction for sharded static index
 * Supports manifest, shards, and lazy detail loading
 */

export type IndexItem = {
  key: string;
  source: string;
  id: string;
  title: string;
  org: string;
  url: string;
  updated_at: string;
  tags_top: string[];
  license: string;
  health_label: string;
  health_score: number;
  momentum_label: string;
  momentum_score: number;
  popularity: {
    stars: number;
    forks: number;
    downloads: number;
    likes: number;
  };
  scores: {
    total: number;
    popularity: number;
    health: number;
    people: number;
  };
  why: string;
};

export type Manifest = {
  generated_at: string;
  counts: {
    total: number;
    github: number;
    hf: number;
  };
  facets: {
    tags: Record<string, number>;
    source: Record<string, number>;
    health_label: Record<string, number>;
    [key: string]: Record<string, number>;
  };
  shards: Array<{
    type: string;
    name: string;
    file: string;
    count: number;
  }>;
};

export type DetailItem = {
  key: string;
  item: any; // Full project object
};

// In-memory caches
const shardCache = new Map<string, IndexItem[]>();
const detailCache = new Map<string, DetailItem>();
let manifestCache: Manifest | null = null;

/**
 * Load manifest (cached)
 */
export async function loadManifest(): Promise<Manifest> {
  if (manifestCache) return manifestCache;

  try {
    const response = await fetch('/data/index/manifest.json');
    if (!response.ok) {
      throw new Error(`Failed to load manifest: ${response.statusText}`);
    }
    manifestCache = await response.json();
    console.log(`✓ Loaded manifest: ${manifestCache!.counts.total} total items`);
    return manifestCache!;
  } catch (error) {
    console.error('Failed to load manifest:', error);
    throw error;
  }
}

/**
 * Load a shard file (cached)
 */
export async function loadShard(shardFile: string): Promise<IndexItem[]> {
  if (shardCache.has(shardFile)) {
    return shardCache.get(shardFile)!;
  }

  try {
    const response = await fetch(`/data/index/shards/${shardFile}`);
    if (!response.ok) {
      console.warn(`Shard not found: ${shardFile}`);
      return [];
    }
    const items: IndexItem[] = await response.json();
    shardCache.set(shardFile, items);
    console.log(`✓ Loaded shard: ${shardFile} (${items.length} items)`);
    return items;
  } catch (error) {
    console.error(`Failed to load shard ${shardFile}:`, error);
    return [];
  }
}

/**
 * Load multiple shards and merge
 */
export async function loadShards(shardFiles: string[]): Promise<IndexItem[]> {
  const shards = await Promise.all(shardFiles.map((file) => loadShard(file)));
  
  // Deduplicate by key
  const itemsMap = new Map<string, IndexItem>();
  for (const shard of shards) {
    for (const item of shard) {
      itemsMap.set(item.key, item);
    }
  }
  
  return Array.from(itemsMap.values());
}

/**
 * Load detail for a specific item (cached)
 */
export async function loadDetail(key: string): Promise<DetailItem | null> {
  if (detailCache.has(key)) {
    return detailCache.get(key)!;
  }

  try {
    // Convert key to slug: "github:owner/repo" -> "github__owner__repo.json"
    const [source, id] = key.split(':', 2);
    const slug = `${source}__${id.replace(/\//g, '__')}.json`;
    
    const response = await fetch(`/data/items/${slug}`);
    if (!response.ok) {
      console.warn(`Detail not found: ${key}`);
      return null;
    }
    const detail: DetailItem = await response.json();
    detailCache.set(key, detail);
    return detail;
  } catch (error) {
    console.error(`Failed to load detail ${key}:`, error);
    return null;
  }
}

/**
 * Get shard files for a given source filter
 */
export function getShardsForSource(source: 'all' | 'github' | 'huggingface', manifest: Manifest): string[] {
  if (source === 'all') {
    return manifest.shards
      .filter((s) => s.type === 'source')
      .map((s) => s.file);
  }
  
  const shard = manifest.shards.find((s) => s.type === 'source' && s.name === source);
  return shard ? [shard.file] : [];
}

/**
 * Get shard file for a specific lens
 */
export function getShardForLens(lensId: string, manifest: Manifest): string | null {
  const shard = manifest.shards.find((s) => s.type === 'lens' && s.name === lensId);
  return shard ? shard.file : null;
}

/**
 * Get shard file for a specific tag (if exists)
 */
export function getShardForTag(tag: string, manifest: Manifest): string | null {
  const shard = manifest.shards.find((s) => s.type === 'tag' && s.name === tag);
  return shard ? shard.file : null;
}

/**
 * Clear all caches (useful for refresh)
 */
export function clearCaches() {
  shardCache.clear();
  detailCache.clear();
  manifestCache = null;
}

