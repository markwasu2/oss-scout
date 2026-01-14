/**
 * Semantic search utilities using @xenova/transformers
 * Client-side embedding generation and similarity computation
 */

import { pipeline, env } from '@xenova/transformers';

// Disable local model storage (use cache in temp dir)
env.allowLocalModels = false;

// Singleton model instance
let embedder: any = null;
let modelLoading: Promise<any> | null = null;

/**
 * Load the embedding model (cached singleton)
 * Uses all-MiniLM-L6-v2 to match server-side embeddings
 */
export async function loadEmbedder() {
  if (embedder) return embedder;
  if (modelLoading) return modelLoading;

  modelLoading = (async () => {
    console.log('Loading embedding model...');
    embedder = await pipeline('feature-extraction', 'Xenova/all-MiniLM-L6-v2');
    console.log('✓ Embedding model ready');
    return embedder;
  })();

  return modelLoading;
}

/**
 * Generate embedding for a text query
 */
export async function embedQuery(text: string): Promise<Float32Array> {
  const model = await loadEmbedder();
  const output = await model(text, { pooling: 'mean', normalize: true });
  return output.data;
}

/**
 * Compute cosine similarity between two vectors
 */
export function cosineSimilarity(a: number[] | Float32Array, b: number[] | Float32Array): number {
  let dotProduct = 0;
  let normA = 0;
  let normB = 0;

  for (let i = 0; i < a.length; i++) {
    dotProduct += a[i] * b[i];
    normA += a[i] * a[i];
    normB += b[i] * b[i];
  }

  if (normA === 0 || normB === 0) return 0;
  return dotProduct / (Math.sqrt(normA) * Math.sqrt(normB));
}

/**
 * Find top K similar items given a query vector
 */
export function findTopSimilar<T>(
  queryVec: number[] | Float32Array,
  items: T[],
  getVector: (item: T) => number[] | undefined,
  k: number = 20
): Array<{ item: T; similarity: number }> {
  const scored = items
    .map((item) => {
      const vec = getVector(item);
      if (!vec) return null;
      const similarity = cosineSimilarity(queryVec, vec);
      return { item, similarity };
    })
    .filter((x): x is { item: T; similarity: number } => x !== null)
    .sort((a, b) => b.similarity - a.similarity);

  return scored.slice(0, k);
}

/**
 * Embeddings data structure
 */
export type EmbeddingsData = {
  generated_at: string;
  model: string;
  dimensions: number;
  count: number;
  embeddings: Array<{
    id: string;
    source: string;
    vec: number[];
  }>;
};

/**
 * Load embeddings from public data folder
 */
export async function loadEmbeddings(): Promise<EmbeddingsData | null> {
  try {
    const response = await fetch('/data/embeddings.json');
    if (!response.ok) {
      console.warn('Embeddings file not found');
      return null;
    }
    const data = await response.json();
    console.log(`✓ Loaded ${data.count} embeddings (${data.dimensions} dims)`);
    return data;
  } catch (error) {
    console.error('Failed to load embeddings:', error);
    return null;
  }
}

