// ═══ Search & Smart Albums Module (R1 CLIP Semantic Search) ═══

function filterAndSortClipResults(results, threshold) {
  if (!Array.isArray(results) || typeof threshold !== 'number') return [];
  return results
    .filter(item => typeof item.score === 'number' && item.score >= threshold && !isNaN(item.score))
    .sort((a, b) => b.score - a.score);
}

const Search = (() => {
  let isSemanticSearchActive = false;
  let lastSearchResults = [];

  function init() {
    const searchInput = document.getElementById('search-input');
    if (searchInput) {
      searchInput.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') {
          const query = searchInput.value.trim();
          if (query.length > 0 && isSemanticQuery(query)) {
            e.preventDefault();
            await runSemanticSearch(query);
          }
        }
      });
    }
  }

  function isSemanticQuery(query) {
    if (!query) return false;
    const words = query.trim().split(/\s+/);
    return words.length >= 2 || ['собака', 'пляж', 'закат', 'горы', 'семья', 'dog', 'beach', 'sunset', 'mountain', 'family'].includes(words[0].toLowerCase());
  }

  function clearSemanticSearch() {
    isSemanticSearchActive = false;
    lastSearchResults = [];
    if (typeof Gallery !== 'undefined' && typeof Gallery.clearSemanticSearch === 'function') {
      Gallery.clearSemanticSearch();
    }
  }

  async function runSemanticSearch(query, limit = 100) {
    if (!query || typeof query !== 'string' || query.trim() === '') {
      clearSemanticSearch();
      return [];
    }

    try {
      if (typeof window !== 'undefined' && window.API && typeof window.API.searchClipSemantic === 'function') {
        const rawResults = await window.API.searchClipSemantic(query, limit);
        const filtered = filterAndSortClipResults(rawResults, 0.1);
        lastSearchResults = filtered;
        isSemanticSearchActive = true;

        if (typeof Gallery !== 'undefined' && typeof Gallery.setSemanticSearchResults === 'function') {
          Gallery.setSemanticSearchResults(filtered);
        }
        return filtered;
      }
    } catch (err) {
      if (typeof Logger !== 'undefined') {
        Logger.error('Search', `Semantic search error for query "${query}"`, err);
      }
    }
    return [];
  }

  return {
    init,
    filterAndSortClipResults,
    runSemanticSearch,
    clearSemanticSearch,
    isSemanticQuery,
    get isSemanticSearchActive() { return isSemanticSearchActive; },
    get lastSearchResults() { return lastSearchResults; }
  };
})();

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { filterAndSortClipResults, Search };
}

if (typeof window !== 'undefined') {
  window.filterAndSortClipResults = filterAndSortClipResults;
  window.Search = Search;
}
