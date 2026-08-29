/**
 * Retrieval precision = distinct relevant document_ids retrieved / distinct document_ids retrieved.
 * No citations and no expected docs is a vacuous match (1); no citations with expected docs is 0.
 */
export function computePrecision(
  retrievedDocumentIds: string[],
  expectedDocumentIds: string[],
): number {
  const retrieved = [...new Set(retrievedDocumentIds)]
  if (retrieved.length === 0) {
    return expectedDocumentIds.length === 0 ? 1 : 0
  }
  const expected = new Set(expectedDocumentIds)
  const relevant = retrieved.filter((id) => expected.has(id))
  return relevant.length / retrieved.length
}
