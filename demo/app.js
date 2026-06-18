(function () {
  const data = window.QQ_DEMO_INDEX;
  const summaries = data.entities;
  const entityList = Object.entries(summaries).map(function (entry) {
    return Object.assign({ id: entry[0] }, entry[1]);
  });
  const identifierToIds = buildIdentifierIndex(entityList);
  window.QQ_DEMO_CHUNKS = window.QQ_DEMO_CHUNKS || {};
  window.QQ_DEMO_NAME_BUCKETS = window.QQ_DEMO_NAME_BUCKETS || {};
  const loadedBuckets = window.QQ_DEMO_CHUNKS;
  const loadedNameBuckets = window.QQ_DEMO_NAME_BUCKETS;
  const bucketLoads = {};
  const nameBucketLoads = {};
  const availableNameBuckets = (data.meta.counts && data.meta.counts.nameBuckets) || data.meta.nameBuckets || {};
  const SEARCH_RESULT_LIMIT = 24;
  const SHORT_LABEL_LIMIT = 18;
  const SHORT_LABEL_SLICE = 16;
  const IDENTIFIER_EXACT_RANK = 0;
  const NAME_EXACT_RANK = 1;
  const NAME_PREFIX_RANK = 2;
  const NAME_SUBSTRING_RANK = 3;
  const MULTILINGUAL_EXACT_RANK = 4;
  const MULTILINGUAL_PREFIX_RANK = 5;
  const MULTILINGUAL_SUBSTRING_RANK = 6;
  const RELATED_NAME_RANK = NAME_SUBSTRING_RANK;
  const GRAPH_WIDTH = 640;
  const GRAPH_HEIGHT = 420;
  const GRAPH_CENTER_X = GRAPH_WIDTH / 2;
  const GRAPH_CENTER_Y = GRAPH_HEIGHT / 2;
  const DEFAULT_GRAPH_VIEWBOX = "0 0 640 420";
  const GRAPH_PADDING_X = 36;
  const GRAPH_PADDING_Y = 28;
  const GRAPH_MIN_WIDTH = 420;
  const GRAPH_MIN_HEIGHT = 260;
  const GRAPH_TIGHT_LIMIT = 4;
  const GRAPH_RING_RADIUS_NEAR = 140;
  const GRAPH_RING_RADIUS_FAR = 170;
  const GRAPH_RING_RADIUS_MAX_EXTRA = 56;
  const GRAPH_LABEL_CHAR_WIDTH = 7.4;
  const GRAPH_LABEL_MIN_GAP = 18;
  const GRAPH_LABEL_RADIUS_FACTOR = 0.32;
  const GRAPH_LAYOUT_PASSES = 3;
  const GRAPH_NODE_RADIUS = 34;
  const GRAPH_CURRENT_RADIUS = 50;
  const GRAPH_ROW_NODE_RADIUS = 28;
  const GRAPH_ROW_CURRENT_RADIUS = 38;
  const GRAPH_ROW_MAX_SPACING = 130;
  const GRAPH_ROW_TOTAL_WIDTH = 500;
  const GRAPH_EDGE_NODE_GAP = 28;
  const GRAPH_ROW_PARENT_OFFSET = 70;
  const GRAPH_FAMILY_TOP_Y = 22;
  const GRAPH_FAMILY_EMPTY_START_Y = 116;
  const GRAPH_FAMILY_CHAIN_START_Y = 48;
  const GRAPH_FAMILY_EMPTY_ANCHOR_Y = 46;
  const GRAPH_FAMILY_SIBLING_OFFSET_Y = 64;
  const GRAPH_FAMILY_SIBLING_FALLBACK_SPREAD = 440;
  const FAMILY_VERTICAL_STEP = 54;
  const FAMILY_LEVEL_GAP = 118;
  const FAMILY_SIDE_SPACING = 150;
  const GRAPH_EXPAND_INCREMENT = 4;
  const GRAPH_FAMILY_INCREMENT = 6;
  const GRAPH_CATEGORY_DEFAULTS = {
    scripts: 2,
    regions: 2,
    languoids: 4,
    familyAncestors: 6,
    familySiblings: 8,
    treeChildren: 8,
  };
  const propertyLabels = {
    name: "Name",
    sample: "Example",
    script_type: "Type",
    family: "Family",
    endonym: "Endonym",
    bcp_47: "BCP-47",
    iso_639_1: "ISO 639-1",
    iso_639_2b: "ISO 639-2B",
    iso_639_3: "ISO 639-3",
    iso_639_5: "ISO 639-5",
    glottocode: "Glottocode",
    wikidata_id: "Wikidata",
    wikipedia_code: "Wikipedia code",
    wikipedia_url: "Wikipedia URL",
    wikipedia_article_count: "Wikipedia articles",
    wikipedia_active_users: "Wikipedia active users",
    speaker_count: "Speaker count",
    latitude: "Latitude",
    longitude: "Longitude",
    level: "Level",
    scope: "Scope",
    status: "Status",
    endangerment_status: "Endangerment",
    description: "Description",
    id: "Canonical ID",
    iso_15924: "ISO 15924",
    unicode_alias: "Unicode script",
    unicode_character_count: "Unicode characters",
    unicode_range_count: "Unicode ranges",
    unicode_ranges: "Code point ranges",
    is_historical: "Historical",
    languoid_count: "Languoid count",
    country_code: "Country code",
    official_name: "Official name",
    subdivision_code: "Subdivision code",
    subdivision_type: "Subdivision type",
    parent_country_code: "Parent country code",
  };
  const PROPERTY_NUMBER_KEYS = {
    speaker_count: true,
    wikipedia_article_count: true,
    wikipedia_active_users: true,
    unicode_character_count: true,
    unicode_range_count: true,
  };
  const WIKIPEDIA_URL_KEY = "wikipedia_url";
  const RESOURCE_GROUPS = ["Datasets", "Reference", "Typology"];
  const propertySections = {
    languoid: [
      { title: "Names", keys: ["name", "endonym", "description"] },
      { title: "Identifiers", keys: ["bcp_47", "iso_639_1", "iso_639_2b", "iso_639_3", "iso_639_5", "glottocode", "wikidata_id"] },
      { title: "Classification", keys: ["level", "scope", "status", "endangerment_status"] },
      { title: "Geography", keys: ["latitude", "longitude", "speaker_count"] },
      { title: "Wikipedia", keys: ["wikipedia_code", "wikipedia_url", "wikipedia_article_count", "wikipedia_active_users"] },
      { title: "Internal", keys: ["id"] },
    ],
    script: [
      { title: "Names", keys: ["name", "sample"] },
      { title: "Identifiers", keys: ["iso_15924", "id"] },
      { title: "Unicode", keys: ["unicode_alias", "unicode_character_count", "unicode_range_count", "unicode_ranges"] },
      { title: "Classification", keys: ["script_type", "family", "is_historical"] },
      { title: "Coverage", keys: ["languoid_count"] },
    ],
    region: [
      { title: "Names", keys: ["name", "official_name"] },
      { title: "Identifiers", keys: ["country_code", "subdivision_code", "parent_country_code", "id"] },
      { title: "Classification", keys: ["subdivision_type", "is_historical"] },
    ],
  };
  const state = {
    currentId: data.meta.defaultId,
    pendingId: null,
    searchToken: 0,
    graphView: "mixed",
    graphCategoryLimits: Object.assign({}, GRAPH_CATEGORY_DEFAULTS),
    expandedRelationGroups: {},
  };
  const RELATION_LIST_LIMIT = 10;
  const RELATION_GROUP_PRIORITY = {
    Scripts: 0,
    Regions: 5,
    "Family tree": 10,
    Parent: 20,
    Children: 30,
    Siblings: 40,
    Macrolanguage: 50,
    "Individual languages": 60,
  };

  const statsEl = document.getElementById("stats");
  const searchEl = document.getElementById("search");
  const searchResultsEl = document.getElementById("search-results");
  const entityTypeEl = document.getElementById("entity-type");
  const entityNameEl = document.getElementById("entity-name");
  const entitySubtitleEl = document.getElementById("entity-subtitle");
  const entityActionsEl = document.getElementById("entity-actions");
  const entityWarningEl = document.getElementById("entity-warning");
  const propertiesEl = document.getElementById("properties");
  const resourcesEl = document.getElementById("resources");
  const relationsEl = document.getElementById("relations");
  const graphEl = document.getElementById("graph");
  const graphViewEl = document.getElementById("graph-view");
  const introSourcesEl = document.getElementById("intro-sources");

  (function renderStats() {
    const wrap = document.createElement("section");
    wrap.className = "intro-stats";

    const title = document.createElement("p");
    title.className = "intro-stats-title";
    title.textContent = "Coverage";
    wrap.appendChild(title);

    const dbVersion = (data.meta.counts && data.meta.counts.dbVersion) || data.meta.dbVersion;
    if (dbVersion) {
      const buildMeta = document.createElement("p");
      buildMeta.className = "intro-stats-meta";
      buildMeta.textContent = "Database version: " + dbVersion;
      wrap.appendChild(buildMeta);
    }

    const total = document.createElement("div");
    total.className = "stat-total";
    const totalBadge = document.createElement("span");
    totalBadge.className = "stat-badge";
    totalBadge.textContent = countLabel(data.meta.counts.entities, "entity", "entities");
    total.appendChild(totalBadge);
    wrap.appendChild(total);

    const breakdown = document.createElement("div");
    breakdown.className = "stat-breakdown";
    [
      { text: countLabel(data.meta.counts.languoids, "languoid", "languoids"), type: "is-languoid" },
      { text: countLabel(data.meta.counts.scripts, "script", "scripts"), type: "is-script" },
      { text: countLabel(data.meta.counts.regions, "region", "regions"), type: "is-region" },
    ].forEach(function (item) {
      const badge = document.createElement("span");
      badge.className = "stat-badge" + (item.type ? " " + item.type : "");
      badge.textContent = item.text;
      breakdown.appendChild(badge);
    });
    wrap.appendChild(breakdown);

    statsEl.replaceChildren(wrap);
  })();

  (function renderSources() {
    if (!introSourcesEl) {
      return;
    }
    const sources = (data.meta.counts && data.meta.counts.sources) || data.meta.sources || [];
    if (!sources.length) {
      return;
    }

    const title = document.createElement("p");
    title.className = "intro-sources-title";
    title.textContent = "Sources";
    introSourcesEl.appendChild(title);

    const list = document.createElement("div");
    list.className = "intro-source-list";

    sources.forEach(function (source) {
      const card = document.createElement("div");
      card.className = "intro-source-item";

      const name = document.createElement("h3");
      name.className = "intro-source-name";
      name.textContent = source.name;
      card.appendChild(name);

      const meta = [];
      if (source.license) {
        meta.push("License: " + source.license);
      }
      if (source.last_updated) {
        meta.push("Updated: " + source.last_updated);
      }
      if (meta.length) {
        const metaLine = document.createElement("p");
        metaLine.className = "intro-source-meta";
        metaLine.textContent = meta.join(" · ");
        card.appendChild(metaLine);
      }

      const links = [];
      if (source.source_url) {
        links.push({ label: "Source", href: source.source_url });
      }
      if (source.website_url) {
        links.push({ label: "Website", href: source.website_url });
      }
      if (source.paper_url) {
        links.push({ label: "Paper", href: source.paper_url });
      }
      if (links.length) {
        const linksLine = document.createElement("p");
        linksLine.className = "intro-source-links";
        links.forEach(function (link, index) {
          if (index > 0) {
            linksLine.appendChild(document.createTextNode(" · "));
          }
          const anchor = document.createElement("a");
          anchor.href = link.href;
          anchor.target = "_blank";
          anchor.rel = "noreferrer noopener";
          anchor.textContent = link.label + " ↗";
          linksLine.appendChild(anchor);
        });
        card.appendChild(linksLine);
      }

      if (source.notes) {
        const notes = document.createElement("p");
        notes.className = "intro-source-notes";
        appendMarkdownLinks(notes, source.notes);
        card.appendChild(notes);
      }

      list.appendChild(card);
    });

    introSourcesEl.appendChild(list);
  })();

  function titleCase(value) {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  function countLabel(count, singular, plural) {
    return count.toLocaleString() + " " + (count === 1 ? singular : plural);
  }

  function formatNumberValue(value) {
    if (value === null || value === undefined || value === "") {
      return "";
    }
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return String(value);
    }
    return numeric.toLocaleString();
  }

  function appendMarkdownLinks(parent, text) {
    const pattern = /\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g;
    let lastIndex = 0;
    let match = pattern.exec(text);

    while (match) {
      if (match.index > lastIndex) {
        parent.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }
      const anchor = document.createElement("a");
      anchor.href = match[2];
      anchor.target = "_blank";
      anchor.rel = "noreferrer noopener";
      anchor.textContent = match[1] + " ↗";
      parent.appendChild(anchor);
      lastIndex = pattern.lastIndex;
      match = pattern.exec(text);
    }

    if (lastIndex < text.length) {
      parent.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
  }

  function normalizeSearchText(value) {
    return String(value || "")
      .normalize("NFC")
      .toLowerCase()
      .replace(/[\p{Pd}\p{Pc}\p{Ps}\p{Pe}\p{Pi}\p{Pf}\p{Po}]+/gu, " ")
      .replace(/\s+/g, " ")
      .trim();
  }

  function buildIdentifierIndex(list) {
    const index = {};
    list.forEach(function (entity) {
      (entity.i || []).forEach(function (identifier) {
        const key = identifier.toLowerCase();
        if (!index[key]) {
          index[key] = [];
        }
        if (index[key].indexOf(entity.id) === -1) {
          index[key].push(entity.id);
        }
      });
    });
    return index;
  }

  function entityIdsForIdentifier(identifier) {
    return identifierToIds[(identifier || "").toLowerCase()] || [];
  }

  function appendInlineEntityLinks(parent, identifiers, labelById) {
    const wrap = document.createElement("span");
    wrap.className = "inline-links";
    let hasAny = false;

    identifiers.forEach(function (identifier) {
      const ids = entityIdsForIdentifier(identifier);
      if (ids.length === 0) {
        const text = document.createElement("span");
        text.textContent = identifier;
        wrap.appendChild(text);
        hasAny = true;
        return;
      }
      ids.forEach(function (entityId) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "inline-link";
        button.textContent = labelById ? labelById(entityId, identifier) : identifier;
        button.addEventListener("click", function () {
          navigateTo(entityId);
        });
        wrap.appendChild(button);
        hasAny = true;
      });
    });

    if (hasAny) {
      parent.appendChild(wrap);
    }
  }

  function appendTargetEntityLinks(parent, targetIds, labelById) {
    const wrap = document.createElement("span");
    wrap.className = "inline-links";
    let hasAny = false;

    (targetIds || []).forEach(function (entityId) {
      if (!summaries[entityId]) {
        return;
      }
      const button = document.createElement("button");
      button.type = "button";
      button.className = "inline-link";
      button.textContent = labelById ? labelById(entityId) : summaries[entityId].n;
      button.addEventListener("click", function () {
        navigateTo(entityId);
      });
      wrap.appendChild(button);
      hasAny = true;
    });

    if (hasAny) {
      parent.appendChild(wrap);
    }
  }

  function renderEntityWarning(detail) {
    entityWarningEl.replaceChildren();
    if (
      (!detail.replaced_from || detail.replaced_from.length === 0) &&
      (!detail.replaced_by || detail.replaced_by.length === 0) &&
      (!detail.deprecated || detail.deprecated.length === 0)
    ) {
      return;
    }

    const box = document.createElement("div");
    box.className = "warning-box";

    if (detail.replaced_from && detail.replaced_from.length > 0) {
      const line = document.createElement("div");
      line.appendChild(document.createTextNode("Deprecated entities: "));
      appendTargetEntityLinks(line, detail.replaced_from);
      box.appendChild(line);
    }

    if (detail.replaced_by && detail.replaced_by.length > 0) {
      const line = document.createElement("div");
      line.className = "deprecated-item-meta";
      line.appendChild(document.createTextNode("Replaced by: "));
      appendTargetEntityLinks(line, detail.replaced_by);
      box.appendChild(line);
    }

    if (detail.deprecated && detail.deprecated.length > 0) {
      detail.deprecated.forEach(function (entry) {
        const line = document.createElement("div");
        line.className = "deprecated-item-meta";
        const label = document.createElement("span");
        label.className = "inline-link";
        label.textContent = entry.code;
        line.appendChild(label);

        const meta = [
          entry.code_type || null,
          entry.reason || null,
          entry.effective || null,
        ].filter(Boolean).join(" · ");
        if (meta) {
          line.appendChild(document.createTextNode(" · " + meta));
        }

        if (entry.target_ids && entry.target_ids.length > 0) {
          line.appendChild(document.createTextNode(" → "));
          appendTargetEntityLinks(line, entry.target_ids);
        }

        box.appendChild(line);
      });
    }

    entityWarningEl.appendChild(box);
  }

  function copyText(text, button) {
    navigator.clipboard.writeText(text).then(function () {
      button.dataset.copied = "true";
      button.textContent = "Copied";
      window.setTimeout(function () {
        button.dataset.copied = "false";
        button.textContent = "Copy";
      }, 1000);
    });
  }

  function appendHighlightedText(parent, text, normalizedQuery) {
    if (!normalizedQuery) {
      parent.textContent = text;
      return;
    }

    const haystack = text.toLowerCase();
    const needle = normalizedQuery.toLowerCase();
    let offset = 0;
    let index = haystack.indexOf(needle, offset);

    if (index === -1) {
      parent.textContent = text;
      return;
    }

    while (index !== -1) {
      if (index > offset) {
        parent.appendChild(document.createTextNode(text.slice(offset, index)));
      }
      const strong = document.createElement("strong");
      strong.className = "search-highlight";
      strong.textContent = text.slice(index, index + needle.length);
      parent.appendChild(strong);
      offset = index + needle.length;
      index = haystack.indexOf(needle, offset);
    }

    if (offset < text.length) {
      parent.appendChild(document.createTextNode(text.slice(offset)));
    }
  }

  function makeEntityButton(entityId, className, matchText, highlightQuery) {
    const entity = summaries[entityId];
    const button = document.createElement("button");
    button.type = "button";
    button.className = className + " is-" + entity.t;
    button.addEventListener("click", function () {
      navigateTo(entityId);
    });

    const top = document.createElement("span");
    top.className = className + "-top";
    button.appendChild(top);

    const type = document.createElement("span");
    type.className = className + "-type";
    type.textContent = entity.t;
    top.appendChild(type);

    const name = document.createElement("span");
    name.className = className + "-name";
    appendHighlightedText(name, entity.n, highlightQuery);
    top.appendChild(name);

    const meta = document.createElement("span");
    meta.className = className + "-meta";
    appendHighlightedText(meta, formatEntityMeta(entity), highlightQuery);
    button.appendChild(meta);

    if (matchText) {
      const match = document.createElement("span");
      match.className = className + "-match";
      appendHighlightedText(match, matchText, highlightQuery);
      button.appendChild(match);
    }

    return button;
  }

  function formatEntityMeta(entity) {
    const parts = entity.s ? entity.s.split(" / ").filter(Boolean) : [];
    return parts.join(" · ");
  }

  function bySearchRank(a, b) {
    if (a.rank !== b.rank) {
      return a.rank - b.rank;
    }
    const aSort = a.sortText || a.entity.n;
    const bSort = b.sortText || b.entity.n;
    return aSort.localeCompare(bSort) || a.entity.n.localeCompare(b.entity.n) || a.entity.id.localeCompare(b.entity.id);
  }

  function renderScoredSearchResults(scored, normalizedQuery) {
    searchResultsEl.replaceChildren();
    scored.sort(bySearchRank);
    scored.slice(0, SEARCH_RESULT_LIMIT).forEach(function (item) {
      searchResultsEl.appendChild(makeEntityButton(item.entity.id, "search-result", item.matchText, normalizedQuery));
    });
  }

  function scorePrimaryEntities(normalized) {
    const scored = [];

    for (let i = 0; i < entityList.length; i += 1) {
      const entity = entityList[i];
      const match = scoreEntity(entity, normalized);
      if (match === null) {
        continue;
      }
      scored.push({ entity: entity, rank: match.rank, matchText: match.text, sortText: match.sortText });
    }

    return scored;
  }

  function renderSearchResults(query) {
    const token = state.searchToken + 1;
    state.searchToken = token;
    searchResultsEl.replaceChildren();
    if (!query) {
      return;
    }

    const normalized = normalizeSearchText(query);
    if (!normalized) {
      return;
    }

    const primary = scorePrimaryEntities(normalized);
    renderScoredSearchResults(primary, normalized);

    const bucket = nameBucketForQuery(normalized);
    loadNameBucket(bucket).then(function (entries) {
      if (state.searchToken !== token) {
        return;
      }
      renderScoredSearchResults(mergeMultilingualMatches(primary.slice(), entries, normalized), normalized);
    }).catch(function () {
      if (state.searchToken !== token) {
        return;
      }
      renderScoredSearchResults(primary, normalized);
    });
  }

  function scoreEntity(entity, normalized) {
    if (entity.t === "languoid") {
      const exactId = firstExact(entity.i, normalized);
      if (exactId) {
        const isDeprecated = entity.d && entity.d.indexOf(exactId) !== -1;
        return { rank: IDENTIFIER_EXACT_RANK, text: (isDeprecated ? "Deprecated identifier: " : "Exact identifier: ") + exactId };
      }
      const exactName = firstExact(entity.m, normalized);
      if (exactName) {
        return { rank: NAME_EXACT_RANK, text: "Exact name: " + exactName };
      }
      const prefixName = firstPrefix(entity.m, normalized);
      if (prefixName) {
        return { rank: NAME_PREFIX_RANK, text: "Starts with: " + prefixName };
      }
      const substringName = firstSubstring(entity.m, normalized);
      if (substringName) {
        return { rank: NAME_SUBSTRING_RANK, text: "Contains: " + substringName };
      }
      const relatedName = firstSubstring(entity.a || [], normalized);
      if (relatedName) {
        return { rank: RELATED_NAME_RANK, text: "Related family: " + relatedName, sortText: relatedName };
      }
      return null;
    }

    if (entity.t === "script") {
      const exactScriptId = firstExact(entity.i, normalized);
      if (exactScriptId) {
        return { rank: IDENTIFIER_EXACT_RANK, text: "Exact identifier: " + exactScriptId };
      }
      const exactScript = firstExact(entity.m, normalized);
      if (exactScript) {
        return { rank: NAME_EXACT_RANK, text: "Exact name: " + exactScript };
      }
      const prefixScript = firstPrefix(entity.m, normalized);
      if (prefixScript) {
        return { rank: NAME_PREFIX_RANK, text: "Starts with: " + prefixScript };
      }
      const substringScript = firstSubstring(entity.m, normalized);
      if (substringScript) {
        return { rank: NAME_SUBSTRING_RANK, text: "Contains: " + substringScript };
      }
      return null;
    }

    if (entity.t === "region") {
      const exactRegionId = firstExact(entity.i, normalized);
      if (exactRegionId) {
        return { rank: IDENTIFIER_EXACT_RANK, text: "Exact identifier: " + exactRegionId };
      }
      const exactRegion = firstExact(entity.m, normalized);
      if (exactRegion) {
        return { rank: NAME_EXACT_RANK, text: "Exact name: " + exactRegion };
      }
      const prefixRegion = firstPrefix(entity.m, normalized) || firstPrefix(entity.i, normalized);
      if (prefixRegion) {
        return { rank: NAME_PREFIX_RANK, text: "Starts with: " + prefixRegion };
      }
      const substringRegion = firstSubstring(entity.m, normalized) || firstSubstring(entity.i, normalized);
      if (substringRegion) {
        return { rank: NAME_SUBSTRING_RANK, text: "Contains: " + substringRegion };
      }
      return null;
    }

    return null;
  }

  function firstExact(values, query) {
    for (let i = 0; i < values.length; i += 1) {
      if (normalizeSearchText(values[i]) === query) {
        return values[i];
      }
    }
    return null;
  }

  function firstPrefix(values, query) {
    for (let i = 0; i < values.length; i += 1) {
      if (normalizeSearchText(values[i]).startsWith(query)) {
        return values[i];
      }
    }
    return null;
  }

  function firstSubstring(values, query) {
    for (let i = 0; i < values.length; i += 1) {
      if (normalizeSearchText(values[i]).indexOf(query) !== -1) {
        return values[i];
      }
    }
    return null;
  }

  function detailsFor(entityId) {
    const summary = summaries[entityId];
    const chunk = loadedBuckets[summary.b];
    if (!chunk) {
      return null;
    }
    return chunk[entityId] || null;
  }

  function loadBucket(bucket) {
    if (loadedBuckets[bucket]) {
      return Promise.resolve(loadedBuckets[bucket]);
    }
    if (bucketLoads[bucket]) {
      return bucketLoads[bucket];
    }

    bucketLoads[bucket] = new Promise(function (resolve, reject) {
      const script = document.createElement("script");
      script.src = "./data/chunks/" + bucket + ".js";
      script.onload = function () {
        resolve(loadedBuckets[bucket]);
      };
      script.onerror = function () {
        reject(new Error("Failed to load bucket " + bucket));
      };
      document.body.appendChild(script);
    });

    return bucketLoads[bucket];
  }

  function nameBucketForQuery(query) {
    if (!query) {
      return null;
    }
    return ("0" + (query.codePointAt(0) % 256).toString(16)).slice(-2);
  }

  function loadNameBucket(bucket) {
    if (!bucket || !availableNameBuckets[bucket]) {
      return Promise.resolve([]);
    }
    if (loadedNameBuckets[bucket]) {
      return Promise.resolve(loadedNameBuckets[bucket]);
    }
    if (nameBucketLoads[bucket]) {
      return nameBucketLoads[bucket];
    }

    nameBucketLoads[bucket] = new Promise(function (resolve, reject) {
      const script = document.createElement("script");
      script.src = "./data/names/" + bucket + ".js";
      script.onload = function () {
        resolve(loadedNameBuckets[bucket] || []);
      };
      script.onerror = function () {
        reject(new Error("Failed to load name bucket " + bucket));
      };
      document.body.appendChild(script);
    });

    return nameBucketLoads[bucket];
  }

  function scoreMultilingualNameEntry(entry, normalized) {
    const normalizedName = normalizeSearchText(entry[0]);
    if (normalizedName === normalized) {
      return MULTILINGUAL_EXACT_RANK;
    }
    if (normalizedName.indexOf(normalized) === 0) {
      return MULTILINGUAL_PREFIX_RANK;
    }
    if (normalizedName.indexOf(normalized) !== -1) {
      return MULTILINGUAL_SUBSTRING_RANK;
    }
    return null;
  }

  function localeLabel(localeId) {
    return summaries[localeId] ? summaries[localeId].n : localeId;
  }

  function mergeMultilingualMatches(scored, entries, normalized) {
    const bestById = {};

    scored.forEach(function (item) {
      bestById[item.entity.id] = item;
    });

    entries.forEach(function (entry) {
      const entityId = entry[1];
      const entity = summaries[entityId];
      const rank = scoreMultilingualNameEntry(entry, normalized);
      if (!entity || rank === null) {
        return;
      }
      if (bestById[entityId] && bestById[entityId].rank <= rank) {
        return;
      }
      bestById[entityId] = {
        entity: Object.assign({ id: entityId }, entity),
        rank: rank,
        matchText: "Name in " + localeLabel(entry[2]) + ": " + entry[0],
      };
    });

    return Object.values(bestById);
  }

  function renderEntityActions() {
    entityActionsEl.replaceChildren();
  }

  function propertyBackedResources(detail) {
    const resources = [];

    if (detail.p.glottocode) {
      resources.push({
        group: "Reference",
        label: "Glottolog",
        links: [
          {
            href: "https://glottolog.org/resource/languoid/id/" + encodeURIComponent(detail.p.glottocode),
            text: detail.p.glottocode + " ↗",
          },
        ],
      });
    }
    if (detail.p.wikidata_id) {
      resources.push({
        group: "Reference",
        label: "Wikidata",
        links: [
          {
            href: "https://www.wikidata.org/wiki/" + encodeURIComponent(detail.p.wikidata_id),
            text: detail.p.wikidata_id + " ↗",
          },
        ],
      });
    }
    if (detail.p.wikipedia_url) {
      resources.push({
        group: "Reference",
        label: "Wikipedia",
        links: [{ href: detail.p.wikipedia_url, text: detail.p.wikipedia_code + " ↗" }],
      });
    }

    return resources;
  }

  function sourceBackedResources(detail) {
    return (detail.resources || []).map(function (resource) {
      return {
        group: resource.group,
        label: resource.label,
        links: [
          {
            code: resource.code,
            href: resource.url,
            text: resource.code + " ↗",
            count: resource.count,
          },
        ],
      };
    });
  }

  function resourceLinks(summary, detail) {
    if (summary.t !== "languoid") {
      return [];
    }

    const seen = {};
    return propertyBackedResources(detail)
      .concat(sourceBackedResources(detail))
      .map(function (resource) {
        const links = resource.links.filter(function (link) {
          const key = resource.group + "::" + resource.label + "::" + link.href;
          if (seen[key]) {
            return false;
          }
          seen[key] = true;
          return true;
        });
        if (links.length === 0) {
          return null;
        }
        return Object.assign({}, resource, { links: links });
      })
      .filter(Boolean);
  }

  function formatResourceCount(count) {
    if (!count || count < 1) {
      return "";
    }
    if (count >= 1000) {
      return "1000+";
    }
    if (count >= 500) {
      return "500+";
    }
    if (count >= 100) {
      return "100+";
    }
    if (count >= 50) {
      return "50+";
    }
    if (count >= 10) {
      return "10+";
    }
    return String(count);
  }

  function renderResources(summary, detail) {
    resourcesEl.replaceChildren();

    const links = resourceLinks(summary, detail);
    if (links.length === 0) {
      resourcesEl.textContent = "No external resources found.";
      return;
    }

    RESOURCE_GROUPS.forEach(function (groupName) {
      const groupLinks = links.filter(function (resource) {
        return resource.group === groupName;
      });
      if (groupLinks.length === 0) {
        return;
      }

      const group = document.createElement("section");
      group.className = "resource-group";

      const title = document.createElement("h3");
      title.className = "resource-group-title";
      title.textContent = groupName;
      group.appendChild(title);

      nHFDatasets = groupLinks.filter(i => i.label === "Hugging Face").length;

      groupLinks.forEach(function (resource) {
        const row = document.createElement("div");
        row.className = "resource-row";

        const label = document.createElement("div");
        label.className = "resource-label";
        label.textContent = resource.label;
        if (resource.label === "Hugging Face" && nHFDatasets > 1) {
          const hint = document.createElement("button");
          hint.type = "button";
          hint.className = "resource-hint";
          hint.textContent = "?";
          hint.dataset.tooltip =
            "Hugging Face combines multiple language filters as AND, so QQ shows one link per matching language tag.";
          hint.setAttribute(
            "aria-label",
            "Hugging Face combines multiple language filters as AND, so QQ shows one link per matching language tag."
          );
          label.appendChild(hint);
        }
        row.appendChild(label);

        const values = document.createElement("div");
        values.className = "resource-values";
        resource.links.forEach(function (linkData, index) {
          if (index > 0) {
            const separator = document.createElement("span");
            separator.className = "resource-separator";
            separator.textContent = "·";
            values.appendChild(separator);
          }
          const link = document.createElement("a");
          link.className = "resource-link property-link";
          link.href = linkData.href;
          link.target = "_blank";
          link.rel = "noreferrer noopener";
          link.textContent = linkData.text;
          values.appendChild(link);
          const countText = formatResourceCount(linkData.count);
          if (countText) {
            const count = document.createElement("span");
            count.className = "resource-count";
            count.textContent = countText + (countText === "1" ? " dataset" : " datasets");
            values.appendChild(count);
          }
        });
        row.appendChild(values);
        group.appendChild(row);
      });

      resourcesEl.appendChild(group);
    });
  }

  function renderProperties(summary, detail) {
    propertiesEl.replaceChildren();
    propertySections[summary.t].forEach(function (section) {
      const wrapper = document.createElement("section");
      wrapper.className = "property-section";

      const title = document.createElement("h3");
      title.className = "property-section-title";
      title.textContent = section.title;
      wrapper.appendChild(title);

      section.keys.forEach(function (key) {
        const row = document.createElement("div");
        row.className = "property";

        const label = document.createElement("div");
        label.className = "property-label";
        label.textContent = propertyLabels[key] || key;
        row.appendChild(label);

        const value = document.createElement("div");
        value.className = "property-value";
        const propertyValue = key in detail.p ? detail.p[key] : "";
        if (propertyValue === "") {
          value.classList.add("is-empty");
          value.textContent = " ";
        } else if (key === WIKIPEDIA_URL_KEY) {
          const link = document.createElement("a");
          link.className = "property-link";
          link.href = propertyValue;
          link.target = "_blank";
          link.rel = "noreferrer noopener";
          link.textContent = propertyValue + " ↗";
          value.appendChild(link);
        } else if (PROPERTY_NUMBER_KEYS[key]) {
          value.textContent = formatNumberValue(propertyValue);
        } else if (
          propertyValue.indexOf("://") !== -1 ||
          propertyValue.indexOf("lang:") === 0 ||
          propertyValue.indexOf("script:") === 0 ||
          propertyValue.indexOf("region:") === 0
        ) {
          value.classList.add("is-code");
          value.textContent = propertyValue;
        } else {
          value.textContent = propertyValue;
        }
        row.appendChild(value);

        const copy = document.createElement("button");
        copy.type = "button";
        copy.className = "copy-button";
        copy.setAttribute("aria-label", propertyValue === "" ? "Empty value" : "Copy value");
        if (propertyValue === "") {
          copy.textContent = "Empty";
          copy.disabled = true;
        } else {
          copy.textContent = "Copy";
          copy.addEventListener("click", function () {
            copyText(propertyValue, copy);
          });
        }
        row.appendChild(copy);

        wrapper.appendChild(row);
      });

      propertiesEl.appendChild(wrapper);
    });
  }

  function relationExpansionKey(entityId, label) {
    return entityId + "::" + label;
  }

  function renderRelations(entityId, detail) {
    relationsEl.replaceChildren();
    const groups = detail.r.slice().sort(function (a, b) {
      const aPriority = Object.prototype.hasOwnProperty.call(RELATION_GROUP_PRIORITY, a.l)
        ? RELATION_GROUP_PRIORITY[a.l]
        : 100;
      const bPriority = Object.prototype.hasOwnProperty.call(RELATION_GROUP_PRIORITY, b.l)
        ? RELATION_GROUP_PRIORITY[b.l]
        : 100;
      if (aPriority !== bPriority) {
        return aPriority - bPriority;
      }
      return a.l.localeCompare(b.l);
    });

    groups.forEach(function (group) {
      const wrapper = document.createElement("section");
      wrapper.className = "relation-group";

      const header = document.createElement("div");
      header.className = "relation-group-header";

      const title = document.createElement("h3");
      title.className = "relation-group-title";
      title.textContent = group.l;
      header.appendChild(title);

      const count = document.createElement("div");
      count.className = "relation-count";
      count.textContent = countLabel(group.i.length, "item", "items");
      header.appendChild(count);
      wrapper.appendChild(header);

      const list = document.createElement("div");
      list.className = "relation-list" + (group.l === "Family tree" ? " is-family-tree" : "");
      const groupKey = relationExpansionKey(entityId, group.l);
      const isExpanded = state.expandedRelationGroups[groupKey] === true;
      const relationIds = group.l === "Family tree" ? group.i.slice().reverse() : group.i.slice();
      const visibleCount = isExpanded ? relationIds.length : Math.min(relationIds.length, RELATION_LIST_LIMIT);

      relationIds.slice(0, visibleCount).forEach(function (relatedEntityId, index) {
        const item = makeEntityButton(relatedEntityId, "relation-item");
        if (group.l === "Family tree") {
          item.style.setProperty("--family-indent", Math.min(index, 6) * 0.85 + "rem");
        }
        list.appendChild(item);
      });

      if (relationIds.length > RELATION_LIST_LIMIT && !isExpanded) {
        const expand = document.createElement("button");
        expand.type = "button";
        expand.className = "relation-expand";
        expand.textContent = `Expand (${countLabel(relationIds.length - RELATION_LIST_LIMIT, "more item", "more items")})`;
        expand.addEventListener("click", function () {
          state.expandedRelationGroups[groupKey] = true;
          renderRelations(entityId, detail);
        });
        list.appendChild(expand);
      }

      wrapper.appendChild(list);
      relationsEl.appendChild(wrapper);
    });
  }

  function graphLabel(entity) {
    if (entity.n.length <= SHORT_LABEL_LIMIT) {
      return entity.n;
    }
    return entity.n.slice(0, SHORT_LABEL_SLICE) + "…";
  }

  function relationItems(detail, label) {
    for (let i = 0; i < detail.r.length; i += 1) {
      if (detail.r[i].l === label) {
        return detail.r[i].i.slice();
      }
    }
    return [];
  }

  function uniqueList(ids) {
    const seen = {};
    const result = [];
    ids.forEach(function (entityId) {
      if (seen[entityId]) {
        return;
      }
      seen[entityId] = true;
      result.push(entityId);
    });
    return result;
  }

  function mixedNeighborSets(summary, detail) {
    if (summary.t === "script") {
      return {
        scripts: [],
        regions: [],
        languoids: uniqueList(relationItems(detail, "Canonical languoids").concat(relationItems(detail, "Languoids"))),
      };
    }

    if (summary.t === "region") {
      return {
        scripts: relationItems(detail, "Scripts"),
        regions: uniqueList(
          relationItems(detail, "Parent region").concat(relationItems(detail, "Child regions")).concat(relationItems(detail, "Subdivisions"))
        ),
        languoids: relationItems(detail, "Languoids"),
      };
    }

    return {
      scripts: relationItems(detail, "Scripts"),
      regions: relationItems(detail, "Regions"),
      languoids: uniqueList(
        []
          .concat(relationItems(detail, "Parent"))
          .concat(relationItems(detail, "Children"))
          .concat(relationItems(detail, "Siblings"))
          .concat(relationItems(detail, "Family tree"))
          .concat(relationItems(detail, "Macrolanguage"))
          .concat(relationItems(detail, "Individual languages"))
      ),
    };
  }

  function entityTypeClass(entity) {
    return "is-" + entity.t;
  }

  function makeSvgLabel(x, y, textValue, className, onClick) {
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", x);
    text.setAttribute("y", y + 4);
    text.setAttribute("class", className);
    text.textContent = textValue;
    if (onClick) {
      text.addEventListener("click", onClick);
    }
    graphEl.appendChild(text);
    return text;
  }

  function makeSvgLabelPlate(textNode, className, onClick) {
    const box = textNode.getBBox();
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", box.x - 12);
    rect.setAttribute("y", box.y - 6);
    rect.setAttribute("width", box.width + 24);
    rect.setAttribute("height", box.height + 12);
    rect.setAttribute("rx", 10);
    rect.setAttribute("class", className);
    if (onClick) {
      rect.addEventListener("click", onClick);
      rect.style.cursor = "pointer";
    }
    graphEl.insertBefore(rect, textNode);
  }

  function drawGraphEdge(x1, y1, x2, y2) {
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", x1);
    line.setAttribute("y1", y1);
    line.setAttribute("x2", x2);
    line.setAttribute("y2", y2);
    line.setAttribute("class", "graph-link");
    graphEl.appendChild(line);
  }

  function resetGraphViewport() {
    graphEl.setAttribute("viewBox", DEFAULT_GRAPH_VIEWBOX);
  }

  function adjustGraphViewport() {
    if (!graphEl.firstChild) {
      resetGraphViewport();
      return;
    }

    const box = graphEl.getBBox();
    let x = box.x - GRAPH_PADDING_X;
    let y = box.y - GRAPH_PADDING_Y;
    let width = box.width + GRAPH_PADDING_X * 2;
    let height = box.height + GRAPH_PADDING_Y * 2;

    if (width < GRAPH_MIN_WIDTH) {
      x -= (GRAPH_MIN_WIDTH - width) / 2;
      width = GRAPH_MIN_WIDTH;
    }

    if (height < GRAPH_MIN_HEIGHT) {
      y -= (GRAPH_MIN_HEIGHT - height) / 2;
      height = GRAPH_MIN_HEIGHT;
    }

    graphEl.setAttribute("viewBox", [x, y, width, height].join(" "));
  }

  function drawGraphEntity(entity, x, y, radius, extraClass) {
    const open = function () {
      if (state.currentId !== entity.id) {
        resetGraphState();
      }
      navigateTo(entity.id);
    };
    const labelClass = "graph-label" + (extraClass ? " " + extraClass : "");
    const plateClass = "graph-label-plate " + entityTypeClass(entity) + (extraClass ? " " + extraClass : "");
    const label = makeSvgLabel(x, y, graphLabel(entity), labelClass, open);
    makeSvgLabelPlate(label, plateClass, open);
  }

  function drawActionNode(x, y, labelText, onClick, typeName) {
    const typeClass = typeName ? " is-" + typeName : "";
    const label = makeSvgLabel(x, y, labelText, "graph-label graph-expand-label is-action" + typeClass, onClick);
    makeSvgLabelPlate(label, "graph-label-plate graph-expand" + typeClass, onClick);
  }

  function effectiveGraphLimit(baseLimit, count) {
    if (count <= GRAPH_TIGHT_LIMIT) {
      return count;
    }
    return baseLimit;
  }

  function estimateGraphLabelWidth(slot) {
    const text = slot.kind === "entity" ? graphLabel(slot.entity) : slot.label;
    return text.length * GRAPH_LABEL_CHAR_WIDTH + 24;
  }

  function layoutCircleSlots(slots) {
    if (slots.length === 0) {
      return [];
    }

    const positioned = slots.map(function (slot, index) {
      const width = estimateGraphLabelWidth(slot);
      const baseRadius = index % 2 === 0 ? GRAPH_RING_RADIUS_NEAR : GRAPH_RING_RADIUS_FAR;
      return {
        slot: slot,
        width: width,
        radius: baseRadius + Math.min(width * GRAPH_LABEL_RADIUS_FACTOR, GRAPH_RING_RADIUS_MAX_EXTRA),
        angle: (Math.PI * 2 * index) / Math.max(slots.length, 1),
      };
    });

    for (let pass = 0; pass < GRAPH_LAYOUT_PASSES; pass += 1) {
      for (let i = 0; i < positioned.length - 1; i += 1) {
        const current = positioned[i];
        const next = positioned[i + 1];
        const desiredGap = (current.width / 2 + next.width / 2 + GRAPH_LABEL_MIN_GAP) / Math.max(current.radius, next.radius);
        const actualGap = next.angle - current.angle;
        if (actualGap >= desiredGap) {
          continue;
        }
        const push = (desiredGap - actualGap) / 2;
        current.angle -= push;
        next.angle += push;
      }
    }

    const first = positioned[0];
    const last = positioned[positioned.length - 1];
    const currentCenter = (first.angle + last.angle) / 2;
    const shift = -Math.PI / 2 - currentCenter;

    return positioned.map(function (item) {
      return {
        slot: item.slot,
        x: GRAPH_CENTER_X + Math.cos(item.angle + shift) * item.radius,
        y: GRAPH_CENTER_Y + Math.sin(item.angle + shift) * item.radius,
      };
    });
  }

  function drawCenteredCircle(summary, detail) {
    let slots = [];

    if (state.graphView === "mixed") {
      const sets = mixedNeighborSets(summary, detail);
      ["scripts", "regions", "languoids"].forEach(function (key) {
        const ids = sets[key];
        const visible = ids.slice(0, effectiveGraphLimit(state.graphCategoryLimits[key], ids.length));
        visible.forEach(function (id) {
          slots.push({ kind: "entity", entity: Object.assign({ id: id }, summaries[id]) });
        });
        if (ids.length > visible.length) {
          slots.push({
            kind: "expand",
            label: "+" + (ids.length - visible.length),
            expandKey: key,
            typeName: key === "languoids" ? "languoid" : key.slice(0, -1),
          });
        }
      });
    } else {
      const relationMap = {
        scripts: relationItems(detail, "Scripts"),
        regions: summary.t === "region"
          ? uniqueList(
              relationItems(detail, "Parent region").concat(relationItems(detail, "Child regions")).concat(relationItems(detail, "Subdivisions"))
            )
          : relationItems(detail, "Regions"),
        languoids: mixedNeighborSets(summary, detail).languoids,
      };
      const ids = relationMap[state.graphView] || [];
      const visible = ids.slice(0, effectiveGraphLimit(state.graphCategoryLimits[state.graphView] || ids.length, ids.length));
      visible.forEach(function (id) {
        slots.push({ kind: "entity", entity: Object.assign({ id: id }, summaries[id]) });
      });
      if (ids.length > visible.length) {
        slots.push({
          kind: "expand",
          label: "+" + (ids.length - visible.length),
          expandKey: state.graphView,
          typeName: state.graphView === "languoids" ? "languoid" : state.graphView.slice(0, -1),
        });
      }
    }

    layoutCircleSlots(slots).forEach(function (positioned) {
      const slot = positioned.slot;
      const x = positioned.x;
      const y = positioned.y;
      drawGraphEdge(GRAPH_CENTER_X, GRAPH_CENTER_Y, x, y);
      if (slot.kind === "entity") {
        drawGraphEntity(slot.entity, x, y, GRAPH_NODE_RADIUS, "");
      } else {
        drawActionNode(x, y, slot.label, function () {
          state.graphCategoryLimits[slot.expandKey] += GRAPH_EXPAND_INCREMENT;
          renderGraph(summary, detail);
        }, slot.typeName);
      }
    });

    drawGraphEntity(summary, GRAPH_CENTER_X, GRAPH_CENTER_Y, GRAPH_CURRENT_RADIUS, "current");
  }

  function treeNode(entityId) {
    return Object.assign({ id: entityId }, summaries[entityId]);
  }

  function drawVerticalChain(ids, centerX, startY, stepY, currentId) {
    ids.forEach(function (id, index) {
      const entity = treeNode(id);
      const y = startY + index * stepY;
      if (index > 0) {
        drawGraphEdge(centerX, startY + (index - 1) * stepY + GRAPH_EDGE_NODE_GAP, centerX, y - GRAPH_EDGE_NODE_GAP);
      }
      drawGraphEntity(entity, centerX, y, id === currentId ? GRAPH_ROW_CURRENT_RADIUS : GRAPH_ROW_NODE_RADIUS, id === currentId ? "current" : "");
    });
  }

  function drawRow(ids, centerX, y, limitKey, currentId, onExpand) {
    const visible = ids.slice(0, effectiveGraphLimit(state.graphCategoryLimits[limitKey], ids.length));
    const hiddenCount = Math.max(ids.length - visible.length, 0);
    const slots = visible.slice();
    if (hiddenCount > 0) {
      slots.push("__expand__");
    }
    const spacing = slots.length > 1 ? Math.min(GRAPH_ROW_MAX_SPACING, GRAPH_ROW_TOTAL_WIDTH / (slots.length - 1)) : 0;
    const startX = centerX - (spacing * (slots.length - 1)) / 2;
    slots.forEach(function (item, index) {
      const x = startX + spacing * index;
      drawGraphEdge(centerX, y - GRAPH_ROW_PARENT_OFFSET, x, y - GRAPH_EDGE_NODE_GAP);
      if (item === "__expand__") {
        const expandType = limitKey.toLowerCase().indexOf("children") !== -1 || limitKey === "siblings" ? "languoid" : null;
        drawActionNode(x, y, "+" + hiddenCount, onExpand, expandType);
      } else {
        drawGraphEntity(treeNode(item), x, y, item === currentId ? GRAPH_ROW_CURRENT_RADIUS : GRAPH_ROW_NODE_RADIUS, item === currentId ? "current" : "");
      }
    });
  }

  function visibleFamilyItems(ids, limit) {
    return ids.slice(0, effectiveGraphLimit(limit, ids.length));
  }

  function drawFamilyLevel(summary, siblingIds, centerX, y, anchorY) {
    const visible = visibleFamilyItems(siblingIds, state.graphCategoryLimits.familySiblings);
    const hiddenCount = Math.max(siblingIds.length - visible.length, 0);
    const sideSpacing = Math.min(FAMILY_SIDE_SPACING, GRAPH_FAMILY_SIBLING_FALLBACK_SPREAD / Math.max(visible.length, 2));

    drawGraphEdge(centerX, anchorY, centerX, y - GRAPH_EDGE_NODE_GAP);
    drawGraphEntity(summary, centerX, y, GRAPH_ROW_CURRENT_RADIUS, "current");

    visible.forEach(function (id, index) {
      const side = index % 2 === 0 ? -1 : 1;
      const offset = Math.floor(index / 2) + 1;
      const x = centerX + side * sideSpacing * offset;
      drawGraphEdge(centerX, anchorY, x, y - GRAPH_EDGE_NODE_GAP);
      drawGraphEntity(treeNode(id), x, y, GRAPH_ROW_NODE_RADIUS, "");
    });

    if (hiddenCount > 0) {
      const expandOffset = Math.floor(visible.length / 2) + 1;
      const expandX = centerX - sideSpacing * expandOffset;
      drawGraphEdge(centerX, anchorY, expandX, y - GRAPH_EDGE_NODE_GAP);
      drawActionNode(expandX, y, "+" + hiddenCount, function () {
        state.graphCategoryLimits.familySiblings += GRAPH_FAMILY_INCREMENT;
        renderGraph(summary, detailsFor(summary.id));
      }, "languoid");
    }
  }

  function renderHierarchyGraph(summary, detail) {
    const centerX = GRAPH_CENTER_X;
    const ancestry = relationItems(detail, "Family tree").slice().reverse();
    const visibleAncestors = ancestry.slice(Math.max(0, ancestry.length - state.graphCategoryLimits.familyAncestors));
    const hiddenAncestorCount = ancestry.length - visibleAncestors.length;
    const siblings = relationItems(detail, "Siblings");
    const hasSiblingRow = siblings.length > 0;
    const chain = visibleAncestors.slice();
    const startY = chain.length > 0 ? GRAPH_FAMILY_CHAIN_START_Y : GRAPH_FAMILY_EMPTY_START_Y;
    if (chain.length > 0) {
      drawVerticalChain(chain, centerX, startY, FAMILY_VERTICAL_STEP, "");
    }
    if (hiddenAncestorCount > 0) {
      drawGraphEdge(centerX, GRAPH_FAMILY_TOP_Y, centerX, startY - GRAPH_EDGE_NODE_GAP);
      drawActionNode(centerX, GRAPH_FAMILY_TOP_Y, "+" + hiddenAncestorCount, function () {
        state.graphCategoryLimits.familyAncestors += GRAPH_EXPAND_INCREMENT;
        renderGraph(summary, detail);
      }, "languoid");
    }
    const anchorY = chain.length > 0 ? startY + (chain.length - 1) * FAMILY_VERTICAL_STEP + GRAPH_EDGE_NODE_GAP : GRAPH_FAMILY_EMPTY_ANCHOR_Y;
    const currentY = chain.length > 0
      ? startY + chain.length * FAMILY_VERTICAL_STEP + (hasSiblingRow ? GRAPH_FAMILY_SIBLING_OFFSET_Y : 0)
      : GRAPH_FAMILY_EMPTY_START_Y;
    if (hasSiblingRow) {
      drawFamilyLevel(summary, siblings, centerX, currentY, anchorY);
    } else {
      drawGraphEdge(centerX, anchorY, centerX, currentY - GRAPH_EDGE_NODE_GAP);
      drawGraphEntity(summary, centerX, currentY, GRAPH_ROW_CURRENT_RADIUS, "current");
    }
    const children = relationItems(detail, "Children");
    if (children.length > 0) {
      drawRow(children, centerX, currentY + FAMILY_LEVEL_GAP, "treeChildren", summary.id, function () {
        state.graphCategoryLimits.treeChildren += GRAPH_FAMILY_INCREMENT;
        renderGraph(summary, detail);
      });
    }
  }

  function availableGraphViews(summary, detail) {
    const available = ["mixed"];

    if (relationItems(detail, "Scripts").length > 0) {
      available.push("scripts");
    }

    const regionCount = summary.t === "region"
      ? uniqueList(
          relationItems(detail, "Parent region")
            .concat(relationItems(detail, "Child regions"))
            .concat(relationItems(detail, "Subdivisions"))
        ).length
      : relationItems(detail, "Regions").length;
    if (regionCount > 0) {
      available.push("regions");
    }

    if (
      summary.t === "languoid" && (
        relationItems(detail, "Family tree").length > 0 ||
        relationItems(detail, "Parent").length > 0 ||
        relationItems(detail, "Children").length > 0 ||
        relationItems(detail, "Siblings").length > 0
      )
    ) {
      available.push("family");
    }

    return available;
  }

  function syncGraphView(summary, detail) {
    const allowed = availableGraphViews(summary, detail);
    Array.prototype.forEach.call(graphViewEl.options, function (option) {
      option.disabled = allowed.indexOf(option.value) === -1;
    });
    if (allowed.indexOf(state.graphView) === -1) {
      state.graphView = "mixed";
    }
    graphViewEl.value = state.graphView;
  }

  function renderGraph(summary, detail) {
    graphEl.replaceChildren();
    syncGraphView(summary, detail);
    if (state.graphView === "family") {
      renderHierarchyGraph(summary, detail);
    } else {
      drawCenteredCircle(summary, detail);
    }
    adjustGraphViewport();
  }

  function renderLoading() {
    entityActionsEl.replaceChildren();
    entityWarningEl.textContent = "";
    propertiesEl.textContent = "Loading properties…";
    resourcesEl.textContent = "Loading resources…";
    relationsEl.textContent = "Loading connections…";
    graphEl.replaceChildren();
    resetGraphViewport();
  }

  function resetGraphState(resetView) {
    if (resetView) {
      state.graphView = "mixed";
    }
    state.graphCategoryLimits = Object.assign({}, GRAPH_CATEGORY_DEFAULTS);
  }

  async function renderEntity(entityId) {
    const entity = Object.assign({ id: entityId }, summaries[entityId]);
    state.pendingId = entityId;
    state.currentId = entityId;

    resetGraphState(true);
    state.expandedRelationGroups = {};
    entityTypeEl.textContent = titleCase(entity.t);
    entityNameEl.textContent = entity.n;
    entitySubtitleEl.textContent = entity.s;
    if (!detailsFor(entityId)) {
      renderLoading();
      await loadBucket(entity.b);
      if (state.pendingId !== entityId) {
        return;
      }
    }
    const detail = detailsFor(entityId);
    if (!detail) {
      entityActionsEl.replaceChildren();
      entityWarningEl.textContent = "";
      propertiesEl.textContent = "No properties found.";
      resourcesEl.textContent = "No external resources found.";
      relationsEl.textContent = "No connections found.";
      return;
    }
    if (state.pendingId !== entityId) {
      return;
    }
    renderEntityActions(entity, detail);
    renderEntityWarning(detail);
    renderProperties(entity, detail);
    renderResources(entity, detail);
    renderRelations(entityId, detail);
    renderGraph(entity, detail);
    searchResultsEl.replaceChildren();
    searchEl.value = "";
    window.location.hash = entity.id;
    state.pendingId = null;
  }

  function navigateTo(entityId) {
    if (!summaries[entityId]) {
      return;
    }
    renderEntity(entityId);
  }

  function syncFromHash() {
    const entityId = window.location.hash ? window.location.hash.slice(1) : data.meta.defaultId;
    if (!summaries[entityId] || entityId === state.currentId) {
      return;
    }
    navigateTo(entityId);
  }

  searchEl.addEventListener("input", function (event) {
    renderSearchResults(event.target.value);
  });

  searchEl.addEventListener("keydown", function (event) {
    const results = Array.prototype.slice.call(searchResultsEl.querySelectorAll("button"));
    if (event.key === "ArrowDown") {
      if (results.length === 0) {
        return;
      }
      event.preventDefault();
      results[0].focus();
      return;
    }
    if (event.key !== "Enter") {
      return;
    }
    const first = searchResultsEl.querySelector("button");
    if (first) {
      first.click();
    }
  });

  searchResultsEl.addEventListener("keydown", function (event) {
    const results = Array.prototype.slice.call(searchResultsEl.querySelectorAll("button"));
    const currentIndex = results.indexOf(document.activeElement);
    if (event.key === "ArrowDown") {
      if (currentIndex === -1 || currentIndex === results.length - 1) {
        return;
      }
      event.preventDefault();
      results[currentIndex + 1].focus();
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (currentIndex <= 0) {
        searchEl.focus();
        return;
      }
      results[currentIndex - 1].focus();
    }
  });

  graphViewEl.addEventListener("change", function (event) {
    state.graphView = event.target.value;
    if (state.currentId && summaries[state.currentId]) {
      loadBucket(summaries[state.currentId].b).then(function () {
        const current = Object.assign({ id: state.currentId }, summaries[state.currentId]);
        const detail = detailsFor(state.currentId);
        if (detail) {
          resetGraphState(false);
          renderGraph(current, detail);
        }
      });
    }
  });

  window.addEventListener("hashchange", syncFromHash);

  const initialId = window.location.hash ? window.location.hash.slice(1) : data.meta.defaultId;
  navigateTo(initialId);
})();
