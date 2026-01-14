/**
 * Data adapter: loads from sharded index or falls back to legacy projects.json
 * Provides a unified interface for the UI
 */

import { loadManifest, loadShards, loadDetail, getShardsForSource, getShardForLens, type IndexItem, type Manifest } from './data';

export type LegacyProject = any; // Full project object from old format

export type AdapterState = {
  mode: 'sharded' | 'legacy';
  manifest?: Manifest;
  items: IndexItem[];
  totalCount: number;
  generatedAt: string;
};

/**
 * Initialize data loading - tries sharded first, falls back to legacy
 */
export async function initializeData(): Promise<AdapterState> {
  // TEMPORARY: Force legacy mode while pipeline generates sharded index
  // TODO: Re-enable sharded mode after pipeline completes
  const FORCE_LEGACY = true;
  
  if (!FORCE_LEGACY) {
    // Try sharded index first
    try {
      const manifest = await loadManifest();
      // Load initial shard (github by default)
      const initialShards = getShardsForSource('github', manifest);
      const items = await loadShards(initialShards);
      
      console.log(`✓ Using SHARDED mode: ${items.length} items loaded`);
      
      return {
        mode: 'sharded',
        manifest,
        items,
        totalCount: manifest.counts.total,
        generatedAt: manifest.generated_at,
      };
    } catch (error) {
      console.warn('⚠️ Sharded index not available, falling back to legacy format');
    }
  }
  
  // Fallback to legacy projects.json
  console.log('⚠️ Using LEGACY mode (sharded index not ready)');
  console.log('Run ./pipeline/build.sh to generate sharded index');
  
  try {
    const response = await fetch('/data/projects.json');
    if (!response.ok) {
      throw new Error(`Legacy projects.json not found: ${response.statusText}`);
    }
    const data = await response.json();
    
    // Convert legacy projects to index items
    const items = data.projects.map(legacyToIndexItem);
    
    console.log(`✓ Loaded ${items.length} projects in legacy mode`);
    
    return {
      mode: 'legacy',
      items,
      totalCount: data.count,
      generatedAt: data.generated_at,
    };
  } catch (legacyError) {
    console.error('❌ Failed to load any data format:', legacyError);
    throw new Error('No data available. Run ./pipeline/build.sh to generate data.');
  }
}

/**
 * Load items for a specific lens (sharded mode only)
 */
export async function loadLensItems(lensId: string, manifest: Manifest): Promise<IndexItem[]> {
  const lensShardFile = getShardForLens(lensId, manifest);
  if (lensShardFile) {
    return await loadShards([lensShardFile]);
  }
  // Fallback: return empty (will filter client-side)
  return [];
}

/**
 * Load items for a specific source
 */
export async function loadSourceItems(source: 'all' | 'github' | 'huggingface', manifest: Manifest): Promise<IndexItem[]> {
  const shardFiles = getShardsForSource(source, manifest);
  return await loadShards(shardFiles);
}

/**
 * Convert legacy project to index item
 */
function legacyToIndexItem(project: LegacyProject): IndexItem {
  // Build "why" string
  const parts = [];
  if (project.momentum?.momentum_label === 'rising') parts.push('Rising');
  else if (project.health?.health_label === 'alive') parts.push('Alive');
  
  const contribCount = project.health?.contributors_90d || project.contributors?.length || 0;
  if (contribCount >= 5) parts.push('multi-maintainer');
  else if (contribCount >= 2) parts.push('team-maintained');
  
  const why = parts.slice(0, 4).join(' • ') || 'Open source project';
  
  // Extract license
  let license = 'unknown';
  if (project.hf?.license) {
    const lic = project.hf.license.toLowerCase();
    if (lic.includes('mit')) license = 'mit';
    else if (lic.includes('apache')) license = 'apache-2.0';
    else if (lic.includes('gpl')) license = 'gpl';
    else license = project.hf.license.substring(0, 20);
  } else if (project.tags?.includes('permissive')) {
    license = 'permissive';
  } else if (project.tags?.includes('restricted')) {
    license = 'restricted';
  }
  
  return {
    key: `${project.source}:${project.id}`,
    source: project.source,
    id: project.id,
    title: project.name,
    org: project.full_name?.split('/')[0] || '',
    url: project.url,
    updated_at: project.updated_at,
    tags_top: project.tags?.slice(0, 5) || [],
    license,
    health_label: project.health?.health_label || 'unknown',
    health_score: project.health_score || 0,
    momentum_label: project.momentum?.momentum_label || 'flat',
    momentum_score: project.momentum?.momentum_score || 0,
    popularity: {
      stars: project.stars || 0,
      forks: project.forks || 0,
      downloads: project.downloads || 0,
      likes: project.likes || 0,
    },
    scores: {
      total: project.score || 0,
      popularity: project.popularity_score || 0,
      health: project.health_score || 0,
      people: project.people_score || 0,
    },
    why,
  };
}

/**
 * Get full project details (supports both modes)
 */
export async function getProjectDetails(key: string, mode: 'sharded' | 'legacy', legacyProjects?: LegacyProject[]): Promise<LegacyProject | null> {
  if (mode === 'sharded') {
    const detail = await loadDetail(key);
    return detail?.item || null;
  } else {
    // Legacy mode: find in memory
    if (!legacyProjects) return null;
    return legacyProjects.find((p) => `${p.source}:${p.id}` === key) || null;
  }
}

