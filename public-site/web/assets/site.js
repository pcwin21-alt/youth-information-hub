
(() => {
  function setFeedback(card, message, isError) {
    const feedback = card && card.querySelector('[data-article-feedback]');
    if (!feedback) {
      return;
    }
    if (feedback._timer) {
      clearTimeout(feedback._timer);
    }
    feedback.textContent = message;
    feedback.classList.toggle('error', Boolean(isError));
    feedback._timer = window.setTimeout(() => {
      feedback.textContent = '';
      feedback.classList.remove('error');
    }, 2200);
  }

  function fallbackCopy(text) {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'absolute';
    area.style.left = '-9999px';
    document.body.appendChild(area);
    area.select();
    const copied = document.execCommand('copy');
    document.body.removeChild(area);
    if (!copied) {
      throw new Error('copy_failed');
    }
  }

  async function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return;
    }
    fallbackCopy(text);
  }

  function normalizeNewsDateRange(startValue, endValue) {
    let startDate = startValue || '';
    let endDate = endValue || '';
    if (startDate && endDate && startDate > endDate) {
      const swappedStart = endDate;
      endDate = startDate;
      startDate = swappedStart;
    }
    return { startDate, endDate };
  }

  function formatNewsDateRange(startDate, endDate) {
    if (startDate && endDate) {
      return `${startDate} - ${endDate}`;
    }
    if (startDate) {
      return `${startDate}부터`;
    }
    if (endDate) {
      return `${endDate}까지`;
    }
    return '전체';
  }

  function openNewsDatePicker(input) {
    if (!input) {
      return;
    }
    input.focus({ preventScroll: true });
    if (typeof input.showPicker === 'function') {
      try {
        input.showPicker();
      } catch (error) {
        // Some browsers limit showPicker; keep focus fallback.
      }
    }
  }

  function normalizeSearchQuery(value) {
    return (value || '').trim().replace(/\s+/g, ' ');
  }

  function cardMatchesSearch(card, query) {
    const normalizedQuery = normalizeSearchQuery(query);
    if (!normalizedQuery) {
      return true;
    }
    const searchText = (card.getAttribute('data-article-search') || '').toLowerCase();
    return normalizedQuery.toLowerCase().split(' ').every((term) => searchText.includes(term));
  }

  function formatSearchLabel(query) {
    const normalizedQuery = normalizeSearchQuery(query);
    return normalizedQuery ? `검색 "${normalizedQuery}"` : '';
  }

  function contentDirectionLabel(value) {
    const labels = {
      promotion: '홍보성',
      column: '칼럼·기고',
      insight: '인사이트·분석',
      report: '일반보도',
      official_release: '공식자료',
      unknown: '미분류',
    };
    return labels[value] || value || '';
  }

  function getRegionMapTooltip(region) {
    if (!region || !region.dataset || !region.dataset.regionMapId) {
      return null;
    }
    const svg = region.closest('.filter-region-map-svg');
    if (!svg) {
      return null;
    }
    return Array.from(svg.querySelectorAll('.filter-region-map-tooltip'))
      .find((tooltip) => tooltip.dataset.regionMapTooltip === region.dataset.regionMapId) || null;
  }

  function syncRegionMapTooltipState(region) {
    const tooltip = getRegionMapTooltip(region);
    if (!tooltip) {
      return;
    }
    tooltip.classList.toggle('active', region.classList.contains('active'));
    tooltip.classList.toggle('is-empty', region.classList.contains('is-empty'));
  }

  function setRegionMapTooltipVisibility(target, isVisible) {
    const region = target.closest && target.closest('.filter-region-map-region');
    if (!region) {
      return;
    }
    const tooltip = getRegionMapTooltip(region);
    if (!tooltip) {
      return;
    }
    if (isVisible) {
      const svg = region.closest('.filter-region-map-svg');
      svg.querySelectorAll('.filter-region-map-tooltip.is-visible').forEach((item) => {
        if (item !== tooltip) {
          item.classList.remove('is-visible');
        }
      });
    }
    tooltip.classList.toggle('is-visible', isVisible);
  }

  function updateRegionFilterButtonCount(button, count) {
    const label = button.getAttribute('data-region-label') || button.getAttribute('data-filter-value') || '';
    const safeCount = Number.isFinite(count) ? count : 0;
    if (label) {
      button.setAttribute('aria-label', `${label} ${safeCount}건 선택`);
    }
    const countNodes = [];
    const inlineCountNode = button.querySelector('[data-region-map-count]');
    if (inlineCountNode) {
      countNodes.push(inlineCountNode);
    }
    const tooltip = getRegionMapTooltip(button);
    const tooltipCountNode = tooltip && tooltip.querySelector('[data-region-map-count]');
    if (tooltipCountNode) {
      countNodes.push(tooltipCountNode);
    }
    countNodes.forEach((countNode) => {
      countNode.textContent = `${safeCount}건`;
    });
    button.dataset.regionVisibleCount = String(safeCount);
    button.classList.toggle('is-empty', safeCount === 0);
    syncRegionMapTooltipState(button);
  }

  function bringMapRegionToFront(target) {
    const region = target.closest && target.closest('.filter-region-map-region, .local-map-region');
    if (!region || !region.parentNode) {
      return;
    }
    if (!region.querySelector('.filter-region-map-hit-target, .local-map-hit-target')) {
      return;
    }
    const tooltipLayer = region.parentNode.querySelector('.filter-region-map-tooltip-layer');
    if (tooltipLayer) {
      region.parentNode.insertBefore(region, tooltipLayer);
    } else {
      region.parentNode.appendChild(region);
    }
  }

  function applyNewsFilters(root, selectedDateStart, selectedDateEnd, selectedRegion, selectedDirection, selectedTopic, selectedQuery) {
    const normalizedDates = normalizeNewsDateRange(
      selectedDateStart ?? root.dataset.selectedDateStart ?? root.getAttribute('data-default-date-start') ?? '',
      selectedDateEnd ?? root.dataset.selectedDateEnd ?? root.getAttribute('data-default-date-end') ?? '',
    );
    const activeDateStart = normalizedDates.startDate;
    const activeDateEnd = normalizedDates.endDate;
    const hasDateRange = Boolean(activeDateStart || activeDateEnd);
    const activeRegion = selectedRegion || root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all';
    const activeDirection = selectedDirection || root.dataset.selectedDirection || root.getAttribute('data-default-direction') || 'all';
    const activeTopic = selectedTopic || root.dataset.selectedTopic || root.getAttribute('data-default-topic') || 'all';
    const activeQuery = normalizeSearchQuery(
      selectedQuery ?? root.dataset.selectedSearchQuery ?? root.getAttribute('data-default-search-query') ?? ''
    );
    let activeHourStart = root.dataset.selectedHourStart || root.dataset.selectedHour || 'all';
    let activeHourEnd = root.dataset.selectedHourEnd || root.dataset.selectedHour || 'all';
    if (activeHourStart !== 'all' && activeHourEnd !== 'all' && activeHourStart > activeHourEnd) {
      [activeHourStart, activeHourEnd] = [activeHourEnd, activeHourStart];
    }
    root.dataset.selectedDateStart = activeDateStart;
    root.dataset.selectedDateEnd = activeDateEnd;
    root.dataset.selectedRegion = activeRegion;
    root.dataset.selectedDirection = activeDirection;
    root.dataset.selectedTopic = activeTopic;
    root.dataset.selectedSearchQuery = activeQuery;
    root.dataset.selectedHourStart = activeHourStart;
    root.dataset.selectedHourEnd = activeHourEnd;

    const articleCards = Array.from(root.querySelectorAll('[data-article-date]'));
    const regionCounts = new Map();
    let visibleCount = 0;

    articleCards.forEach((card) => {
      const articleDate = card.getAttribute('data-article-date') || '';
      const articleRegion = card.getAttribute('data-article-region') || '중앙';
      const articleDirection = card.getAttribute('data-article-direction') || 'unknown';
      const articleTopics = (card.getAttribute('data-article-topics') || '').split('|').filter(Boolean);
      const articleHour = card.getAttribute('data-article-hour') || '';
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const regionMatch = activeRegion === 'all' || articleRegion === activeRegion;
      const directionMatch = activeDirection === 'all' || articleDirection === activeDirection;
      const topicMatch = activeTopic === 'all' || articleTopics.includes(activeTopic);
      const hourMatch = (!activeHourStart || activeHourStart === 'all' || articleHour >= activeHourStart)
        && (!activeHourEnd || activeHourEnd === 'all' || articleHour <= activeHourEnd);
      const searchMatch = cardMatchesSearch(card, activeQuery);
      const isMatch = dateMatch && regionMatch && directionMatch && topicMatch && hourMatch && searchMatch;
      if (dateMatch && directionMatch && topicMatch && hourMatch && searchMatch) {
        regionCounts.set(articleRegion, (regionCounts.get(articleRegion) || 0) + 1);
      }
      card.hidden = !isMatch;
      if (isMatch) {
        visibleCount += 1;
      }
    });

    root.querySelectorAll('[data-news-filter]').forEach((button) => {
      const group = button.getAttribute('data-filter-group') || 'date';
      const value = button.getAttribute('data-filter-value') || 'all';
      const isActive = group === 'region'
        ? value === activeRegion
        : group === 'direction'
          ? value === activeDirection
          : group === 'topic'
            ? value === activeTopic
            : group === 'date'
              ? (value === 'all' ? !hasDateRange : activeDateStart === value && activeDateEnd === value)
              : group === 'hour'
                ? (activeHourStart === activeHourEnd && value === activeHourStart)
              : false;
      if (group === 'region' && value !== 'all') {
        updateRegionFilterButtonCount(button, regionCounts.get(value) || 0);
      }
      button.classList.toggle('active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      syncRegionMapTooltipState(button);
    });

    root.querySelectorAll('[data-news-date-input]').forEach((dateInput) => {
      const role = dateInput.getAttribute('data-date-role') || 'start';
      const nextValue = role === 'end' ? activeDateEnd : activeDateStart;
      if (dateInput.value !== nextValue) {
        dateInput.value = nextValue;
      }
    });

    root.querySelectorAll('[data-news-search-input]').forEach((searchInput) => {
      if (searchInput.value !== activeQuery) {
        searchInput.value = activeQuery;
      }
    });

    const status = root.querySelector('[data-news-filter-status]');
    if (status) {
      const dateLabel = formatNewsDateRange(activeDateStart, activeDateEnd);
      const searchLabel = formatSearchLabel(activeQuery);
      if (!hasDateRange && activeRegion === 'all' && activeDirection === 'all' && activeTopic === 'all' && activeHourStart === 'all' && activeHourEnd === 'all' && !searchLabel) {
        status.textContent = `전체 ${visibleCount}건을 보고 있습니다.`;
      } else {
        const parts = [];
        if (activeRegion !== 'all') {
          parts.push(activeRegion);
        }
        if (activeDirection !== 'all') {
          parts.push(contentDirectionLabel(activeDirection));
        }
        if (activeTopic !== 'all') {
          parts.push(`#${activeTopic}`);
        }
        if (activeHourStart !== 'all' || activeHourEnd !== 'all') {
          parts.push(activeHourStart === activeHourEnd
            ? activeHourStart
            : `${activeHourStart === 'all' ? '처음' : activeHourStart}–${activeHourEnd === 'all' ? '마지막' : activeHourEnd}`);
        }
        if (searchLabel) {
          parts.push(searchLabel);
        }
        if (hasDateRange) {
          parts.push(dateLabel);
        }
        status.textContent = `${parts.join(' · ')} 기사 ${visibleCount}건을 보고 있습니다.`;
      }
    }

    const emptyState = root.querySelector('[data-news-empty-state]');
    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  }

  function getPolicyAvailabilityByAttribute(articleCards, targetGroup, attributeName, activeType, activeDateStart, activeDateEnd, hasDateRange, activeQuery) {
    const availableValues = new Set();

    articleCards.forEach((card) => {
      const articleGroup = card.getAttribute('data-policy-group') || 'official';
      if (articleGroup !== targetGroup) {
        return;
      }
      const attributeValue = card.getAttribute(attributeName) || '';
      const articleType = card.getAttribute('data-policy-type') || '기타';
      const articleDate = card.getAttribute('data-article-date') || '';
      const typeMatch = activeType === 'all' || articleType === activeType;
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const searchMatch = cardMatchesSearch(card, activeQuery);

      if (attributeValue && typeMatch && dateMatch && searchMatch) {
        availableValues.add(attributeValue);
      }
    });

    return availableValues;
  }

  function getPolicyCountsByAttribute(articleCards, targetGroup, attributeName, activeType, activeDateStart, activeDateEnd, hasDateRange, activeQuery) {
    const counts = new Map();

    articleCards.forEach((card) => {
      const articleGroup = card.getAttribute('data-policy-group') || 'official';
      if (articleGroup !== targetGroup) {
        return;
      }
      const attributeValue = card.getAttribute(attributeName) || '';
      const articleType = card.getAttribute('data-policy-type') || '기타';
      const articleDate = card.getAttribute('data-article-date') || '';
      const typeMatch = activeType === 'all' || articleType === activeType;
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const searchMatch = cardMatchesSearch(card, activeQuery);

      if (attributeValue && typeMatch && dateMatch && searchMatch) {
        counts.set(attributeValue, (counts.get(attributeValue) || 0) + 1);
      }
    });

    return counts;
  }

  function formatPolicyGroup(value, scopeMode) {
    if (scopeMode === 'hub-detail') {
      if (value === 'official') {
        return '중앙부처 자문·회의';
      }
      if (value === 'local') {
        return '지역 청년정책 네트워크';
      }
      if (value === 'public') {
        return '공공기관 참여·협의';
      }
      return '전체';
    }
    if (value === 'official') {
      return '중앙정부';
    }
    if (value === 'local') {
      return '지자체';
    }
    return '전체';
  }

  function formatPolicyScopeLabel(group, scopeMode) {
    if (scopeMode === 'hub-detail') {
      if (group === 'official') {
        return '부처·기관';
      }
      if (group === 'local') {
        return '지역';
      }
      if (group === 'public') {
        return '공공기관';
      }
      return '세부 구분';
    }
    if (group === 'official') {
      return '중앙부처·기관';
    }
    if (group === 'local') {
      return '지역';
    }
    return '세부 구분';
  }

  function applyPolicyFilters(root, selectedGroup, selectedRegion, selectedType, selectedDateStart, selectedDateEnd, selectedQuery) {
    const normalizedDates = normalizeNewsDateRange(
      selectedDateStart ?? root.dataset.selectedDateStart ?? root.getAttribute('data-default-date-start') ?? '',
      selectedDateEnd ?? root.dataset.selectedDateEnd ?? root.getAttribute('data-default-date-end') ?? '',
    );
    const scopeMode = root.dataset.policyScopeMode || '';
    const activeGroup = selectedGroup || root.dataset.selectedPolicyGroup || root.getAttribute('data-default-policy-group') || 'all';
    let activeRegion = selectedRegion || root.dataset.selectedPolicyRegion || root.getAttribute('data-default-policy-region') || 'all';
    let activeScope = root.dataset.selectedPolicyScope || root.getAttribute('data-default-policy-scope') || 'all';
    const activeType = selectedType || root.dataset.selectedPolicyType || root.getAttribute('data-default-policy-type') || 'all';
    const activeQuery = normalizeSearchQuery(
      selectedQuery ?? root.dataset.selectedSearchQuery ?? root.getAttribute('data-default-search-query') ?? ''
    );
    const activeDateStart = normalizedDates.startDate;
    const activeDateEnd = normalizedDates.endDate;
    const hasDateRange = Boolean(activeDateStart || activeDateEnd);
    const usesPolicyScope = scopeMode === 'authority-region' || scopeMode === 'hub-detail';
    const usesHubDetailScope = scopeMode === 'hub-detail';
    const keepEmptySections = root.dataset.keepEmptySections === 'true';
    const keepEmptyScopes = root.dataset.keepEmptyScopes === 'true';
    root.dataset.selectedPolicyGroup = activeGroup;
    root.dataset.selectedPolicyRegion = activeRegion;
    root.dataset.selectedPolicyScope = activeScope;
    root.dataset.selectedPolicyType = activeType;
    root.dataset.selectedSearchQuery = activeQuery;
    root.dataset.selectedDateStart = activeDateStart;
    root.dataset.selectedDateEnd = activeDateEnd;

    if (usesHubDetailScope) {
      activeRegion = 'all';
      root.dataset.selectedPolicyRegion = 'all';
    }

    const articleCards = Array.from(root.querySelectorAll('[data-policy-card="true"]'));
    const regionTargetGroup = usesPolicyScope ? (activeGroup === 'all' ? 'local' : activeGroup) : activeGroup;
    const availableRegions = getPolicyAvailabilityByAttribute(
      articleCards,
      regionTargetGroup,
      'data-article-region',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    const availableAuthorities = getPolicyAvailabilityByAttribute(
      articleCards,
      'official',
      usesHubDetailScope ? 'data-policy-scope' : 'data-policy-authority',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    const availableLocalScopes = getPolicyAvailabilityByAttribute(
      articleCards,
      'local',
      usesHubDetailScope ? 'data-policy-scope' : 'data-article-region',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    const localScopeCounts = getPolicyCountsByAttribute(
      articleCards,
      'local',
      usesHubDetailScope ? 'data-policy-scope' : 'data-article-region',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    const availablePublicScopes = getPolicyAvailabilityByAttribute(
      articleCards,
      'public',
      'data-policy-scope',
      activeType,
      activeDateStart,
      activeDateEnd,
      hasDateRange,
      activeQuery,
    );
    if (activeRegion !== 'all' && !availableRegions.has(activeRegion)) {
      activeRegion = 'all';
    }
    root.dataset.selectedPolicyRegion = activeRegion;

    let visibleScopeKind = 'all';
    let availableScopes = new Set();
    if (usesPolicyScope) {
      if (activeGroup === 'official') {
        visibleScopeKind = 'official';
        availableScopes = availableAuthorities;
      } else if (activeGroup === 'local') {
        visibleScopeKind = 'local';
        availableScopes = usesHubDetailScope ? availableLocalScopes : availableRegions;
      } else if (usesHubDetailScope && activeGroup === 'public') {
        visibleScopeKind = 'public';
        availableScopes = availablePublicScopes;
      } else {
        activeScope = 'all';
      }
      if (activeScope !== 'all' && !keepEmptyScopes && !availableScopes.has(activeScope)) {
        activeScope = 'all';
      }
      root.dataset.selectedPolicyScope = activeScope;
    }

    const visibleByGroup = { official: 0, local: 0, public: 0, related: 0 };
    let visibleCount = 0;

    articleCards.forEach((card) => {
      const articleGroup = card.getAttribute('data-policy-group') || 'official';
      const articleRegion = card.getAttribute('data-article-region') || '중앙';
      const articleAuthority = card.getAttribute('data-policy-authority') || '';
      const articleScope = usesHubDetailScope
        ? (card.getAttribute('data-policy-scope') || '')
        : (articleGroup === 'official' ? articleAuthority : articleRegion);
      const articleType = card.getAttribute('data-policy-type') || '기타';
      const articleDate = card.getAttribute('data-article-date') || '';
      const groupMatch = activeGroup === 'all' || articleGroup === activeGroup;
      const regionMatch = activeRegion === 'all' || articleRegion === activeRegion;
      const scopeMatch = !usesPolicyScope || activeGroup === 'all' || activeScope === 'all' || articleScope === activeScope;
      const typeMatch = activeType === 'all' || articleType === activeType;
      const isAfterStart = !activeDateStart || (articleDate && articleDate >= activeDateStart);
      const isBeforeEnd = !activeDateEnd || (articleDate && articleDate <= activeDateEnd);
      const dateMatch = !hasDateRange || (isAfterStart && isBeforeEnd);
      const searchMatch = cardMatchesSearch(card, activeQuery);
      const isMatch = groupMatch && regionMatch && scopeMatch && typeMatch && dateMatch && searchMatch;
      card.hidden = !isMatch;
      if (isMatch) {
        visibleCount += 1;
        visibleByGroup[articleGroup] = (visibleByGroup[articleGroup] || 0) + 1;
      }
    });

    root.querySelectorAll('[data-policy-filter]').forEach((button) => {
      const group = button.getAttribute('data-filter-group') || 'group';
      const value = button.getAttribute('data-filter-value') || 'all';
      const isScopeButton = button.hasAttribute('data-policy-scope-button');
      let isActive =
        group === 'group' ? value === activeGroup :
        group === 'region' ? value === activeRegion :
        group === 'type' ? value === activeType :
        value === 'all' && !hasDateRange;
      if (group === 'region' && value !== 'all') {
        button.hidden = !availableRegions.has(value);
      }
      if (usesPolicyScope && isScopeButton) {
        const scopeKind = button.getAttribute('data-scope-kind') || 'all';
        if (scopeKind === 'all') {
          button.hidden = false;
        } else if (scopeKind !== visibleScopeKind) {
          button.hidden = true;
        } else {
          button.hidden = !keepEmptyScopes && !availableScopes.has(value);
        }
        if (scopeKind === 'local' && value !== 'all') {
          updateRegionFilterButtonCount(button, localScopeCounts.get(value) || 0);
        }
        isActive = value === activeScope;
      }
      button.classList.toggle('active', isActive);
      button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      syncRegionMapTooltipState(button);
    });

    const scopeLabel = root.querySelector('[data-policy-scope-label]');
    if (scopeLabel && usesPolicyScope) {
      scopeLabel.textContent = formatPolicyScopeLabel(activeGroup, scopeMode);
    }

    root.querySelectorAll('[data-policy-date-input]').forEach((dateInput) => {
      const role = dateInput.getAttribute('data-date-role') || 'start';
      const nextValue = role === 'end' ? activeDateEnd : activeDateStart;
      if (dateInput.value !== nextValue) {
        dateInput.value = nextValue;
      }
    });

    root.querySelectorAll('[data-policy-search-input]').forEach((searchInput) => {
      if (searchInput.value !== activeQuery) {
        searchInput.value = activeQuery;
      }
    });

    root.querySelectorAll('[data-policy-section]').forEach((section) => {
      const sectionGroup = section.getAttribute('data-policy-section') || 'official';
      const visibleInSection = visibleByGroup[sectionGroup] || 0;
      const shouldKeepEmpty = keepEmptySections && (activeGroup === 'all' || sectionGroup === activeGroup);
      section.hidden = visibleInSection === 0 && !shouldKeepEmpty;
      const count = section.querySelector('[data-policy-section-count]');
      if (count) {
        count.textContent = `${visibleInSection}건`;
      }
    });

    const status = root.querySelector('[data-policy-filter-status]');
    if (status) {
      const parts = [];
      if (activeGroup !== 'all') {
        parts.push(formatPolicyGroup(activeGroup, scopeMode));
      }
      if (usesPolicyScope && activeGroup !== 'all' && activeScope !== 'all') {
        parts.push(activeScope);
      } else if (activeRegion !== 'all') {
        parts.push(activeRegion);
      }
      if (activeType !== 'all') {
        parts.push(activeType);
      }
      if (activeQuery) {
        parts.push(formatSearchLabel(activeQuery));
      }
      if (hasDateRange) {
        parts.push(formatNewsDateRange(activeDateStart, activeDateEnd));
      }
      if (parts.length === 0) {
        status.textContent = `전체 ${visibleCount}건을 보고 있습니다.`;
      } else {
        status.textContent = `${parts.join(' · ')} ${visibleCount}건을 보고 있습니다.`;
      }
    }

    const emptyState = root.querySelector('[data-policy-empty-state]');
    if (emptyState) {
      emptyState.hidden = visibleCount !== 0;
    }
  }

  function markGuideSeen() {
    try {
      localStorage.setItem('youthTogetherGuideSeen-v1', '1');
    } catch (error) {
      // ignore storage errors
    }
  }

  function closeGuideOverlay(overlay, shouldPersist) {
    if (!overlay) {
      return;
    }
    if (shouldPersist) {
      markGuideSeen();
    }
    overlay.hidden = true;
    document.body.classList.remove('is-guide-open');
  }

  function setOfficialView(activeView) {
    document.querySelectorAll('[data-official-view-tab]').forEach((tab) => {
      const isActive = tab.getAttribute('data-official-view-tab') === activeView;
      tab.classList.toggle('active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
      tab.tabIndex = isActive ? 0 : -1;
    });
    document.querySelectorAll('[data-official-view-panel]').forEach((panel) => {
      panel.hidden = panel.getAttribute('data-official-view-panel') !== activeView;
    });
  }

  function setLocalMaterialView(activeView) {
    document.querySelectorAll('[data-local-view-tab]').forEach((tab) => {
      const isActive = tab.getAttribute('data-local-view-tab') === activeView;
      tab.classList.toggle('active', isActive);
      tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
      tab.tabIndex = isActive ? 0 : -1;
    });
    document.querySelectorAll('[data-local-view-panel]').forEach((panel) => {
      panel.hidden = panel.getAttribute('data-local-view-panel') !== activeView;
    });
  }

  function monthKeyFromDate(date) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  }

  function newsFilterStageValue(root, pendingKey, selectedKey, fallback = '') {
    return root.dataset[pendingKey] ?? root.dataset[selectedKey] ?? fallback;
  }

  function syncNewsFilterStage(root) {
    if (!root.querySelector('[data-news-range-filter]')) return;
    const topic = newsFilterStageValue(root, 'pendingTopic', 'selectedTopic', 'all');
    let hourStart = newsFilterStageValue(root, 'pendingHourStart', 'selectedHourStart', 'all');
    let hourEnd = newsFilterStageValue(root, 'pendingHourEnd', 'selectedHourEnd', 'all');
    if (hourStart !== 'all' && hourEnd !== 'all' && hourStart > hourEnd) {
      [hourStart, hourEnd] = [hourEnd, hourStart];
    }
    const query = newsFilterStageValue(root, 'pendingSearchQuery', 'selectedSearchQuery', '');
    root.querySelectorAll('[data-news-filter-stage="topic"]').forEach((button) => {
      const active = (button.getAttribute('data-filter-value') || 'all') === topic;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    const hourStartSelect = root.querySelector('[data-news-hour-start]');
    const hourEndSelect = root.querySelector('[data-news-hour-end]');
    if (hourStartSelect && hourStartSelect.value !== hourStart) hourStartSelect.value = hourStart;
    if (hourEndSelect && hourEndSelect.value !== hourEnd) hourEndSelect.value = hourEnd;
    const searchInput = root.querySelector('[data-news-search-stage]');
    if (searchInput && searchInput.value !== query) searchInput.value = query;
  }

  function renderNewsRangeCalendar(root) {
    const calendar = root.querySelector('[data-news-range-calendar]');
    if (!calendar) return;
    const dates = Array.from(root.querySelectorAll('[data-article-date]'))
      .map((card) => card.getAttribute('data-article-date') || '')
      .filter(Boolean)
      .sort();
    if (!dates.length) return;
    const earliestMonth = dates[0].slice(0, 7);
    const latestMonth = dates[dates.length - 1].slice(0, 7);
    let visibleMonth = root.dataset.newsCalendarMonth || latestMonth;
    if (visibleMonth < earliestMonth) visibleMonth = earliestMonth;
    if (visibleMonth > latestMonth) visibleMonth = latestMonth;
    root.dataset.newsCalendarMonth = visibleMonth;
    const [year, month] = visibleMonth.split('-').map(Number);
    const countByDate = new Map();
    dates.forEach((date) => countByDate.set(date, (countByDate.get(date) || 0) + 1));
    const pendingStart = root.dataset.pendingDateStart || root.dataset.selectedDateStart || '';
    const pendingEnd = root.dataset.pendingDateEnd || root.dataset.selectedDateEnd || '';
    const label = root.querySelector('[data-news-calendar-label]');
    if (label) label.textContent = `${year}년 ${month}월`;
    const previous = root.querySelector('[data-news-calendar-prev]');
    const next = root.querySelector('[data-news-calendar-next]');
    if (previous) previous.disabled = visibleMonth <= earliestMonth;
    if (next) next.disabled = visibleMonth >= latestMonth;
    calendar.replaceChildren();
    ['일', '월', '화', '수', '목', '금', '토'].forEach((weekday) => {
      const name = document.createElement('span');
      name.className = 'news-calendar-weekday'; name.textContent = weekday; calendar.append(name);
    });
    const firstDay = new Date(year, month - 1, 1).getDay();
    for (let blank = 0; blank < firstDay; blank += 1) {
      const spacer = document.createElement('span'); spacer.className = 'news-calendar-day is-blank'; calendar.append(spacer);
    }
    const lastDay = new Date(year, month, 0).getDate();
    for (let day = 1; day <= lastDay; day += 1) {
      const date = `${visibleMonth}-${String(day).padStart(2, '0')}`;
      const count = countByDate.get(date) || 0;
      const button = document.createElement('button');
      button.type = 'button'; button.className = 'news-calendar-day'; button.dataset.newsCalendarDate = date;
      // A range endpoint can legitimately be a day with no matching article.
      // Keep every calendar date selectable; the resulting empty range is a
      // valid, explicit filter state rather than an unreachable one.
      button.classList.toggle('is-empty', count === 0);
      const inRange = pendingStart && pendingEnd && date >= pendingStart && date <= pendingEnd;
      button.classList.toggle('is-selected', date === pendingStart || date === pendingEnd);
      button.classList.toggle('is-in-range', Boolean(inRange && date !== pendingStart && date !== pendingEnd));
      button.setAttribute('aria-pressed', String(date === pendingStart || date === pendingEnd));
      button.setAttribute('aria-label', `${date} 기사 ${count}건, 날짜 선택`);
      const dayNumber = document.createElement('span'); dayNumber.textContent = String(day);
      const countLabel = document.createElement('small'); countLabel.textContent = `${count}건`;
      button.append(dayNumber, countLabel); calendar.append(button);
    }
  }

  function initializeNewsRangeFilters() {
    document.querySelectorAll('[data-news-filter-root]').forEach((root) => {
      if (!root.querySelector('[data-news-range-filter]')) return;
      root.dataset.pendingDateStart = root.dataset.selectedDateStart || '';
      root.dataset.pendingDateEnd = root.dataset.selectedDateEnd || '';
      root.dataset.pendingTopic = root.dataset.selectedTopic || 'all';
      root.dataset.pendingHourStart = root.dataset.selectedHourStart || root.dataset.selectedHour || 'all';
      root.dataset.pendingHourEnd = root.dataset.selectedHourEnd || root.dataset.selectedHour || 'all';
      root.dataset.pendingSearchQuery = root.dataset.selectedSearchQuery || '';
      syncNewsFilterStage(root); renderNewsRangeCalendar(root);
      root.addEventListener('click', (event) => {
        const calendarMove = event.target.closest('[data-news-calendar-prev], [data-news-calendar-next]');
        if (calendarMove) {
          event.stopPropagation();
          const [year, month] = (root.dataset.newsCalendarMonth || '').split('-').map(Number);
          root.dataset.newsCalendarMonth = monthKeyFromDate(new Date(year, month - 1 + (calendarMove.hasAttribute('data-news-calendar-next') ? 1 : -1), 1));
          renderNewsRangeCalendar(root); return;
        }
        const calendarDate = event.target.closest('[data-news-calendar-date]');
        if (calendarDate) {
          event.stopPropagation();
          const value = calendarDate.dataset.newsCalendarDate || '';
          const start = root.dataset.pendingDateStart || '';
          const end = root.dataset.pendingDateEnd || '';
          if (!start || !end || root.dataset.newsRangeAnchor !== 'true') {
            root.dataset.pendingDateStart = value; root.dataset.pendingDateEnd = value; root.dataset.newsRangeAnchor = 'true';
          } else {
            root.dataset.pendingDateStart = value < start ? value : start;
            root.dataset.pendingDateEnd = value < start ? start : value;
            root.dataset.newsRangeAnchor = 'false';
          }
          // Date selection is a primary result control: show its matching
          // articles immediately.  The Apply button still commits any staged
          // hour, topic, and keyword changes alongside the chosen dates.
          applyNewsFilters(
            root,
            root.dataset.pendingDateStart || '',
            root.dataset.pendingDateEnd || '',
            root.dataset.selectedRegion || 'all',
            root.dataset.selectedDirection || 'all',
            root.dataset.selectedTopic || 'all',
            root.dataset.selectedSearchQuery || '',
          );
          renderNewsRangeCalendar(root); return;
        }
        const topic = event.target.closest('[data-news-filter-stage="topic"]');
        if (topic) {
          event.stopPropagation(); root.dataset.pendingTopic = topic.getAttribute('data-filter-value') || 'all'; syncNewsFilterStage(root); return;
        }
        if (event.target.closest('[data-news-filter-apply]')) {
          event.stopPropagation();
          root.dataset.selectedHourStart = root.dataset.pendingHourStart || 'all';
          root.dataset.selectedHourEnd = root.dataset.pendingHourEnd || 'all';
          applyNewsFilters(root, root.dataset.pendingDateStart || '', root.dataset.pendingDateEnd || '', root.dataset.selectedRegion || 'all', root.dataset.selectedDirection || 'all', root.dataset.pendingTopic || 'all', root.dataset.pendingSearchQuery || '');
          syncNewsFilterStage(root); renderNewsRangeCalendar(root); return;
        }
        if (event.target.closest('[data-news-filter-reset]')) {
          event.stopPropagation(); root.dataset.pendingDateStart = ''; root.dataset.pendingDateEnd = ''; root.dataset.newsRangeAnchor = 'false';
          root.dataset.pendingTopic = 'all'; root.dataset.pendingHourStart = 'all'; root.dataset.pendingHourEnd = 'all'; root.dataset.pendingSearchQuery = '';
          root.dataset.selectedHour = 'all'; root.dataset.selectedHourStart = 'all'; root.dataset.selectedHourEnd = 'all';
          applyNewsFilters(root, '', '', 'all', 'all', 'all', ''); syncNewsFilterStage(root); renderNewsRangeCalendar(root);
        }
      });
      const hourStartSelect = root.querySelector('[data-news-hour-start]');
      const hourEndSelect = root.querySelector('[data-news-hour-end]');
      if (hourStartSelect) hourStartSelect.addEventListener('change', () => { root.dataset.pendingHourStart = hourStartSelect.value || 'all'; syncNewsFilterStage(root); });
      if (hourEndSelect) hourEndSelect.addEventListener('change', () => { root.dataset.pendingHourEnd = hourEndSelect.value || 'all'; syncNewsFilterStage(root); });
      const searchInput = root.querySelector('[data-news-search-stage]');
      if (searchInput) searchInput.addEventListener('input', () => { root.dataset.pendingSearchQuery = searchInput.value; });
    });
  }

  document.addEventListener('click', async (event) => {
    const guideDismiss = event.target.closest('[data-guide-dismiss]');
    if (guideDismiss) {
      event.preventDefault();
      closeGuideOverlay(document.querySelector('[data-guide-overlay]'), true);
      return;
    }

    const homeBriefingTab = event.target.closest('[data-home-briefing-tab]');
    if (homeBriefingTab) {
      event.preventDefault();
      const root = homeBriefingTab.closest('[data-home-briefing-tabs]');
      const target = homeBriefingTab.getAttribute('data-home-briefing-tab') || '';
      if (root && target) {
        root.querySelectorAll('[data-home-briefing-tab]').forEach((tab) => {
          const isActive = tab === homeBriefingTab;
          tab.classList.toggle('active', isActive);
          tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
          tab.tabIndex = isActive ? 0 : -1;
        });
        root.querySelectorAll('[data-home-briefing-panel]').forEach((panel) => {
          const isActive = panel.getAttribute('data-home-briefing-panel') === target;
          panel.hidden = !isActive;
          panel.classList.toggle('active', isActive);
        });
      }
      return;
    }

    const officialViewTab = event.target.closest('[data-official-view-tab]');
    if (officialViewTab) {
      event.preventDefault();
      setOfficialView(officialViewTab.getAttribute('data-official-view-tab') || 'releases');
      return;
    }

    const localViewTab = event.target.closest('[data-local-view-tab]');
    if (localViewTab) {
      event.preventDefault();
      setLocalMaterialView(localViewTab.getAttribute('data-local-view-tab') || 'releases');
      return;
    }

    const guideOpenLink = event.target.closest('[data-guide-open-link]');
    if (guideOpenLink) {
      markGuideSeen();
      return;
    }

    if (event.target.matches('[data-guide-overlay]')) {
      closeGuideOverlay(event.target, true);
      return;
    }

    const dateLaunch = event.target.closest('[data-news-date-launch], [data-policy-date-launch]');
    if (dateLaunch) {
      const dateInput = dateLaunch.querySelector('[data-news-date-input], [data-policy-date-input]');
      if (dateInput) {
        event.preventDefault();
        openNewsDatePicker(dateInput);
      }
      return;
    }

    const filterButton = event.target.closest('[data-news-filter]');
    if (filterButton) {
      event.preventDefault();
      const root = filterButton.closest('[data-news-filter-root]');
      if (root) {
        const group = filterButton.getAttribute('data-filter-group') || 'date';
        const value = filterButton.getAttribute('data-filter-value') || 'all';
        if (group === 'hour') {
          root.dataset.selectedHour = value;
        }
        applyNewsFilters(
          root,
          group === 'date'
            ? (value === 'all' ? '' : value)
            : (root.dataset.selectedDateStart || root.getAttribute('data-default-date-start') || ''),
          group === 'date'
            ? (value === 'all' ? '' : value)
            : (root.dataset.selectedDateEnd || root.getAttribute('data-default-date-end') || ''),
          group === 'region' ? value : (root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all'),
          group === 'direction' ? value : (root.dataset.selectedDirection || root.getAttribute('data-default-direction') || 'all'),
          group === 'topic' ? value : (root.dataset.selectedTopic || root.getAttribute('data-default-topic') || 'all'),
          root.dataset.selectedSearchQuery || root.getAttribute('data-default-search-query') || '',
        );
      }
      return;
    }

    const policyFilterButton = event.target.closest('[data-policy-filter]');
    if (policyFilterButton) {
      event.preventDefault();
      const root = policyFilterButton.closest('[data-policy-filter-root]');
      if (root) {
        const filterGroup = policyFilterButton.getAttribute('data-filter-group') || 'group';
        const filterValue = policyFilterButton.getAttribute('data-filter-value') || 'all';
        if (filterGroup === 'scope') {
          root.dataset.selectedPolicyScope = filterValue;
        }
        applyPolicyFilters(
          root,
          filterGroup === 'group' ? filterValue : (root.dataset.selectedPolicyGroup || root.getAttribute('data-default-policy-group') || 'all'),
          filterGroup === 'region' ? filterValue : (root.dataset.selectedPolicyRegion || root.getAttribute('data-default-policy-region') || 'all'),
          filterGroup === 'type' ? filterValue : (root.dataset.selectedPolicyType || root.getAttribute('data-default-policy-type') || 'all'),
          filterGroup === 'date' ? '' : (root.dataset.selectedDateStart || root.getAttribute('data-default-date-start') || ''),
          filterGroup === 'date' ? '' : (root.dataset.selectedDateEnd || root.getAttribute('data-default-date-end') || ''),
          root.dataset.selectedSearchQuery || root.getAttribute('data-default-search-query') || '',
        );
      }
      return;
    }

    const button = event.target.closest('[data-article-action]');
    if (!button) {
      return;
    }

    event.preventDefault();
    const card = button.closest('[data-article-card]');
    const url = button.getAttribute('data-article-url') || (card && card.getAttribute('data-article-url')) || '';
    const title = button.getAttribute('data-share-title') || (card && card.getAttribute('data-article-title')) || document.title;
    const action = button.getAttribute('data-article-action');

    if (!url) {
      setFeedback(card, '링크 정보를 찾지 못했습니다.', true);
      return;
    }

    try {
      if (action === 'share' && typeof navigator.share === 'function') {
        await navigator.share({ title, url });
        setFeedback(card, '공유 창을 열었습니다.', false);
        return;
      }

      await copyText(url);
      setFeedback(card, action === 'share' ? '공유 링크를 복사했습니다.' : '링크를 복사했습니다.', false);
    } catch (error) {
      if (error && error.name === 'AbortError') {
        return;
      }
      setFeedback(card, '링크 복사에 실패했습니다.', true);
    }
  });

  document.addEventListener('keydown', (event) => {
    const currentTab = event.target.closest && event.target.closest('[data-official-view-tab], [data-local-view-tab]');
    if (!currentTab || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      return;
    }

    const calendarMove = event.target.closest('[data-news-calendar-prev], [data-news-calendar-next]');
    if (calendarMove) {
      const root = calendarMove.closest('[data-news-filter-root]');
      if (root) {
        const [year, month] = (root.dataset.newsCalendarMonth || '').split('-').map(Number);
        const moved = new Date(year, month - 1 + (calendarMove.hasAttribute('data-news-calendar-next') ? 1 : -1), 1);
        root.dataset.newsCalendarMonth = monthKeyFromDate(moved); renderNewsRangeCalendar(root);
      }
      return;
    }

    const calendarDate = event.target.closest('[data-news-calendar-date]');
    if (calendarDate) {
      const root = calendarDate.closest('[data-news-filter-root]');
      const value = calendarDate.dataset.newsCalendarDate || '';
      if (root && value) {
        const start = root.dataset.pendingDateStart || '';
        const end = root.dataset.pendingDateEnd || '';
        if (!start || !end || root.dataset.newsRangeAnchor !== 'true') {
          root.dataset.pendingDateStart = value; root.dataset.pendingDateEnd = value; root.dataset.newsRangeAnchor = 'true';
        } else {
          root.dataset.pendingDateStart = value < start ? value : start;
          root.dataset.pendingDateEnd = value < start ? start : value;
          root.dataset.newsRangeAnchor = 'false';
        }
        renderNewsRangeCalendar(root);
      }
      return;
    }

    const stagedTopic = event.target.closest('[data-news-filter-stage="topic"]');
    if (stagedTopic) {
      const root = stagedTopic.closest('[data-news-filter-root]');
      if (root) { root.dataset.pendingTopic = stagedTopic.getAttribute('data-filter-value') || 'all'; syncNewsFilterStage(root); }
      return;
    }

    const applyStagedFilters = event.target.closest('[data-news-filter-apply]');
    if (applyStagedFilters) {
      const root = applyStagedFilters.closest('[data-news-filter-root]');
      if (root) {
        root.dataset.selectedHourStart = root.dataset.pendingHourStart || 'all';
        root.dataset.selectedHourEnd = root.dataset.pendingHourEnd || 'all';
        applyNewsFilters(root, root.dataset.pendingDateStart || '', root.dataset.pendingDateEnd || '', root.dataset.selectedRegion || 'all', root.dataset.selectedDirection || 'all', root.dataset.pendingTopic || 'all', root.dataset.pendingSearchQuery || '');
        syncNewsFilterStage(root); renderNewsRangeCalendar(root);
      }
      return;
    }

    const resetStagedFilters = event.target.closest('[data-news-filter-reset]');
    if (resetStagedFilters) {
      const root = resetStagedFilters.closest('[data-news-filter-root]');
      if (root) {
        root.dataset.pendingDateStart = ''; root.dataset.pendingDateEnd = ''; root.dataset.newsRangeAnchor = 'false';
        root.dataset.pendingTopic = 'all'; root.dataset.pendingHourStart = 'all'; root.dataset.pendingHourEnd = 'all'; root.dataset.pendingSearchQuery = '';
        root.dataset.selectedHour = 'all'; root.dataset.selectedHourStart = 'all'; root.dataset.selectedHourEnd = 'all';
        applyNewsFilters(root, '', '', 'all', 'all', 'all', ''); syncNewsFilterStage(root); renderNewsRangeCalendar(root);
      }
      return;
    }
    const isLocalTab = currentTab.hasAttribute('data-local-view-tab');
    const tabs = Array.from(document.querySelectorAll(isLocalTab ? '[data-local-view-tab]' : '[data-official-view-tab]'));
    const currentIndex = tabs.indexOf(currentTab);
    const targetIndex = event.key === 'Home' ? 0
      : event.key === 'End' ? tabs.length - 1
      : (currentIndex + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
    const nextTab = tabs[targetIndex];
    if (nextTab) {
      event.preventDefault();
      if (isLocalTab) {
        setLocalMaterialView(nextTab.getAttribute('data-local-view-tab') || 'releases');
      } else {
        setOfficialView(nextTab.getAttribute('data-official-view-tab') || 'releases');
      }
      nextTab.focus();
    }
  });

  document.addEventListener('pointerover', (event) => {
    bringMapRegionToFront(event.target);
    setRegionMapTooltipVisibility(event.target, true);
  });

  document.addEventListener('pointerout', (event) => {
    const region = event.target.closest && event.target.closest('.filter-region-map-region');
    const relatedTarget = event.relatedTarget;
    const relatedRegion = relatedTarget && relatedTarget.closest
      ? relatedTarget.closest('.filter-region-map-region')
      : null;
    if (region && relatedRegion !== region) {
      setRegionMapTooltipVisibility(region, false);
    }
  });

  document.addEventListener('focusin', (event) => {
    bringMapRegionToFront(event.target);
    setRegionMapTooltipVisibility(event.target, true);
  });

  document.addEventListener('focusout', (event) => {
    setRegionMapTooltipVisibility(event.target, false);
  });

  const pageParams = new URLSearchParams(window.location.search);
  const queryFromUrl = normalizeSearchQuery(pageParams.get('q') || pageParams.get('keyword') || '');
  const topicFromUrl = normalizeSearchQuery(pageParams.get('topic') || '');
  const directionFromUrl = normalizeSearchQuery(pageParams.get('direction') || '');
  const regionFromUrl = normalizeSearchQuery(pageParams.get('region') || '');

  document.querySelectorAll('[data-news-filter-root]').forEach((root) => {
    applyNewsFilters(
      root,
      root.getAttribute('data-default-date-start') || '',
      root.getAttribute('data-default-date-end') || '',
      regionFromUrl || root.getAttribute('data-default-region') || 'all',
      directionFromUrl || root.getAttribute('data-default-direction') || 'all',
      topicFromUrl || root.getAttribute('data-default-topic') || 'all',
      queryFromUrl || root.getAttribute('data-default-search-query') || '',
    );
  });
  initializeNewsRangeFilters();

  document.querySelectorAll('[data-policy-filter-root]').forEach((root) => {
    applyPolicyFilters(
      root,
      root.getAttribute('data-default-policy-group') || 'all',
      root.getAttribute('data-default-policy-region') || 'all',
      root.getAttribute('data-default-policy-type') || 'all',
      root.getAttribute('data-default-date-start') || '',
      root.getAttribute('data-default-date-end') || '',
      root.getAttribute('data-default-search-query') || '',
    );
  });

  document.addEventListener('input', (event) => {
    const stagedSearchInput = event.target.closest('[data-news-search-stage]');
    if (stagedSearchInput) {
      const root = stagedSearchInput.closest('[data-news-filter-root]');
      if (root) root.dataset.pendingSearchQuery = stagedSearchInput.value;
      return;
    }

    const searchInput = event.target.closest('[data-news-search-input]');
    if (searchInput) {
      const root = searchInput.closest('[data-news-filter-root]');
      if (!root) {
        return;
      }
      applyNewsFilters(
        root,
        root.dataset.selectedDateStart || root.getAttribute('data-default-date-start') || '',
        root.dataset.selectedDateEnd || root.getAttribute('data-default-date-end') || '',
        root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all',
        root.dataset.selectedDirection || root.getAttribute('data-default-direction') || 'all',
        root.dataset.selectedTopic || root.getAttribute('data-default-topic') || 'all',
        searchInput.value,
      );
      return;
    }

    const policySearchInput = event.target.closest('[data-policy-search-input]');
    if (!policySearchInput) {
      return;
    }
    const policyRoot = policySearchInput.closest('[data-policy-filter-root]');
    if (!policyRoot) {
      return;
    }
    applyPolicyFilters(
      policyRoot,
      policyRoot.dataset.selectedPolicyGroup || policyRoot.getAttribute('data-default-policy-group') || 'all',
      policyRoot.dataset.selectedPolicyRegion || policyRoot.getAttribute('data-default-policy-region') || 'all',
      policyRoot.dataset.selectedPolicyType || policyRoot.getAttribute('data-default-policy-type') || 'all',
      policyRoot.dataset.selectedDateStart || policyRoot.getAttribute('data-default-date-start') || '',
      policyRoot.dataset.selectedDateEnd || policyRoot.getAttribute('data-default-date-end') || '',
      policySearchInput.value,
    );
  });

  document.addEventListener('change', (event) => {
    const hourSelect = event.target.closest('[data-news-hour-start], [data-news-hour-end]');
    if (hourSelect) {
      const root = hourSelect.closest('[data-news-filter-root]');
      if (root) {
        const key = hourSelect.hasAttribute('data-news-hour-end') ? 'pendingHourEnd' : 'pendingHourStart';
        root.dataset[key] = hourSelect.value || 'all';
        syncNewsFilterStage(root);
      }
      return;
    }

    const dateInput = event.target.closest('[data-news-date-input]');
    if (dateInput) {
      const root = dateInput.closest('[data-news-filter-root]');
      if (!root) {
        return;
      }
      const startInput = root.querySelector('[data-news-date-input][data-date-role="start"]');
      const endInput = root.querySelector('[data-news-date-input][data-date-role="end"]');
      applyNewsFilters(
        root,
        startInput ? startInput.value : '',
        endInput ? endInput.value : '',
        root.dataset.selectedRegion || root.getAttribute('data-default-region') || 'all',
        root.dataset.selectedDirection || root.getAttribute('data-default-direction') || 'all',
        root.dataset.selectedTopic || root.getAttribute('data-default-topic') || 'all',
        root.dataset.selectedSearchQuery || root.getAttribute('data-default-search-query') || '',
      );
      return;
    }

    const policyDateInput = event.target.closest('[data-policy-date-input]');
    if (!policyDateInput) {
      return;
    }
    const policyRoot = policyDateInput.closest('[data-policy-filter-root]');
    if (!policyRoot) {
      return;
    }
    const policyStartInput = policyRoot.querySelector('[data-policy-date-input][data-date-role="start"]');
    const policyEndInput = policyRoot.querySelector('[data-policy-date-input][data-date-role="end"]');
    applyPolicyFilters(
      policyRoot,
      policyRoot.dataset.selectedPolicyGroup || policyRoot.getAttribute('data-default-policy-group') || 'all',
      policyRoot.dataset.selectedPolicyRegion || policyRoot.getAttribute('data-default-policy-region') || 'all',
      policyRoot.dataset.selectedPolicyType || policyRoot.getAttribute('data-default-policy-type') || 'all',
      policyStartInput ? policyStartInput.value : '',
      policyEndInput ? policyEndInput.value : '',
      policyRoot.dataset.selectedSearchQuery || policyRoot.getAttribute('data-default-search-query') || '',
    );
  });

  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape') {
      return;
    }
    const overlay = document.querySelector('[data-guide-overlay]');
    if (overlay && !overlay.hidden) {
      closeGuideOverlay(overlay, true);
    }
  });

  function setupLiveClock() {
    const clocks = Array.from(document.querySelectorAll('[data-live-clock]'));
    if (clocks.length === 0) {
      return;
    }
    const weekdayMap = {
      월요일: '월',
      화요일: '화',
      수요일: '수',
      목요일: '목',
      금요일: '금',
      토요일: '토',
      일요일: '일',
      Mon: '월',
      Tue: '화',
      Wed: '수',
      Thu: '목',
      Fri: '금',
      Sat: '토',
      Sun: '일',
    };

    function readPart(parts, type) {
      const part = parts.find((item) => item.type === type);
      return part ? part.value : '';
    }

    function clockParts(now) {
      try {
        const parts = new Intl.DateTimeFormat('ko-KR', {
          timeZone: 'Asia/Seoul',
          year: 'numeric',
          month: '2-digit',
          day: '2-digit',
          weekday: 'short',
          hour: '2-digit',
          minute: '2-digit',
          hour12: false,
        }).formatToParts(now);
        const year = readPart(parts, 'year');
        const month = readPart(parts, 'month');
        const day = readPart(parts, 'day');
        const weekdayRaw = readPart(parts, 'weekday');
        const weekday = weekdayMap[weekdayRaw] || weekdayRaw.replace('요일', '');
        const hour = readPart(parts, 'hour').padStart(2, '0');
        const minute = readPart(parts, 'minute').padStart(2, '0');
        return { year, month, day, weekday, hour, minute };
      } catch (error) {
        const fallback = new Date(now.getTime() + (9 * 60 + now.getTimezoneOffset()) * 60000);
        const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
        return {
          year: String(fallback.getFullYear()),
          month: String(fallback.getMonth() + 1).padStart(2, '0'),
          day: String(fallback.getDate()).padStart(2, '0'),
          weekday: weekdays[fallback.getDay()],
          hour: String(fallback.getHours()).padStart(2, '0'),
          minute: String(fallback.getMinutes()).padStart(2, '0'),
        };
      }
    }

    function updateClock() {
      const parts = clockParts(new Date());
      const fullDate = `${parts.year}.${parts.month}.${parts.day} (${parts.weekday})`;
      const shortDate = `${parts.month}.${parts.day}`;
      const time = `${parts.hour}:${parts.minute}`;
      const iso = `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}:00+09:00`;
      clocks.forEach((clock) => {
        clock.setAttribute('datetime', iso);
        clock.setAttribute('aria-label', `한국시간 ${fullDate} ${time}`);
        const fullDateNode = clock.querySelector('[data-live-clock-date]');
        const shortDateNode = clock.querySelector('[data-live-clock-date-short]');
        const timeNode = clock.querySelector('[data-live-clock-time]');
        if (fullDateNode) {
          fullDateNode.textContent = fullDate;
        }
        if (shortDateNode) {
          shortDateNode.textContent = shortDate;
        }
        if (timeNode) {
          timeNode.textContent = time;
        }
      });
    }

    updateClock();
    window.setInterval(updateClock, 30000);
  }

  function setupPageMarkers() {
    const markerLinks = Array.from(document.querySelectorAll('[data-marker-link]'));
    if (markerLinks.length === 0) {
      return;
    }

    const markerPairs = markerLinks.map((link) => {
      const href = link.getAttribute('href') || '';
      if (!href.startsWith('#')) {
        return null;
      }
      const targetId = decodeURIComponent(href.slice(1));
      const target = document.getElementById(targetId);
      return target ? { link, target } : null;
    }).filter(Boolean);

    if (markerPairs.length === 0) {
      return;
    }

    function activateMarker(activeLink) {
      markerLinks.forEach((link) => {
        const isActive = link === activeLink;
        link.classList.toggle('active', isActive);
        if (isActive) {
          link.setAttribute('aria-current', 'location');
        } else {
          link.removeAttribute('aria-current');
        }
      });
    }

    function activateFromHash() {
      const hash = window.location.hash || '#page-top';
      const current = markerPairs.find(({ link }) => link.getAttribute('href') === hash);
      if (current) {
        activateMarker(current.link);
      }
    }

    if ('IntersectionObserver' in window) {
      const observer = new IntersectionObserver((entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((left, right) => Math.abs(left.boundingClientRect.top) - Math.abs(right.boundingClientRect.top));
        if (visibleEntries.length === 0) {
          return;
        }
        const activePair = markerPairs.find(({ target }) => target === visibleEntries[0].target);
        if (activePair) {
          activateMarker(activePair.link);
        }
      }, {
        rootMargin: '-24% 0px -62% 0px',
        threshold: [0, 0.12, 0.35, 0.7],
      });
      markerPairs.forEach(({ target }) => observer.observe(target));
    }

    markerLinks.forEach((link) => {
      link.addEventListener('click', () => activateMarker(link));
    });
    window.addEventListener('hashchange', activateFromHash);
    activateFromHash();
  }

  setupLiveClock();
  setupPageMarkers();

  const guideOverlay = document.querySelector('[data-guide-overlay]');
  if (guideOverlay && document.body.dataset.page === 'index.html') {
    guideOverlay.hidden = true;
  }
})();


(() => {
  const panel = document.querySelector('[data-floating-nav]');
  const toggle = panel?.querySelector('[data-floating-nav-toggle]');
  const handle = panel?.querySelector('[data-floating-nav-drag]');
  if (!panel || !toggle || !handle) {
    return;
  }

  function setCollapsed(collapsed) {
    panel.classList.toggle('is-collapsed', collapsed);
    toggle.setAttribute('aria-expanded', String(!collapsed));
    toggle.setAttribute('aria-label', collapsed ? '메뉴 펼치기' : '메뉴 접기');
    toggle.textContent = collapsed ? '›' : '‹';
  }

  toggle.addEventListener('click', () => setCollapsed(!panel.classList.contains('is-collapsed')));

  let pointerId = null;
  let originX = 0;
  let originY = 0;
  let originLeft = 0;
  let originTop = 0;

  function startDrag(event) {
    if (event.button !== 0 || event.pointerType === 'mouse' && event.buttons !== 1) {
      return;
    }
    const bounds = panel.getBoundingClientRect();
    pointerId = event.pointerId;
    originX = event.clientX;
    originY = event.clientY;
    originLeft = bounds.left;
    originTop = bounds.top;
    panel.style.right = 'auto';
    panel.style.bottom = 'auto';
    panel.classList.add('is-dragging');
    handle.setPointerCapture?.(pointerId);
    event.preventDefault();
  }

  function moveDrag(event) {
    if (event.pointerId !== pointerId) {
      return;
    }
    const maxLeft = Math.max(8, window.innerWidth - panel.offsetWidth - 8);
    const maxTop = Math.max(8, window.innerHeight - panel.offsetHeight - 8);
    const left = Math.min(maxLeft, Math.max(8, originLeft + event.clientX - originX));
    const top = Math.min(maxTop, Math.max(8, originTop + event.clientY - originY));
    panel.style.left = `${left}px`;
    panel.style.top = `${top}px`;
  }

  function endDrag(event) {
    if (event.pointerId !== pointerId) {
      return;
    }
    if (handle.hasPointerCapture?.(pointerId)) {
      handle.releasePointerCapture(pointerId);
    }
    pointerId = null;
    panel.classList.remove('is-dragging');
  }

  handle.addEventListener('pointerdown', startDrag);
  handle.addEventListener('pointermove', moveDrag);
  handle.addEventListener('pointerup', endDrag);
  handle.addEventListener('pointercancel', endDrag);
})();


(() => {
  const overlay = document.querySelector('[data-mobile-menu-overlay]');
  const openButtons = Array.from(document.querySelectorAll('[data-mobile-menu-open]'));
  if (!overlay || openButtons.length === 0) {
    return;
  }

  const closeButton = overlay.querySelector('[data-mobile-menu-close]');
  let returnFocusTarget = openButtons[0];

  function getFocusableElements() {
    return Array.from(overlay.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'))
      .filter((element) => !element.hidden && element.getAttribute('aria-hidden') !== 'true');
  }

  function setExpanded(isExpanded) {
    openButtons.forEach((button) => button.setAttribute('aria-expanded', String(isExpanded)));
  }

  function openMenu(event) {
    returnFocusTarget = event.currentTarget instanceof HTMLElement ? event.currentTarget : openButtons[0];
    overlay.hidden = false;
    document.body.classList.add('mobile-menu-open');
    setExpanded(true);
    window.requestAnimationFrame(() => (closeButton || getFocusableElements()[0])?.focus());
  }

  function closeMenu() {
    overlay.hidden = true;
    document.body.classList.remove('mobile-menu-open');
    setExpanded(false);
    returnFocusTarget?.focus();
  }

  setExpanded(false);
  openButtons.forEach((button) => button.addEventListener('click', openMenu));
  closeButton?.addEventListener('click', closeMenu);
  overlay.addEventListener('click', (event) => {
    if (event.target === overlay) {
      closeMenu();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && !overlay.hidden) {
      closeMenu();
      return;
    }
    if (event.key !== 'Tab' || overlay.hidden) {
      return;
    }
    const focusableElements = getFocusableElements();
    if (focusableElements.length === 0) {
      return;
    }
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    if (event.shiftKey && document.activeElement === firstElement) {
      event.preventDefault();
      lastElement.focus();
    } else if (!event.shiftKey && document.activeElement === lastElement) {
      event.preventDefault();
      firstElement.focus();
    }
  });
})();


(() => {
  const root = document.querySelector('[data-flow-root]');
  if (!root) {
    return;
  }

  const storageKey = 'youth-trend-room-read-until';
  const items = Array.from(root.querySelectorAll('[data-flow-item]'));
  const cells = Array.from(root.querySelectorAll('[data-flow-cell]'));
  const periods = Array.from(root.querySelectorAll('[data-flow-period]'));
  const dateButtons = Array.from(root.querySelectorAll('[data-flow-date]'));
  const status = root.querySelector('[data-flow-status]');
  const markButton = root.querySelector('[data-flow-mark-read]');
  const allButton = root.querySelector('[data-flow-all]');
  function visiblePeriodIndexes() {
    return new Set(
      periods
        .filter((period) => !period.hidden)
        .map((period) => String(period.dataset.flowPeriodIndex || '0'))
    );
  }

  function visibleItems() {
    return items.filter((item) => !item.hidden);
  }

  function readStoredTimestamp() {
    try {
      return Number(window.localStorage.getItem(storageKey) || 0);
    } catch (error) {
      return 0;
    }
  }

  function refreshReadMarker() {
    root.querySelectorAll('[data-flow-read-marker]').forEach((marker) => marker.remove());
    const readUntil = readStoredTimestamp();
    const currentItems = visibleItems();
    const unreadCount = currentItems.filter((item) => Number(item.dataset.publishedTs || 0) > readUntil).length;
    if (status) {
      status.textContent = readUntil
        ? `이전에 읽은 뒤 새로 들어온 자료 ${unreadCount}건`
        : `선택한 날짜 ${visiblePeriodIndexes().size}개 · ${currentItems.length}건`;
    }
    if (!readUntil) {
      return;
    }
    const firstReadItem = currentItems.find((item) => Number(item.dataset.publishedTs || 0) <= readUntil);
    if (!firstReadItem) {
      return;
    }
    const marker = document.createElement('div');
    marker.className = 'flow-read-marker';
    marker.dataset.flowReadMarker = 'true';
    marker.textContent = '여기까지 읽으셨습니다';
    firstReadItem.before(marker);
  }

  function showLoadedPeriods() {
    const loadedIndexes = visiblePeriodIndexes();
    items.forEach((item) => {
      item.hidden = !loadedIndexes.has(String(item.dataset.flowPeriodIndex || '0'));
    });
    cells.forEach((cell) => cell.classList.remove('active'));
    refreshReadMarker();
  }

  function selectPeriods(indexes) {
    const selectedIndexes = new Set(indexes.map(String));
    periods.forEach((period) => {
      period.hidden = !selectedIndexes.has(String(period.dataset.flowPeriodIndex || '0'));
    });
    showLoadedPeriods();
    dateButtons.forEach((button) => {
      button.setAttribute('aria-pressed', String(selectedIndexes.has(String(button.dataset.flowDate || '0'))));
    });
  }

  dateButtons.forEach((button) => {
    button.addEventListener('click', () => {
      selectPeriods([button.dataset.flowDate || '0']);
      if (status) {
        status.textContent = `${button.textContent.replace(/\s+/g, ' ').trim()} 흐름 · ${visibleItems().length}건`;
      }
      root.querySelector('[data-flow-stream]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  cells.forEach((cell) => {
    cell.addEventListener('click', () => {
      const start = Number(cell.dataset.startTs || 0);
      const end = Number(cell.dataset.endTs || 0);
      items.forEach((item) => {
        const timestamp = Number(item.dataset.publishedTs || 0);
        item.hidden = !(timestamp >= start && timestamp < end);
      });
      cells.forEach((other) => other.classList.toggle('active', other === cell));
      root.querySelectorAll('[data-flow-read-marker]').forEach((marker) => marker.remove());
      if (status) {
        status.textContent = `${cell.dataset.label || '선택한 시간'} · ${cell.dataset.count || 0}건`;
      }
      root.querySelector('[data-flow-stream]')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });

  allButton?.addEventListener('click', () => {
    selectPeriods(periods.map((period) => period.dataset.flowPeriodIndex || '0'));
    if (status) {
      status.textContent = `최근 7일에 들어온 자료 · ${items.length}건`;
    }
  });
  markButton?.addEventListener('click', () => {
    const latestTimestamp = Math.max(0, ...visibleItems().map((item) => Number(item.dataset.publishedTs || 0)));
    try {
      window.localStorage.setItem(storageKey, String(latestTimestamp));
    } catch (error) {
      // Storage can be blocked; the current view still remains usable.
    }
    refreshReadMarker();
    markButton.textContent = '읽은 위치 저장됨';
  });

  selectPeriods(['0']);
})();


(() => {
  const root = document.querySelector('[data-home-activity]');
  if (!root) return;
  const endpoint = root.dataset.activityUrl || 'home_activity_calendar.json';
  const archiveRoot = document.querySelector('[data-home-activity-archive]');
  const calendar = archiveRoot?.querySelector('[data-home-activity-calendar]');
  const dateRecords = archiveRoot?.querySelector('[data-home-activity-date-records]');
  const dateList = archiveRoot?.querySelector('[data-home-activity-date-list]');
  const dateTitle = archiveRoot?.querySelector('[data-home-activity-date-list-title]');
  const dateStatus = archiveRoot?.querySelector('[data-home-activity-date-status]');
  const previous = archiveRoot?.querySelector('[data-home-activity-previous]');
  const next = archiveRoot?.querySelector('[data-home-activity-next]');
  const monthLabel = archiveRoot?.querySelector('[data-home-activity-month]');
  const seoulFormatter = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' });
  const dayFormatter = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: 'long', day: 'numeric', weekday: 'short' });
  const hourFormatter = new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hour12: false });
  let payload = null;
  let selectedDate = '';
  let visibleMonth = null;

  function escapeText(value) { return String(value || ''); }
  function create(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function dateFromKey(key) { const [year, month, day] = key.split('-').map(Number); return new Date(year, month - 1, day); }
  function dateKeyFromDate(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; }
  function monthKey(date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`; }
  function entriesFor(date) { return (payload?.items || []).filter((item) => item.date === date); }
  function summaryFor(date) { return payload?.days?.[date] || { count: 0, kinds: {} }; }
  function formatKinds(kinds) {
    return Object.entries(kinds || {}).slice(0, 2).map(([kind, count]) => `${kind} ${count}`).join(' · ');
  }
  const menuLinks = {
    news: ['뉴스', 'news.html'], opinion: ['기고·칼럼', 'opinion.html'], research: ['논문·연구', 'reports.html'],
    official: ['정부부처', 'official.html'], local: ['지자체', 'local.html'], 'local-plan': ['지자체 계획', 'local.html'],
    stats: ['정부조사·통계', 'tools.html'], hub: ['현장 목소리', 'hub.html']
  };
  function renderMenuCounts() {
    const target = archiveRoot?.querySelector('[data-home-activity-menu-counts]');
    if (!target || !payload || !visibleMonth) return;
    const counts = {};
    (payload.items || []).filter((item) => String(item.date || '').startsWith(visibleMonth)).forEach((item) => {
      const key = item.kind_key || 'news'; counts[key] = (counts[key] || 0) + 1;
    });
    target.replaceChildren();
    Object.entries(menuLinks).forEach(([key, [label, href]]) => {
      const link = create('a', `home-activity-menu-count home-activity-menu-count--${key}`, `${label} ${counts[key] || 0}건`);
      link.href = href; target.append(link);
    });
  }

  function renderItems(list, title, status, date) {
    if (!list || !payload) return;
    let items = entriesFor(date);
    list.replaceChildren();
    const dateLabel = dayFormatter.format(dateFromKey(date));
    if (title) title.textContent = `${dateLabel} 자료`;
    if (status) status.textContent = `${items.length}건`;
    if (!items.length) {
      list.append(create('p', 'home-activity-empty', '표시할 자료가 없습니다.'));
      return;
    }
    items.forEach((item) => {
      const article = create('article', 'home-activity-item');
      const meta = create('div', 'home-activity-item-meta');
      meta.append(create('span', `home-activity-kind home-activity-kind--${item.kind_key || 'news'}`, escapeText(item.kind)));
      meta.append(create('span', 'home-activity-source', escapeText(item.source)));
      if (item.has_time && item.timestamp) meta.append(create('time', 'home-activity-time', hourFormatter.format(new Date(item.timestamp))));
      else meta.append(create('span', 'home-activity-date-only', '발행 시각 미확인'));
      const link = create('a', 'home-activity-item-title', escapeText(item.title));
      link.href = item.url || 'news.html';
      if (item.url) { link.target = '_blank'; link.rel = 'noreferrer'; }
      article.append(meta, link);
      if (Array.isArray(item.topics) && item.topics.length) article.append(create('p', 'home-activity-topics', item.topics.map((topic) => `#${topic}`).join(' ')));
      list.append(article);
    });
  }

  function renderDateList(date) {
    selectedDate = date;
    renderItems(dateList, dateTitle, dateStatus, date);
  }

  function renderDatePrompt() {
    if (dateTitle) dateTitle.textContent = '날짜별 자료';
    if (dateStatus) dateStatus.textContent = '';
    if (dateList) dateList.replaceChildren();
  }

  function renderCalendar() {
    if (!calendar || !payload || !visibleMonth) return;
    calendar.replaceChildren();
    const [year, month] = visibleMonth.split('-').map(Number);
    const first = new Date(year, month - 1, 1);
    const last = new Date(year, month, 0);
    if (monthLabel) monthLabel.textContent = `${year}년 ${month}월`;
    ['일', '월', '화', '수', '목', '금', '토'].forEach((weekday) => calendar.append(create('span', 'home-activity-weekday', weekday)));
    for (let blank = 0; blank < first.getDay(); blank += 1) calendar.append(create('span', 'home-activity-day blank'));
    for (let day = 1; day <= last.getDate(); day += 1) {
      const date = dateKeyFromDate(new Date(year, month - 1, day));
      const summary = summaryFor(date);
      const isToday = date === payload.today;
      const button = create('button', `home-activity-day${summary.count ? ' has-items' : ''}${isToday ? ' today' : ''}`, String(day));
      button.type = 'button';
      button.disabled = !summary.count;
      button.setAttribute('aria-pressed', String(selectedDate === date));
      button.setAttribute('aria-label', `${date} ${summary.count}건${summary.count ? `, ${formatKinds(summary.kinds)}` : ''}`);
      if (summary.count) {
        button.append(create('small', 'home-activity-day-count', `${summary.count}건`));
        const kinds = formatKinds(summary.kinds);
        if (kinds) button.append(create('small', 'home-activity-day-kinds', kinds));
        button.addEventListener('click', () => {
          renderDateList(date);
          renderCalendar();
          dateRecords?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
      }
      calendar.append(button);
    }
    const current = new Date(year, month - 1, 1);
    const earliest = payload.months?.[payload.months.length - 1] || monthKey(current);
    const latest = payload.months?.[0] || monthKey(current);
    if (previous) previous.disabled = monthKey(current) <= earliest;
    if (next) next.disabled = monthKey(current) >= latest;
    renderMenuCounts();
  }

  previous?.addEventListener('click', () => { const [year, month] = visibleMonth.split('-').map(Number); visibleMonth = monthKey(new Date(year, month - 2, 1)); renderCalendar(); });
  next?.addEventListener('click', () => { const [year, month] = visibleMonth.split('-').map(Number); visibleMonth = monthKey(new Date(year, month, 1)); renderCalendar(); });

  fetch(endpoint, { cache: 'no-cache' })
    .then((response) => response.ok ? response.json() : Promise.reject(new Error(`activity_calendar_${response.status}`)))
    .then((data) => {
      payload = data;
      const initialDate = payload.today || `${payload.months?.[0] || '2026-01'}-01`;
      visibleMonth = monthKey(dateFromKey(initialDate));
      renderCalendar();
      renderDatePrompt();
    })
    .catch(() => {
      if (dateStatus) dateStatus.textContent = '날짜별 기록을 불러오지 못했습니다.';
    });
})();


(() => {
  const endpoint = "";
  const scope = "public";
  function getStoredId(storage, key) {
    try {
      let value = storage.getItem(key);
      if (!value) {
        value = (window.crypto && window.crypto.randomUUID) ? window.crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
        storage.setItem(key, value);
      }
      return value;
    } catch (error) {
      return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }
  }
  if (!endpoint) {
    return;
  }
  const sessionId = getStoredId(window.sessionStorage, "ytSessionId");
  const payload = JSON.stringify({
    event_name: "page_view",
    site_scope: scope,
    session_id: sessionId,
    page_path: window.location.pathname,
    page_url: window.location.href,
    page_title: document.title,
    referrer: document.referrer || "",
    source_origin: window.location.origin || ""
  });
  try {
    if (navigator.sendBeacon) {
      navigator.sendBeacon(endpoint, payload);
    } else {
      fetch(endpoint, {
        method: "POST",
        mode: "no-cors",
        keepalive: true,
        headers: { "Content-Type": "text/plain;charset=UTF-8" },
        body: payload
      });
    }
  } catch (error) {
    console.debug("analytics_beacon_failed", error);
  }
})();


(() => {
  const eventKey = 'youthTogetherProductEvents-v1';
  const profileKey = 'youthTogetherInterestProfile-v1';
  const articleViewKey = 'youthTogetherArticleViews-v1';
  const softGateDismissedKey = 'youthTogetherSoftGateDismissed-v1';
  const endpoint = document.body.dataset.analyticsEndpoint || '';
  const subscriptionEndpoint = document.body.dataset.subscriptionEndpoint || '';
  let productSessionId = '';
  try {
    productSessionId = sessionStorage.getItem('ytSessionId') || `${Date.now()}-${Math.random().toString(16).slice(2)}`;
    sessionStorage.setItem('ytSessionId', productSessionId);
  } catch (error) { productSessionId = `${Date.now()}-${Math.random().toString(16).slice(2)}`; }
  function record(name, detail) {
    const item = { name, detail: detail || {}, path: location.pathname, at: new Date().toISOString() };
    try {
      const events = JSON.parse(localStorage.getItem(eventKey) || '[]');
      events.unshift(item);
      localStorage.setItem(eventKey, JSON.stringify(events.slice(0, 50)));
    } catch (error) { /* local auditing is best effort */ }
    if (endpoint) {
      try { navigator.sendBeacon(endpoint, JSON.stringify({ event_name: name, session_id: productSessionId, page_path: location.pathname, page_url: location.href, detail: item.detail })); } catch (error) { /* no-op */ }
    }
    window.dispatchEvent(new CustomEvent('yt-product-event', { detail: item }));
  }
  document.addEventListener('click', (event) => {
    const target = event.target.closest('[data-event]');
    if (target) record(target.dataset.event, { label: (target.textContent || '').trim().slice(0, 80), href: target.getAttribute('href') || '' });
  });

  function currentProfile() {
    try { return JSON.parse(localStorage.getItem(profileKey) || 'null') || {}; } catch (error) { return {}; }
  }

  function shareFeedback(button, message, isError) {
    const feedback = button.closest('.article-share-actions')?.querySelector('[data-share-feedback]');
    if (!feedback) return;
    feedback.textContent = message;
    feedback.style.color = isError ? '#b42318' : '';
  }

  function buildSharePayload(button) {
    const title = button.dataset.shareTitle || document.title;
    const meta = button.dataset.shareMeta || '';
    const summary = button.dataset.shareSummary || '';
    const path = button.dataset.sharePath || location.href;
    const url = new URL(path, location.href).href;
    const lines = [title, meta, summary, '적재적소 프리핑에서 원문과 관련 자료를 확인해 보세요.', url].filter(Boolean);
    return { title, text: lines.join('\n\n'), url };
  }

  document.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-article-share]');
    if (!button) return;
    event.preventDefault();
    const payload = buildSharePayload(button);
    try {
      if (typeof navigator.share === 'function') {
        await navigator.share(payload);
        shareFeedback(button, '공유할 앱을 선택했습니다.', false);
        record('article_shared_native', { path: button.dataset.sharePath || '', title: payload.title.slice(0, 80) });
        return;
      }
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(payload.text);
      } else {
        const area = document.createElement('textarea');
        area.value = payload.text;
        area.setAttribute('readonly', '');
        area.style.position = 'fixed';
        area.style.left = '-9999px';
        document.body.appendChild(area);
        area.select();
        const copied = document.execCommand('copy');
        document.body.removeChild(area);
        if (!copied) throw new Error('copy_failed');
      }
      shareFeedback(button, '보낼 문구와 링크를 복사했습니다. 카카오톡 대화창에 붙여넣으세요.', false);
      record('article_share_copied', { path: button.dataset.sharePath || '', title: payload.title.slice(0, 80) });
    } catch (error) {
      if (error && error.name === 'AbortError') return;
      shareFeedback(button, '공유 창을 열지 못했습니다. 링크를 길게 눌러 복사해 보세요.', true);
      record('article_share_failed', { path: button.dataset.sharePath || '' });
    }
  });

  document.querySelectorAll('[data-briefing-form]').forEach((form) => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const feedback = form.querySelector('[data-briefing-feedback]');
      const button = form.querySelector('button[type="submit"]');
      const email = (form.elements.email?.value || '').trim();
      const consent = Boolean(form.elements.consent?.checked);
      if (!email || !consent) {
        feedback.textContent = !email ? '이메일 주소를 입력해 주세요.' : '주간 브리핑 수신 항목에 체크해 주세요.';
        return;
      }
      if (!subscriptionEndpoint) {
        feedback.textContent = '이 화면에서는 이메일을 보낼 주소가 연결되지 않았습니다.';
        return;
      }
      const profile = currentProfile();
      button.disabled = true;
      button.textContent = '확인 링크 보내는 중';
      feedback.textContent = '';
      record('briefing_subscription_started', { source_screen: form.dataset.sourceScreen || 'unknown' });
      try {
        const response = await fetch(subscriptionEndpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email,
            consent,
            role: profile.role || '',
            region: profile.region === 'all' ? '' : (profile.region || ''),
            topics: profile.topics || [],
            source_screen: form.dataset.sourceScreen || 'unknown',
          }),
        });
        const result = await response.json().catch(() => ({}));
        feedback.textContent = result.message || (response.ok ? '입력한 이메일의 받은편지함을 확인해 주세요.' : '확인 링크를 보내지 못했습니다.');
        if (response.ok) {
          form.reset();
          record('briefing_subscription_submitted', { source_screen: form.dataset.sourceScreen || 'unknown', status: result.status || 'pending' });
        }
      } catch (error) {
        feedback.textContent = '인터넷 연결을 확인한 뒤 [확인 링크 받기]를 다시 눌러주세요.';
      } finally {
        button.disabled = false;
        button.textContent = '확인 링크 받기';
      }
    });
  });

  const softGate = document.querySelector('[data-soft-gate]');
  if (softGate && document.body.dataset.contentKind === 'briefing') {
    let views = [];
    try { views = JSON.parse(localStorage.getItem(articleViewKey) || '[]'); } catch (error) { views = []; }
    if (!views.includes(location.pathname)) views.push(location.pathname);
    try { localStorage.setItem(articleViewKey, JSON.stringify(views.slice(-20))); } catch (error) { /* best effort */ }
    let dismissedAt = 0;
    try { dismissedAt = Number(localStorage.getItem(softGateDismissedKey) || 0); } catch (error) { dismissedAt = 0; }
    if (views.length >= 4 && Date.now() - dismissedAt > 24 * 60 * 60 * 1000) {
      softGate.hidden = false;
      record('soft_gate_shown', { unique_article_views: views.length });
    }
    softGate.querySelector('[data-soft-gate-close]')?.addEventListener('click', () => {
      softGate.hidden = true;
      try { localStorage.setItem(softGateDismissedKey, String(Date.now())); } catch (error) { /* best effort */ }
      record('soft_gate_dismissed', { unique_article_views: views.length });
    });
  }

  const verified = new URLSearchParams(location.search).get('subscription') === 'verified';
  if (verified) {
    const feedback = document.querySelector('#weekly-briefing [data-briefing-feedback]');
    if (feedback) feedback.textContent = '주간 브리핑 수신을 시작했습니다. 다음 발송부터 입력한 이메일로 보냅니다.';
    record('briefing_email_verified', {});
  }

  const root = document.querySelector('[data-interest-builder]');
  if (root) {
    const role = root.querySelector('[data-interest-role]');
    const region = root.querySelector('[data-interest-region]');
    const topics = Array.from(root.querySelectorAll('[data-interest-topic]'));
    const previews = Array.from(root.querySelectorAll('.preview-panel [data-preview-card]'));
    const feedback = root.querySelector('[data-interest-feedback]');
    const resultLink = root.querySelector('[data-interest-result-link]');
    function profile() { return { role: role.value, region: region.value, topics: topics.filter((input) => input.checked).map((input) => input.value) }; }
    function update() {
      const value = profile();
      topics.forEach((input) => { input.disabled = !input.checked && value.topics.length >= 3; });
      let visible = 0;
      previews.forEach((card) => {
        const regionMatch = value.region === 'all' || card.dataset.region === value.region || card.dataset.region === '전국';
        const cardTopics = (card.dataset.topics || '').split('|');
        const topicMatch = !value.topics.length || value.topics.some((topic) => cardTopics.includes(topic));
        const show = regionMatch && topicMatch && visible < 3;
        card.hidden = !show;
        if (show) visible += 1;
      });
      const params = new URLSearchParams();
      if (value.region !== 'all') params.set('region', value.region);
      if (value.topics[0]) params.set('topic', value.topics[0]);
      resultLink.href = `news.html${params.toString() ? `?${params}` : ''}`;
      const empty = document.querySelector('[data-preview-empty]');
      if (empty) empty.hidden = visible > 0;
    }
    root.addEventListener('change', update);
    root.addEventListener('submit', (event) => {
      event.preventDefault();
      const value = profile();
      try {
        localStorage.setItem(profileKey, JSON.stringify(value));
        feedback.textContent = '이 기기에 관심 설정을 저장했습니다. 주간 브리핑 신청란에는 선택한 지역과 의제만 함께 전달됩니다.';
        record('radar_profile_saved_local', { role: value.role, region: value.region, topic_count: value.topics.length });
      } catch (error) {
        feedback.textContent = '브라우저 저장소를 사용할 수 없어 설정을 저장하지 못했습니다.';
      }
    });
    try {
      const saved = JSON.parse(localStorage.getItem(profileKey) || 'null');
      if (saved) {
        role.value = saved.role || role.value;
        region.value = saved.region || region.value;
        topics.forEach((input) => { input.checked = (saved.topics || []).includes(input.value); });
      }
    } catch (error) { /* ignore malformed local data */ }
    update();
  }

  const eventList = document.querySelector('[data-operator-event-list]');
  if (eventList) {
    function renderEvents() {
      let events = [];
      try { events = JSON.parse(localStorage.getItem(eventKey) || '[]'); } catch (error) { events = []; }
      eventList.innerHTML = events.length ? events.slice(0, 10).map((item) => `<div class="operator-event"><strong>${item.name}</strong><br><span>${new Date(item.at).toLocaleString('ko-KR')} · ${item.path}</span></div>`).join('') : '<p>이 기기에서 기록된 제품 이벤트가 없습니다.</p>';
    }
    renderEvents();
    window.addEventListener('yt-product-event', renderEvents);
  }
})();
