"""Evidence-bounded recent youth-policy discovery, without API calls."""
from datetime import datetime, timedelta, timezone
import hashlib
import html
import re
from urllib.parse import urlsplit

KST = timezone(timedelta(hours=9))
TOPICS = {
    "주거": r"주거|주택|월세|전세|임대|보증금",
    "일자리": r"취업|일자리|고용|창업|근속|구직|인턴|노동",
    "금융·생활": r"적금|금융|대출|자산|생활비|교통비",
    "참여·지역": r"참여|위원|협의|네트워크|정책단|자문|거버넌스",
    "교육·건강": r"교육|대학|장학|건강|마음|상담|고립|은둔",
}


def parse_date(value):
    try:
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return (date.replace(tzinfo=KST) if date.tzinfo is None else date).astimezone(KST)
    except (ValueError, TypeError):
        return None


def clean_title(article):
    title = re.sub(r"\s+", " ", str(article.get("title") or "")).strip()
    # Remove only an exact declared publisher suffix, never arbitrary hyphens.
    for publisher in (article.get("source"), article.get("publisher_name")):
        if publisher:
            title = re.sub(r"\s*[-–|]\s*" + re.escape(str(publisher)) + r"$", "", title).strip()
    title = re.sub(r"\s*[-–|]\s*(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/\S*)?$", "", title, flags=re.I).strip()
    title = re.sub(r"\s*-\s*카드/한컷\s*\|\s*멀티미디어$", "", title).strip()
    return title


def build_digest(articles, updated_at, now=None):
    reference = now or datetime.now(KST)
    updated = parse_date(updated_at)
    groups, urls = {}, set()
    for article in articles:
        title = clean_title(article)
        if len(title) > 180 or title.startswith("이미지 없음"):
            continue
        if not re.search(r"청년|대학생|사회초년|청소년|2030세대|20대|30대", title):
            continue
        if any(article.get(key) for key in ("is_publicly_excluded", "is_noise", "weak_youth_signal", "missing_youth_content_signal")):
            continue
        date = parse_date(article.get("published_date") or article.get("published_at"))
        if not date or not reference - timedelta(days=7) <= date <= reference:
            continue
        url = str(article.get("canonical_url") or article.get("url") or "")
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or url in urls:
            continue
        urls.add(url)
        key = re.sub(r"\W", "", title).casefold() + "|" + str(article.get("region") or "")
        topic = next((name for name, pattern in TOPICS.items() if re.search(pattern, title)), "기타 청년정책")
        item = dict(article, title=title, digest_url=url, digest_date=date)
        group = groups.setdefault(key, {"id": "issue-" + hashlib.sha256(key.encode()).hexdigest()[:12], "topic": topic, "records": []})
        group["records"].append(item)
    issues = sorted(groups.values(), key=lambda group: max(row["digest_date"] for row in group["records"]), reverse=True)
    for issue in issues:
        issue["records"].sort(key=lambda row: row["digest_date"], reverse=True)
    return {"issues": issues, "updated": updated, "reference": reference, "stale": not updated or reference - updated > timedelta(hours=24)}


def render_home_digest(digest, illustration):
    """Keep the existing illustrated editorial hero and pale-green recent rail."""
    esc = html.escape
    updated = digest["updated"]
    freshness = f"마지막 수집 {updated:%Y.%m.%d %H:%M} KST" if updated else "수집 시각 미확인"
    if digest["stale"]:
        freshness += " · 수집 상태 확인 필요"
    rows = "".join(
        f'<li><a href="trends.html#{issue["id"]}"><div><small>{esc(issue["topic"])} · {issue["records"][0]["digest_date"]:%m.%d}</small><strong>{esc(issue["records"][0]["title"])}</strong></div><span aria-hidden="true">→</span></a></li>'
        for issue in digest["issues"][:5]
    ) or '<li class="civic-ai-brief-empty">최근 7일 자료가 없습니다. 전체 자료실에서 지난 소식을 확인하세요.</li>'
    return f'''<section class="civic-ai-brief-home trend-home" id="main-list" aria-label="최근 청년정책 동향">
      <a class="civic-ai-brief-banner" href="trends.html"><img src="{esc(illustration['src'], quote=True)}" alt="{esc(illustration['alt'], quote=True)}"><div class="trend-hero-copy"><small>적재적소 브리프</small><h1>최근 7일,<br>청년정책 소식</h1><em>전체 동향 살펴보기 →</em><time>{esc(freshness)}</time></div></a>
      <aside class="civic-ai-brief-recent"><div><h2>최근 동향</h2><a href="trends.html">전체 보기 →</a></div><ol>{rows}</ol></aside>
    </section>'''


def render_digest(digest, compact=False, illustration=None):
    esc = html.escape
    issues = digest["issues"][:5] if compact else digest["issues"]
    updated = digest["updated"]
    freshness = f"마지막 수집 {updated:%Y.%m.%d %H:%M} KST" if updated else "마지막 수집 시각 미확인"
    if digest["stale"]:
        freshness += " · 최근 수집 상태 확인 필요"
    cards = []
    for issue in issues:
        rows = issue["records"]
        first = rows[0]
        title = esc(first["title"])
        stage = "시행 상태 미확인"
        if first.get("review_status") in ("reviewed", "approved") and first.get("policy_stage") and first.get("stage_evidence_url"):
            stage = str(first["policy_stage"])
        evidence = str(first.get("stage_evidence_url") or "")
        if stage != "시행 상태 미확인" and urlsplit(evidence).scheme in ("http", "https"):
            stage += " · 검토 근거 연결"
        else:
            stage = "시행 상태 미확인"
        source_links = "".join(
            f'<li><a href="{esc(row["digest_url"], quote=True)}" target="_blank" rel="noopener noreferrer">{esc(str(row.get("source") or "출처 미확인"))} 원문 ↗</a> <time>{row["digest_date"]:%m.%d}</time> · {"공식 출처로 분류" if row.get("is_official_source") else "언론·공개 자료"}</li>'
            for row in rows
        )
        if stage != "시행 상태 미확인":
            source_links += f'<li><a href="{esc(evidence, quote=True)}" target="_blank" rel="noopener noreferrer">시행 상태 검토 근거 ↗</a></li>'
        heading = f'<a href="trends.html#{issue["id"]}">{title}</a>' if compact else title
        details = "" if compact else f'<p class="trend-stage">{esc(stage)} · 원문 대조 필요</p><details><summary>원문 {len(rows)}개 확인</summary><ul>{source_links}</ul><p>발표 내용, 적용 대상·지역, 시행일을 원문에서 확인하세요. 같은 제목의 자료를 묶었으며 후속 변화는 검증하지 않았습니다.</p></details>'
        cards.append(f'<article class="trend-item" id="{issue["id"]}" data-trend-topic="{esc(issue["topic"], quote=True)}" data-trend-search="{esc(first["title"] + " " + str(first.get("region") or ""), quote=True)}"><p class="trend-meta">{esc(issue["topic"])} · <time datetime="{first["digest_date"].isoformat()}">{first["digest_date"]:%m.%d}</time></p><h3>{heading}</h3>{details}</article>')
    filters = "" if compact else '<div class="trend-controls"><label>의제 <select data-trend-topic-filter><option value="">전체</option>' + ''.join(f'<option>{esc(topic)}</option>' for topic in (*TOPICS, "기타 청년정책")) + '</select></label><label>지역·키워드 <input type="search" data-trend-search-filter placeholder="예: 광양, 주거, 적금"></label><button type="button" data-trend-reset>필터 초기화</button></div>'
    empty = '<p>최근 7일에 해당하는 청년정책 자료가 없습니다. <a href="news.html">전체 자료 확인</a></p>'
    more = '<button type="button" data-trend-more hidden>더 보기</button>' if not compact else ""
    action = '<a class="product-button" href="trends.html">전체 동향 살펴보기 →</a>' if compact else ""
    hero = f'<section class="policy-brief-hero" aria-labelledby="policy-brief-title"><img src="{esc(illustration["src"], quote=True)}" alt="{esc(illustration["alt"], quote=True)}"><div><p>적재적소 브리프</p><h1 id="policy-brief-title" aria-label="최근 7일, 청년정책 소식">최근 7일,<br>청년정책 소식</h1><span>{esc(freshness)}</span></div></section>' if illustration else ""
    header = '' if hero else f'<header><h1>최근 7일, 청년정책 소식</h1><p class="trend-freshness">{esc(freshness)}</p></header>'
    return hero + f'<section class="trend-digest" id="main-list" data-trend-digest>{header}<h2 class="trend-section-title">관심 의제의 소식 찾기</h2>{filters}<p data-trend-count role="status">{len(issues)}개 제목 묶음 · 같은 제목의 중복 자료 통합</p><h2 class="visually-hidden">최근 동향 자료</h2><div class="trend-items">{"".join(cards) or empty}</div><p data-trend-no-results hidden>조건에 맞는 자료가 없습니다. 필터를 초기화하거나 다른 키워드를 입력하세요.</p>{more}{action}</section>'


DIGEST_CSS = """
.trend-home .trend-hero-copy{position:relative;z-index:2;align-self:end;display:grid;padding:32px;gap:12px;color:#fff;text-shadow:0 2px 12px #0006}
.trend-home .trend-hero-copy small{font-size:16px;font-weight:400}
.trend-home .civic-ai-brief-banner h1{font-size:clamp(26px,3vw,36px);font-weight:700;line-height:1.3;margin:0;color:#fff}
.trend-home .civic-ai-brief-banner em{font-size:16px;line-height:1.5;font-style:normal;font-weight:700}
.trend-home .civic-ai-brief-banner time{font-size:14px;font-weight:400;line-height:1.5;letter-spacing:normal}
.trend-home .civic-ai-brief-recent li{padding:12px 0}.trend-home .civic-ai-brief-recent li a div{min-width:0}.trend-home .civic-ai-brief-recent small{display:block;font-size:14px;color:var(--muted);margin-bottom:5px}
.trend-home .civic-ai-brief-recent strong{display:block;white-space:normal;font-size:16px;line-height:1.5;font-weight:700;color:var(--deep-navy);overflow-wrap:anywhere}
.trend-home .civic-ai-brief-recent{padding:24px}.trend-home .civic-ai-brief-recent strong{display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;overflow:hidden}.trend-home .civic-ai-brief-recent small{line-height:1.5}.trend-home .civic-ai-brief-recent li{padding:8px 0}.trend-home .civic-ai-brief-recent h2{font-size:20px}.trend-home .civic-ai-brief-recent>div a{font-size:14px;font-weight:700}
body[data-page="trends.html"] .policy-brief-hero{min-height:270px}body[data-page="trends.html"] .policy-brief-hero h1{font-size:clamp(26px,3vw,36px);font-weight:700;line-height:1.3}body[data-page="trends.html"] .policy-brief-hero p,body[data-page="trends.html"] .policy-brief-hero span{font-size:14px;font-weight:400;line-height:1.5}
.trend-digest{width:min(1360px,calc(100% - 64px));box-sizing:border-box;margin:32px auto 40px;padding:24px 0;background:transparent;border-top:2px solid var(--deep-navy);color:var(--deep-navy)}
.trend-digest{font-size:16px;line-height:1.6;font-weight:400}.trend-digest h1,.trend-digest h2{font-weight:700;font-size:clamp(24px,4vw,34px);margin:8px 0 12px;line-height:1.3}
.trend-digest header>p{line-height:1.6}.trend-meta{color:#31578c;font-size:14px;margin:0 0 8px}.trend-freshness{color:#536174;font-size:14px}
.trend-items{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0 28px;margin:16px 0 24px}.trend-digest .trend-section-title{font-size:24px}.trend-item a{color:var(--deep-navy)}.trend-meta{color:var(--accent-strong)}.trend-controls{padding:18px;background:#f4f8f6}.trend-archive{width:min(1360px,calc(100% - 64px));margin:auto}
.trend-item{padding:20px 0;border-top:1px solid #dbe2ec;min-width:0;scroll-margin-top:110px}.trend-item h3{font-weight:700;font-size:19px;line-height:1.5;margin:0 0 12px;overflow-wrap:anywhere}.trend-item a{color:#193f78;text-decoration:underline;text-underline-offset:3px}
.trend-item[hidden]{display:none}.trend-stage{font-size:16px;line-height:1.5;color:#536174}.trend-item details{font-size:16px;line-height:1.7}.trend-item summary{cursor:pointer;color:#193f78}.trend-item li{margin:8px 0}.trend-controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:24px 0}.trend-controls label{display:grid;gap:6px}.trend-controls input,.trend-controls select,.trend-controls button{font:inherit;padding:10px;border:1px solid #aab7c9;border-radius:4px;background:white;min-height:44px}.trend-home :focus-visible{outline:3px solid var(--accent-strong);outline-offset:3px}.trend-digest :focus-visible{outline:3px solid var(--accent-strong);outline-offset:3px}.trend-digest [data-trend-more]{font:inherit;min-height:44px;padding:10px 20px;background:white;border:1px solid #aab7c9;cursor:pointer}.trend-archive>summary{cursor:pointer;font-size:20px;padding:20px 0}.trend-archive .policy-brief-grid{margin-top:16px}
@media(max-width:800px){.trend-home .civic-ai-brief-banner{min-height:240px}.trend-home .trend-hero-copy{padding:24px}.trend-home .civic-ai-brief-recent{min-height:0;padding:20px}.trend-home .civic-ai-brief-recent li:nth-child(n+4){display:none}body[data-page="trends.html"] .policy-brief-hero{min-height:210px}.trend-digest,.trend-archive{width:calc(100% - 32px)}}
@media(max-width:640px){.trend-digest{padding:18px 0;margin-top:24px}.trend-items{grid-template-columns:1fr}.trend-controls{display:grid;grid-template-columns:1fr}.trend-controls input{width:100%;box-sizing:border-box}}
.trend-meta{color:var(--accent-strong)}.trend-item a{color:var(--deep-navy)}.trend-item{border-color:var(--line)}
"""

DIGEST_JS = """
document.querySelectorAll('[data-trend-digest]').forEach(root=>{
 const topic=root.querySelector('[data-trend-topic-filter]'),search=root.querySelector('[data-trend-search-filter]');
 if(!topic||!search)return;
 const items=[...root.querySelectorAll('[data-trend-topic]')];
 let limit=30;
 const more=root.querySelector('[data-trend-more]');
 function apply(reset=true){if(reset)limit=30;let count=0,shown=0;const query=search.value.trim().toLocaleLowerCase();items.forEach(item=>{const match=(!topic.value||item.dataset.trendTopic===topic.value)&&(!query||item.dataset.trendSearch.toLocaleLowerCase().includes(query));if(match)count++;item.hidden=!match||shown>=limit;if(!item.hidden)shown++;});root.querySelector('[data-trend-count]').textContent=count+'개 제목 묶음 중 '+shown+'개 표시';root.querySelector('[data-trend-no-results]').hidden=count!==0;more.hidden=count<=shown;}
 topic.addEventListener('change',()=>apply());search.addEventListener('input',()=>apply());root.querySelector('[data-trend-reset]').addEventListener('click',()=>{topic.value='';search.value='';apply();search.focus();});more.addEventListener('click',()=>{limit+=30;apply(false);});
 if(location.hash&&items.some(item=>'#'+item.id===location.hash)){limit=items.length;}apply(false);

});
document.querySelectorAll('.trend-archive').forEach(archive=>{function openAnchor(){if(location.hash&&archive.querySelector('[id="'+CSS.escape(location.hash.slice(1))+'"]'))archive.open=true;}openAnchor();window.addEventListener('hashchange',openAnchor);});
"""
