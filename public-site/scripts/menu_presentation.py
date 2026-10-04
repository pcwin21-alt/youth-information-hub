"""Shared presentation for public archive menus; filtering stays with existing controllers."""
import html

MENU_PAGES = {"news.html", "trends.html", "opinion.html", "official.html", "local.html", "reports.html", "tools.html", "hub.html"}


def render_archive_controls(regions, topics, dates, total_count, *, include_hours=False):
    def choices(group, values):
        return ''.join(
            f'<button class="filter-button{" active" if value == "all" else ""}" type="button" data-news-filter="true" data-filter-group="{group}" data-filter-value="{html.escape(value, quote=True)}" aria-pressed="{"true" if value == "all" else "false"}">{html.escape(label)}</button>'
            for value, label in [("all", "전체"), *((v, v) for v in values if v != "all")]
        )
    hour_options = '<option value="all">전체</option>' + ''.join(f'<option value="{hour:02d}:00">{hour:02d}:00</option>' for hour in range(24))
    hours = f'<div class="menu-date-range"><label>시작 시간<select aria-label="시작 시간" data-menu-hour="selectedHourStart">{hour_options}</select></label><label>종료 시간<select aria-label="종료 시간" data-menu-hour="selectedHourEnd">{hour_options}</select></label></div>' if include_hours else ''
    return f'''<section class="section menu-controls" id="filters" aria-label="자료 검색과 필터">
      <div class="menu-search"><label>키워드 검색<input type="search" data-news-search-input="true" placeholder="제목·요약·출처 검색"></label><button type="button" data-menu-reset>필터 초기화</button></div>
      <details class="menu-advanced"><summary>지역·주제·기간</summary>
        <div class="menu-filter-group"><span>지역</span><div>{choices('region', regions)}</div></div>
        <div class="menu-filter-group"><span>주제</span><div>{choices('topic', topics)}</div></div>
        <div class="menu-date-range"><label>시작일<input type="date" data-news-date-input="true" data-date-role="start"></label><label>종료일<input type="date" data-news-date-input="true" data-date-role="end"></label><button class="filter-button active" type="button" data-news-filter="true" data-filter-group="date" data-filter-value="all" aria-pressed="true">전체 기간</button></div>
      {hours}</details><p class="filter-status" data-news-filter-status role="status">전체 {total_count}건을 보고 있습니다.</p>
    </section>'''


def render_policy_controls(groups_html, date_attrs, total_count):
    return f'''<section class="section menu-controls" id="filters" aria-label="자료 검색과 필터">
      <div class="menu-search"><label>키워드 검색<input type="search" data-policy-search-input="true" placeholder="제목·요약·출처 검색"></label><button type="button" data-menu-policy-reset>필터 초기화</button></div>
      <details class="menu-advanced"><summary>구분·유형·기간</summary>{groups_html}
      <div class="menu-date-range"><label>시작일<input type="date" data-policy-date-input="true" data-date-role="start" {date_attrs}></label><label>종료일<input type="date" data-policy-date-input="true" data-date-role="end" {date_attrs}></label><button class="filter-button active" type="button" data-policy-filter="true" data-filter-group="date" data-filter-value="all" aria-pressed="true">전체 기간</button></div>
      </details><p class="filter-status" data-policy-filter-status role="status">전체 {total_count}건을 보고 있습니다.</p>
    </section>'''


MENU_CSS = """
/* One scoped contract overrides legacy menu-specific card layouts. */
#main-content .menu-layout{--menu-gap:24px;font-size:16px;line-height:1.6}
#main-content .menu-layout .page-intro-card{min-height:160px;padding:24px 28px;margin-top:28px;border-radius:12px;box-shadow:none}
#main-content .menu-layout .page-intro-title{font-size:30px;font-weight:700;line-height:1.4}
#main-content .menu-layout .page-intro-media{max-height:140px}
#main-content .menu-layout .page-intro-copy{display:block;font-size:16px;line-height:1.6;margin:8px 0 0;max-width:850px}
#main-content .menu-layout .section{margin-top:24px;margin-bottom:24px}
#main-content .menu-layout .section .section{width:100%;margin-left:0;margin-right:0}
#main-content .menu-layout .section-head h2,#main-content .menu-layout .trend-section-title{font-size:22px;font-weight:700;line-height:1.5}
#main-content .menu-layout .article-grid,#main-content .menu-layout .trend-items{display:grid;grid-template-columns:minmax(0,1fr)!important;gap:0;align-items:start}
#main-content .menu-layout .article-grid>.article-card{display:grid!important;grid-template-columns:minmax(0,1fr) 144px;grid-template-rows:auto;grid-template-areas:"meta media" "title media" "summary media" "tags media" "related related" "actions actions" "feedback feedback";grid-column:1/-1!important;grid-row:auto!important;gap:6px 24px;min-height:0!important;padding:24px 0!important;border:0;border-top:1px solid var(--line);border-radius:0;background:transparent;box-shadow:none;transform:none;overflow:visible}
#main-content .menu-layout .article-grid>.article-card.no-media{grid-template-columns:minmax(0,1fr)}
#main-content .menu-layout .article-card::after{display:none}
#main-content .menu-layout .article-card>:not(.article-media){margin:0;padding:0}
#main-content .menu-layout .article-card .article-media{grid-area:media;position:static;width:144px;height:100px;min-height:0;margin:0;border:0;border-radius:8px;align-self:start}
#main-content .menu-layout .article-card .article-thumbnail{width:100%;height:100%;object-fit:cover}
#main-content .menu-layout .article-card h3{grid-area:title;display:block;overflow:visible;font-size:19px;font-weight:700;line-height:1.5;letter-spacing:normal;-webkit-line-clamp:unset;overflow-wrap:anywhere}
#main-content .menu-layout .article-card .article-summary{grid-area:summary;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden;font-size:16px;font-weight:400;line-height:1.6;color:var(--muted)}
#main-content .menu-layout .article-card .article-meta{grid-area:meta;display:block;margin:0}
#main-content .menu-layout .article-card .article-meta-tags,#main-content .menu-layout .article-list-time{display:none}
#main-content .menu-layout .article-card .article-byline{display:flex;flex-wrap:wrap;gap:6px;font-size:14px;font-weight:400;line-height:1.5;color:var(--muted)}
#main-content .menu-layout .article-card .badge-row{grid-area:tags;display:flex;flex-wrap:wrap;gap:6px;padding:0;margin:2px 0}
#main-content .menu-layout .article-card .badge{font-size:14px;font-weight:400;line-height:1.5;padding:3px 8px}
#main-content .menu-layout .article-card .article-actions{grid-area:actions;display:flex;flex-wrap:wrap;justify-self:start;gap:8px;border:0;padding:0;margin:6px 0 0}
#main-content .menu-layout .article-actions .action-button,#main-content .menu-layout .article-link-action{font-size:14px;font-weight:700;line-height:1.5;min-height:44px;padding:10px 12px;box-sizing:border-box}
#main-content .menu-layout .article-related{grid-area:related;font-size:16px;line-height:1.6}
#main-content .menu-layout .article-feedback{grid-area:feedback;font-size:14px;min-height:0}
#main-content .menu-layout .article-feedback:empty{display:none}
#main-content .menu-layout [hidden]{display:none!important}
#main-content .menu-layout .menu-controls,#main-content .menu-layout .filter-panel,#main-content .menu-layout .trend-controls{box-sizing:border-box;background:#f4f8f6;border:1px solid var(--line);border-radius:8px;padding:20px;box-shadow:none}
#main-content .menu-layout .menu-search{display:flex;align-items:end;gap:12px}
#main-content .menu-layout .menu-search label{flex:1}
#main-content .menu-layout .menu-search label,#main-content .menu-layout .menu-date-range label{display:grid;gap:6px;font-size:14px;font-weight:700}
#main-content .menu-layout input,#main-content .menu-layout select,#main-content .menu-layout .menu-search button,#main-content .menu-layout .trend-controls button{font:inherit;min-height:44px;box-sizing:border-box;padding:10px 12px;border:1px solid #aab7b3;border-radius:6px;background:white;min-width:0;max-width:100%}
#main-content .menu-layout .menu-search input{width:100%}
#main-content .menu-layout .menu-advanced{margin-top:16px;font-size:16px}
#main-content .menu-layout summary{cursor:pointer;min-height:32px}
#main-content .menu-layout .menu-filter-group{display:grid;grid-template-columns:64px minmax(0,1fr);gap:12px;margin:16px 0}
#main-content .menu-layout .menu-filter-group>div,#main-content .menu-layout .menu-date-range{display:flex;flex-wrap:wrap;gap:8px;align-items:end}
#main-content .menu-layout .filter-button{font-size:14px;font-weight:700;min-height:44px}
#main-content .menu-layout .filter-status{font-size:14px;line-height:1.5;margin:14px 0 0}
#main-content .menu-layout :focus-visible{outline:3px solid var(--accent-strong);outline-offset:3px}
#main-content .menu-layout .trend-digest{margin-top:24px;padding:0;border:0}
#main-content .menu-layout .trend-item{padding:24px 0}
#main-content .menu-layout .trend-item h3{font-size:19px;line-height:1.5}
#main-content .menu-layout .tools-survey-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;gap:24px}
#main-content .menu-layout .resource-card{box-shadow:none;border:1px solid var(--line);border-radius:8px;padding:24px;background:white;color:var(--deep-navy)}
#main-content .menu-layout .resource-card h3{font-size:19px;font-weight:700;line-height:1.5}
#main-content .menu-layout .resource-card p{display:block;font-size:16px;line-height:1.6}
@media(max-width:900px){body .editorial-menu-trigger{display:none!important}}
@media(max-width:800px){
 #main-content .menu-layout .page-intro-card{padding:20px;margin-top:20px;min-height:0}
 #main-content .menu-layout .page-intro-title{font-size:24px}
 #main-content .menu-layout .page-intro-media{display:none}
 #main-content .menu-layout .article-grid>.article-card{grid-template-columns:minmax(0,1fr) 80px;gap:6px 12px;padding:20px 0!important}
 #main-content .menu-layout .article-card .article-media{width:80px;height:72px}
 #main-content .menu-layout .article-card h3{font-size:18px}
 #main-content .menu-layout .article-card .article-summary{grid-column:1/-1}
 #main-content .menu-layout .menu-search{align-items:stretch;flex-direction:column}
 #main-content .menu-layout .menu-controls,#main-content .menu-layout .filter-panel{padding:16px}
 #main-content .menu-layout .tools-survey-grid{grid-template-columns:minmax(0,1fr)!important}
}
"""

MENU_JS = """
document.querySelectorAll('[data-menu-reset]').forEach(button=>button.addEventListener('click',()=>{
 const root=button.closest('[data-news-filter-root]');
 root.querySelectorAll('[data-menu-hour]').forEach(control=>{control.value='all';root.dataset[control.dataset.menuHour]='all';});
 root.querySelectorAll('[data-news-filter][data-filter-value="all"]').forEach(control=>control.click());
 const input=root.querySelector('[data-news-search-input]');input.value='';input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();
}));
document.querySelectorAll('[data-menu-hour]').forEach(control=>control.addEventListener('change',()=>{
 const root=control.closest('[data-news-filter-root]');root.dataset[control.dataset.menuHour]=control.value;
 root.querySelector('[data-news-search-input]').dispatchEvent(new Event('input',{bubbles:true}));
}));
document.querySelectorAll('[data-menu-policy-reset]').forEach(button=>button.addEventListener('click',()=>{
 const root=button.closest('[data-policy-filter-root]');
 root.querySelectorAll('[data-policy-filter][data-filter-value="all"]').forEach(control=>control.click());
 const input=root.querySelector('[data-policy-search-input]');input.value='';input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();
}));
document.querySelectorAll('[data-resource-search]').forEach(input=>{
 const root=input.closest('.menu-layout'),cards=[...root.querySelectorAll('.resource-card')],status=root.querySelector('[data-resource-status]');
 function apply(){let count=0;const query=input.value.trim().toLocaleLowerCase();cards.forEach(card=>{card.hidden=!card.textContent.toLocaleLowerCase().includes(query);if(!card.hidden)count++;});status.textContent=count?count+'건을 보고 있습니다.':'조건에 맞는 자료가 없습니다. 키워드를 바꾸거나 초기화하세요.';}
 input.addEventListener('input',apply);root.querySelector('[data-resource-reset]').addEventListener('click',()=>{input.value='';apply();input.focus();});apply();
});
"""
