(function () {
  'use strict';

  var path = window.location.pathname;
  var state = {};
  var discovery = [];
  var discoveryMeta = {page: 1, per_page: 20, total_count: 0, query: ''};
  var compareSelected = {};
  try { compareSelected = JSON.parse(window.sessionStorage.getItem('osswatch_compare') || '{}'); } catch (e) { compareSelected = {}; }
  var scanTimer = null;

  var nav = [
    ['/','Overview','Overview'],
    ['/discover','Discover','Discover'],
    ['/compare','Compare','Compare'],
    ['/watchlist','Watchlist','Watch'],
    ['/alerts','Alerts','Alerts'],
    ['/army','Army Lens','Army lens'],
    ['/system','System','System']
  ];

  var criteria = {
    security_functionality:'Security functionality',
    detection_capability:'Detection capability',
    activity_maintenance:'Activity / maintenance',
    community_adoption:'Community adoption',
    documentation:'Documentation',
    deployment_practicality:'Deployment practicality',
    open_source_health:'Open-source health',
    defence_relevance:'Defence relevance'
  };

  var capabilities = [
    {name:'Cyber Defence', query:'cybersecurity'},
    {name:'Network Security', query:'network security'},
    {name:'Threat Detection', query:'threat detection'},
    {name:'Security Monitoring', query:'security monitoring'},
    {name:'Incident Response', query:'incident response'},
    {name:'Digital Forensics', query:'digital forensics'},
    {name:'Infrastructure Security', query:'infrastructure security'},
    {name:'Data / Intelligence Analysis', query:'security analytics'}
  ];

  function esc(value) {
    var text = value === null || value === undefined ? '' : String(value);
    return text.replace(/[&<>"']/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }

  function fmt(value) { return Number(value || 0).toLocaleString(); }

  function date(value) {
    if (!value) return '—';
    var d = new Date(value);
    if (isNaN(d.getTime())) return '—';
    return d.toLocaleString(undefined, {month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
  }

  function priorityBadge(value) {
    var p = value || 'REVIEW';
    return '<span class="priority p-' + String(p).toLowerCase() + '">' + esc(p) + '</span>';
  }

  function armyLevel(army) { return army && army.level ? army.level : 'LOW'; }

  function armyBadge(army) {
    if (!army) return '<span class="muted">—</span>';
    return '<span class="army-score">' + esc(army.score || '—') + '/5</span>' +
      '<span class="army-level army-' + String(armyLevel(army)).toLowerCase() + '">' + esc(armyLevel(army)) + '</span>';
  }

  function repoUrl(repo) { return '/repository/' + encodeURIComponent(repo.full_name); }

  function githubUrl(repo) {
    if (repo && repo.github_url) return repo.github_url;
    return 'https://github.com/' + (repo ? repo.full_name : '');
  }

  function normalizeRepository(repo) {
    if (!repo) return null;
    repo.score = repo.score || {total:0, percentage:0, priority:'REVIEW', breakdown:{}};
    repo.score.breakdown = repo.score.breakdown || {};
    repo.army_relevance = repo.army_relevance || {};
    repo.stars = repo.stars || 0;
    repo.forks = repo.forks || 0;
    repo.open_issues = repo.open_issues || 0;
    repo.watchlisted = !!repo.watchlisted;
    return repo;
  }

  function fetchJson(url, options) {
    return fetch(url, options).then(function (response) {
      return response.text().then(function (text) {
        var data = {};
        try { data = text ? JSON.parse(text) : {}; } catch (e) { throw new Error('The server returned an unexpected response.'); }
        if (!response.ok) throw new Error(data.error || 'Request failed.');
        return data;
      });
    });
  }

  function shell(crumb, title, body, options) {
    options = options || {};
    var app = document.querySelector('#app');
    if (!app) return;
    var demo = state.mode === 'DEMO';
    var problem = state.error ? '<div class="notice error"><b>Connection notice</b> ' + esc(state.error) + '</div>' : '';
    var links = nav.map(function (item) {
      return '<a class="' + (path === item[0] ? 'selected' : '') + '" href="' + item[0] + '"><span class="nav-dot"></span><span>' + esc(item[1]) + '</span></a>';
    }).join('');
    app.innerHTML =
      '<div class="app">' +
        '<aside class="rail">' +
          '<a class="brand" href="/"><span class="brand-mark">OW</span><span><b>OSS WATCH</b><span>Repository intelligence</span></span></a>' +
          '<div class="nav-section">Workspace</div>' +
          '<nav>' + links + '</nav>' +
          '<div class="rail-note"><b>Screen → verify → monitor</b><span>Evidence-led open-source assessment for technology scouting and continuous review.</span></div>' +
          '<div class="rail-foot">Evidence first · human review<br>Assessment is not certification</div>' +
        '</aside>' +
        '<section class="workspace">' +
          '<header>' +
            '<div><div class="crumb">' + esc(crumb) + '</div><div class="top-title"><h1>' + esc(title) + '</h1></div></div>' +
            '<div class="header-actions">' +
              '<div class="mode ' + (demo ? 'demo' : 'live') + '"><i></i><b>' + (demo ? 'DEMO' : 'LIVE') + '</b><span>' + (demo ? 'Fixture dataset' : 'GitHub API') + '</span></div>' +
              '<div class="scan-time">' + (state.last_scan ? 'Last scan ' + date(state.last_scan) : 'Not scanned') + '</div>' +
              '<button class="button" onclick="scan()">Run scan</button>' +
            '</div>' +
          '</header>' +
          '<main>' + problem + body + '</main>' +
        '</section>' +
      '</div>';
  }

  function statStrip() {
    var repos = state.repositories || [];
    var alerts = state.alerts || [];
    var tracked = repos.filter(function (r) { return r.watchlisted; }).length;
    var high = repos.filter(function (r) { return r.score && r.score.priority === 'HIGH'; }).length;
    var discovered = state.mode === 'DEMO' ? repos.length : Number(state.last_discovery_count || 0);
    return '<div class="stat-strip">' +
      '<div class="stat-card"><b>' + fmt(discovered) + '</b><span>Discovered</span><small>Current discovery surface</small></div>' +
      '<div class="stat-card"><b>' + fmt(tracked) + '</b><span>Tracked</span><small>Repositories under watch</small></div>' +
      '<div class="stat-card"><b>' + fmt(high) + '</b><span>High priority</span><small>Assessment queue</small></div>' +
      '<div class="stat-card"><b>' + fmt(alerts.length) + '</b><span>Signals</span><small>Recorded changes</small></div>' +
      '<div class="stat-card"><b>' + (state.api_status === 'GitHub REST API connected' ? 'OK' : '—') + '</b><span>API status</span><small>' + (state.mode === 'DEMO' ? 'Offline fixture mode' : 'GitHub REST API') + '</small></div>' +
    '</div>';
  }

  function repoRows(repos, actions) {
    var html = '';
    (repos || []).forEach(function (r) {
      normalizeRepository(r);
      var selected = !!compareSelected[r.full_name];
      var actionHtml = actions ?
        '<td class="actions">' +
          '<label class="compare-check"><input type="checkbox" ' + (selected ? 'checked' : '') + ' onchange="toggleCompare(\'' + esc(r.full_name).replace(/'/g, '&#39;') + '\', this.checked)"> Compare</label>' +
          '<a href="' + githubUrl(r) + '" target="_blank" rel="noopener">GitHub ↗</a>' +
          '<a href="' + repoUrl(r) + '">View</a>' +
          '<button onclick="toggleWatch(\'' + esc(r.full_name).replace(/'/g, '&#39;') + '\',' + (r.watchlisted ? 'true' : 'false') + ')">' + (r.watchlisted ? 'Unwatch' : 'Watch') + '</button>' +
        '</td>' : '';
      html += '<tr>' +
        '<td><a class="repo" href="' + repoUrl(r) + '">' + esc(r.full_name) + '</a><span class="description">' + esc(r.description) + '</span></td>' +
        '<td>' + esc(r.language) + '</td>' +
        '<td>' + fmt(r.stars) + '</td>' +
        '<td>' + fmt(r.forks) + '</td>' +
        '<td>' + date(r.pushed_at) + '</td>' +
        '<td><b>' + r.score.total + '/40</b></td>' +
        '<td>' + priorityBadge(r.score.priority) + '</td>' +
        '<td>' + armyBadge(r.army_relevance) + '</td>' + actionHtml +
      '</tr>';
    });
    return html;
  }

  function table(repos, actions) {
    var withActions = actions !== false;
    var emptyCols = withActions ? 9 : 8;
    return '<div class="data-table"><table><thead><tr>' +
      '<th>Repository</th><th>Language</th><th>Stars</th><th>Forks</th><th>Updated</th><th>Assessment</th><th>Priority</th><th>Army relevance</th>' +
      (withActions ? '<th></th>' : '') +
      '</tr></thead><tbody>' +
      (repos && repos.length ? repoRows(repos, withActions) : '<tr><td colspan="' + emptyCols + '" class="empty">No repositories match this view.</td></tr>') +
      '</tbody></table></div>';
  }

  function signalText(a) {
    if (a.type === 'NEW_REPOSITORY') return 'New repository discovered';
    if (a.type === 'REPOSITORY_UPDATED') return 'Repository updated';
    if (a.type === 'SCORE_CHANGE') return String(a.previous) + '/40 → ' + String(a.current) + '/40 score';
    if (a.type === 'PRIORITY_CHANGE') return String(a.previous) + ' → ' + String(a.current) + ' priority';
    if (a.delta !== null && a.delta !== undefined) return (a.delta > 0 ? '+' : '') + String(a.delta) + ' ' + (a.field || 'change');
    return String(a.type || 'event').split('_').join(' ').toLowerCase();
  }

  function signalList(alerts, limit) {
    var items = (alerts || []).slice().reverse().slice(0, limit || 7);
    if (!items.length) return '<div class="empty">No signals yet. Run another scan after repository data changes.</div>';
    return items.map(function (a) {
      var amber = String(a.type || '').indexOf('SCORE') >= 0 || String(a.type || '').indexOf('PRIORITY') >= 0;
      return '<a class="signal" href="' + repoUrl({full_name:a.repository}) + '">' +
        '<i class="signal-dot ' + (amber ? 'amber' : '') + '"></i>' +
        '<div><b>' + esc(signalText(a)) + '</b><span>' + esc(a.repository) + ' · ' + date(a.detected_at) + '</span></div>' +
        '<em>' + esc(String(a.type || '').split('_').join(' ')) + '</em>' +
      '</a>';
    }).join('');
  }

  function overview() {
    var repos = (state.repositories || []).slice().sort(function (a,b) {
      return Number((b.score && b.score.total) || 0) - Number((a.score && a.score.total) || 0);
    });
    var alerts = state.alerts || [];
    shell('Workspace', 'Repository intelligence',
      statStrip() +
      '<section class="hero-panel">' +
        '<div class="hero-copy"><span class="overline">Open-source repository intelligence</span><h2>Find what matters. Know what changed.</h2><p>Discover projects, explain their technical and defence relevance, then keep the shortlist under continuous observation.</p>' +
          '<div class="quick-search"><input id="home-search" placeholder="Search GitHub repositories…"><button class="button" onclick="homeSearch()">Start discovery →</button></div>' +
          '<div class="quick-links"><a href="/discover">Explore discovery</a><a href="/compare">Compare repositories</a><a href="/army">Open Army Lens</a></div>' +
        '</div>' +
        '<div class="hero-side"><div><div class="hero-side-top"><span class="hero-side-label">Latest query</span><span class="priority p-low">ACTIVE</span></div><div class="hero-query">' + esc(state.last_discovery_query || 'Not searched yet') + '</div><small>' + (state.last_discovery_count ? fmt(state.last_discovery_count) + ' repositories returned' : 'Run discovery to establish a live search surface') + '</small></div><div class="hero-side-footer"><b>Operating principle</b><span>Discovery is broad. Monitoring is explicit.</span></div></div>' +
      '</section>' +
      '<section class="overview-grid">' +
        '<div class="section-block queue"><div class="section-heading"><div><span class="overline">Priority queue</span><h2>What deserves attention</h2></div><a href="/discover">Explore →</a></div><div class="queue-list">' +
          (repos.slice(0,8).map(function (r) { return '<a href="' + repoUrl(r) + '"><span>' + priorityBadge(r.score.priority) + '</span><b>' + esc(r.full_name) + '</b><em>' + r.score.total + '/40</em><small>Army ' + ((r.army_relevance && r.army_relevance.score) || '—') + '/5</small></a>'; }).join('') || '<div class="empty">No tracked repositories yet. Use Discover to find projects.</div>') +
        '</div></div>' +
        '<div class="section-block signals"><div class="section-heading"><div><span class="overline">Recent signals</span><h2>What changed</h2></div><a href="/alerts">Investigate →</a></div>' + signalList(alerts,7) + '</div>' +
      '</section>' +
      '<section class="overview-grid lower">' +
        '<div class="section-block army-overview"><div class="section-heading"><div><span class="overline">Indian Army lens</span><h2>Potentially relevant capabilities</h2></div><a href="/army">Explore →</a></div><div class="capability-grid">' + capabilities.slice(0,6).map(function(c){return '<button onclick="openCapability(\'' + c.name.replace(/'/g,"\\'") + '\',\'' + c.query.replace(/'/g,"\\'") + '\')"><span>' + esc(c.name) + '</span><b>Explore</b></button>';}).join('') + '</div></div>' +
        '<div class="section-block process"><div class="section-heading"><div><span class="overline">Monitoring workflow</span><h2>From discovery to signal</h2></div></div><div class="process-line">' + ['Discover','Assess','Watch','Monitor','Detect','Alert'].map(function(x,i){return '<div><b>' + String(i+1).padStart(2,'0') + '</b><span>' + x + '</span></div>';}).join('') + '</div></div>' +
      '</section>'
    );
    if (state.mode === 'LIVE') refreshDiscoverySummary();
  }

  function homeSearch() {
    var input = document.querySelector('#home-search');
    var q = input ? input.value : 'security monitoring';
    window.location.href = '/discover?q=' + encodeURIComponent(q || 'security monitoring');
  }

  function refreshDiscoverySummary() {
    var q = state.last_discovery_query || 'topic:security';
    fetchJson('/api/discover?q=' + encodeURIComponent(q) + '&page=1').then(function (data) {
      state.last_discovery_count = data.total_count || 0;
      var el = document.querySelector('#discovered-count');
      if (el) el.textContent = fmt(state.last_discovery_count);
    }).catch(function () {});
  }

  function discoverPage() {
    var demo = state.mode === 'DEMO';
    var queryFromUrl = new URLSearchParams(window.location.search).get('q');
    shell('Discover','Explore the open-source ecosystem',
      '<section class="discovery-hero"><div><span class="overline">Discovery workspace</span><h2>Search, assess, shortlist.</h2><p>' + (demo ? 'Demo mode uses the five bundled fixtures for a deterministic offline demonstration.' : 'Search GitHub dynamically. Results remain separate from your monitoring scope until you choose to watch them.') + '</p></div><div class="search-row"><input id="search" placeholder="Search repositories, topics, tools..." value="' + esc(demo ? '' : (queryFromUrl || state.last_discovery_query || 'security monitoring')) + '" ' + (demo ? 'disabled' : '') + '><button class="button" onclick="runDiscovery()">' + (demo ? 'Refresh dataset' : 'Search GitHub') + '</button></div></section>' +
      '<div class="toolbar"><div class="filter-row"><select id="language"><option value="">Any language</option></select><select id="min-stars"><option value="0">Any stars</option><option value="100">100+ stars</option><option value="1000">1k+ stars</option><option value="10000">10k+ stars</option></select><select id="priority-filter"><option value="">Any priority</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option><option>REVIEW</option></select><select id="army-filter"><option value="">Any Army relevance</option><option value="5">5/5</option><option value="4">4+/5</option><option value="3">3+/5</option></select><select id="sort"><option value="score">Highest score</option><option value="army">Army relevance</option><option value="stars">Most stars</option><option value="updated">Recently updated</option></select></div><div class="compare-bar"><span id="compare-count">0 selected</span><a href="/compare">Open comparison →</a></div></div>' +
      '<div id="discovery-result" class="loading">Loading repository results…</div>'
    );
    ['language','min-stars','priority-filter','army-filter','sort'].forEach(function (id) {
      var el = document.querySelector('#' + id);
      if (el) el.addEventListener('change', renderDiscovery);
    });
    var input = document.querySelector('#search');
    if (input) input.addEventListener('keydown', function(e){if(e.key==='Enter')runDiscovery();});
    loadDiscovery(1, demo ? 'topic:security' : (queryFromUrl || state.last_discovery_query || 'security monitoring'));
  }

  function loadDiscovery(page, query) {
    var target = document.querySelector('#discovery-result');
    if (!target) return;
    var searchEl = document.querySelector('#search');
    var requested = query || (searchEl ? searchEl.value : '') || state.last_discovery_query || 'topic:security';
    target.innerHTML = '<div class="loading">Searching and assessing repositories…</div>';
    fetchJson('/api/discover?q=' + encodeURIComponent(requested) + '&page=' + (page || 1)).then(function(data){
      discovery = (data.repositories || []).map(normalizeRepository);
      discoveryMeta = {page:Number(data.page || 1),per_page:Number(data.per_page || 20),total_count:Number(data.total_count || discovery.length),query:requested};
      state.last_discovery_query = requested;
      state.last_discovery_count = discoveryMeta.total_count;
      var select = document.querySelector('#language');
      if (select) {
        var langs = {};
        discovery.forEach(function(r){if(r.language)langs[r.language]=true;});
        select.innerHTML = '<option value="">Any language</option>' + Object.keys(langs).sort().map(function(x){return '<option value="'+esc(x)+'">'+esc(x)+'</option>';}).join('');
      }
      renderDiscovery();
    }).catch(function(error){
      target.innerHTML='<div class="empty-state"><b>Discovery is unavailable</b><span>'+esc(error.message)+'</span><button class="button" onclick="loadDiscovery(1)">Retry</button></div>';
    });
  }

  function runDiscovery() {
    var input=document.querySelector('#search');
    loadDiscovery(1,input ? input.value : 'security monitoring');
  }

  function renderDiscovery() {
    var langEl=document.querySelector('#language'), starsEl=document.querySelector('#min-stars'), pEl=document.querySelector('#priority-filter'), armyEl=document.querySelector('#army-filter'), sortEl=document.querySelector('#sort');
    var lang=langEl ? langEl.value : '', stars=Number(starsEl ? starsEl.value : 0), p=pEl ? pEl.value : '', armyMin=Number(armyEl ? armyEl.value : 0), sort=sortEl ? sortEl.value : 'score';
    var rs=discovery.filter(function(r){return (!lang||r.language===lang)&&Number(r.stars||0)>=stars&&(!p||(r.score&&r.score.priority===p))&&(!armyMin||Number((r.army_relevance&&r.army_relevance.score)||0)>=armyMin);});
    rs.sort(function(a,b){
      if(sort==='stars')return Number(b.stars||0)-Number(a.stars||0);
      if(sort==='updated')return String(b.pushed_at||'').localeCompare(String(a.pushed_at||''));
      if(sort==='army')return Number((b.army_relevance&&b.army_relevance.score)||0)-Number((a.army_relevance&&a.army_relevance.score)||0);
      return Number((b.score&&b.score.total)||0)-Number((a.score&&a.score.total)||0);
    });
    var from=discoveryMeta.total_count?((discoveryMeta.page-1)*discoveryMeta.per_page)+1:0;
    var to=Math.min(discoveryMeta.page*discoveryMeta.per_page,discoveryMeta.total_count);
    var pages=Math.max(1,Math.ceil(discoveryMeta.total_count/discoveryMeta.per_page));
    var pagination=pages>1 ? '<div class="pagination"><span>'+fmt(discoveryMeta.total_count)+' repositories found · Showing '+from+'–'+to+'</span><div><button '+(discoveryMeta.page===1?'disabled':'')+' onclick="loadDiscovery('+(discoveryMeta.page-1)+')">Previous</button><b>'+discoveryMeta.page+' / '+pages+'</b><button '+(discoveryMeta.page===pages?'disabled':'')+' onclick="loadDiscovery('+(discoveryMeta.page+1)+')">Next</button></div></div>' : '<div class="result-count">'+(state.mode==='DEMO'?'5 fixture repositories':fmt(discoveryMeta.total_count)+' repositories found')+'</div>';
    var target=document.querySelector('#discovery-result');
    if(target) target.innerHTML='<div class="result-context"><span>'+fmt(rs.length)+' shown on this page</span><span>Query: '+esc(discoveryMeta.query)+'</span></div>'+table(rs)+pagination;
    updateCompareCount();
  }

  function updateCompareCount(){
    var count=Object.keys(compareSelected).length;
    var el=document.querySelector('#compare-count');
    if(el)el.textContent=count+' selected';
  }

  function toggleCompare(name, checked){
    if(checked) {
      compareSelected[name]=true;
      var repo=discovery.filter(function(r){return r.full_name===name;})[0];
      if(repo) window.__compareRepoCache = window.__compareRepoCache || {}, window.__compareRepoCache[name]=repo;
    } else delete compareSelected[name];
    try { window.sessionStorage.setItem('osswatch_compare', JSON.stringify(compareSelected)); } catch (e) {}
    updateCompareCount();
  }

  function comparePage(){
    var selected=Object.keys(compareSelected);
    var cached=window.__compareRepoCache || {};
    shell('Compare','Compare repositories',
      '<section class="compare-intro"><div><span class="overline">Decision workspace</span><h2>Put repositories side by side.</h2><p>Select repositories in Discover, then compare technical strength, Army relevance, adoption and monitoring priority.</p></div><a class="button secondary" href="/discover">Back to discovery</a></section>' +
      '<div id="compare-stage">' + renderCompareStage(selected,cached) + '</div>'
    );
    if(selected.length) loadCompareDetails(selected);
  }

  function renderCompareStage(selected,cached){
    if(!selected.length)return '<div class="empty-state"><b>No repositories selected</b><span>Go to Discover, select two or more repositories, and return here to compare them.</span><a class="button" href="/discover">Open Discover</a></div>';
    return '<div class="compare-header"><span>'+selected.length+' repositories selected</span><button class="button secondary" onclick="clearCompare()">Clear selection</button></div><div id="compare-table"><div class="loading">Loading repository assessments…</div></div>';
  }

  function loadCompareDetails(names){
    Promise.all(names.map(function(name){return fetchJson('/api/repository?full_name='+encodeURIComponent(name)).then(function(d){return d.repository;});})).then(function(repos){
      var headers='<tr><th>Assessment</th>'+repos.map(function(r){return '<th><a class="repo" href="'+repoUrl(r)+'">'+esc(r.full_name)+'</a></th>';}).join('')+'</tr>';
      var rows='';
      rows += compareRow('Technical score',repos.map(function(r){return '<b>'+r.score.total+'/40</b> '+priorityBadge(r.score.priority);}));
      rows += compareRow('Army relevance',repos.map(function(r){return '<b>'+((r.army_relevance&&r.army_relevance.score)||'—')+'/5</b> '+armyBadge(r.army_relevance);}));
      rows += compareRow('Stars',repos.map(function(r){return fmt(r.stars);}));
      rows += compareRow('Forks',repos.map(function(r){return fmt(r.forks);}));
      rows += compareRow('Activity',repos.map(function(r){return criteria.activity_maintenance+' '+r.score.breakdown.activity_maintenance+'/5';}));
      rows += compareRow('Community',repos.map(function(r){return r.score.breakdown.community_adoption+'/5';}));
      rows += compareRow('Documentation',repos.map(function(r){return r.score.breakdown.documentation+'/5';}));
      rows += compareRow('Defence relevance',repos.map(function(r){return r.score.breakdown.defence_relevance+'/5';}));
      rows += compareRow('Capabilities',repos.map(function(r){return ((r.army_relevance&&r.army_relevance.capabilities)||[]).slice(0,3).map(function(c){return '<span class="tag">'+esc(c)+'</span>';}).join(' ')||'—';}));
      var el=document.querySelector('#compare-table');
      if(el)el.innerHTML='<div class="data-table compare-table"><table><thead>'+headers+'</thead><tbody>'+rows+'</tbody></table></div>';
    }).catch(function(e){var el=document.querySelector('#compare-table');if(el)el.innerHTML='<div class="empty-state"><b>Comparison unavailable</b><span>'+esc(e.message)+'</span></div>';});
  }

  function compareRow(label,values){return '<tr><th>'+esc(label)+'</th>'+values.map(function(v){return '<td>'+v+'</td>';}).join('')+'</tr>';}
  function clearCompare(){compareSelected={};window.__compareRepoCache={};try{window.sessionStorage.removeItem('osswatch_compare');}catch(e){}window.location.href='/discover';}

  function findRepositoryLocal(name){
    var all=state.repositories||[], found=null;
    all.some(function(r){if(r.full_name===name){found=normalizeRepository(r);return true;}return false;});
    if(found)return Promise.resolve(found);
    var dynamic=null;
    discovery.some(function(r){if(r.full_name===name){dynamic=normalizeRepository(r);return true;}return false;});
    if(dynamic)return Promise.resolve(dynamic);
    return fetchJson('/api/repository?full_name='+encodeURIComponent(name)).then(function(d){return normalizeRepository(d.repository);});
  }

  function detail(name){
    shell('Repository','Repository intelligence','<div class="loading">Loading repository profile…</div>');
    findRepositoryLocal(name).then(function(r){
      var history=state.history||[];
      var scores=history.map(function(x){return {at:x.at,score:x.scores ? x.scores[name] : undefined};}).filter(function(x){return x.score!==undefined;});
      var previous=scores.length>1 ? scores[scores.length-2].score : null;
      var alerts=(state.alerts||[]).filter(function(a){return a.repository===name;});
      var army=r.army_relevance||{}, breakdown=r.score&&r.score.breakdown?r.score.breakdown:{};
      var capabilitiesHtml=(army.capabilities||[]).map(function(c){return '<span class="tag">'+esc(c)+'</span>';}).join('')||'<span class="muted">Further evaluation required</span>';
      var considerations=(army.considerations||[]).map(function(c){return '<li>'+esc(c)+'</li>';}).join('');
      var lastRelease=r.last_release ? date(r.last_release) : '—';
      shell('Repository profile',r.full_name,
        '<section class="profile-head enhanced">' +
          '<div><span class="overline">Repository intelligence profile</span><h2 class="repo-title">'+esc(r.name||r.full_name.split('/')[1])+'</h2><p>'+esc(r.description)+'</p><div class="profile-actions"><a class="github-link" href="'+githubUrl(r)+'" target="_blank" rel="noopener">Open on GitHub ↗</a>'+(r.watchlisted?'<span class="watched-label">● Monitored</span>':'<button class="button" onclick="toggleWatch(\''+esc(r.full_name).replace(/'/g,'&#39;')+'\',false)">Add to Watchlist</button>')+'</div></div>' +
          '<div class="dual-assessment"><div class="assessment"><span class="assessment-label">Technical assessment</span><b>'+((r.score&&r.score.total)||0)+'<small>/40</small></b>'+priorityBadge(r.score&&r.score.priority)+'<span>'+((r.score&&r.score.percentage)||0)+'% assessment</span></div><div class="army-summary"><span class="assessment-label">Indian Army relevance</span><b>'+esc(army.score||'—')+'<small>/5</small></b>'+armyBadge(army)+'</div></div>' +
        '</section>' +
        '<section class="facts">'+[['Stars',fmt(r.stars)],['Forks',fmt(r.forks)],['Open issues',fmt(r.open_issues)],['Language',r.language],['License',r.license],['Last push',date(r.pushed_at)],['Last release',lastRelease],['Branch',r.default_branch]].map(function(x){return '<div><span>'+esc(x[0])+'</span><b>'+esc(x[1])+'</b></div>';}).join('')+'</section>' +
        '<section class="decision-band"><div><span class="overline">Monitoring priority</span><h2>Technical '+r.score.total+'/40 · Army relevance '+(army.score||'—')+'/5</h2><p>Use this assessment to decide which repositories warrant further technical evaluation and continuous monitoring.</p></div><a class="button" href="'+githubUrl(r)+'" target="_blank" rel="noopener">Open repository ↗</a></section>' +
        '<section class="profile-grid">' +
          '<div class="section-block assessment-block"><span class="overline">Technical assessment</span><h2>Why this repository scores '+r.score.total+'/40</h2><p class="explanation">'+esc(r.score_explanation||'Assessment is based on available repository metadata and the configured rubric.')+'</p><div class="score-breakdown">'+Object.keys(breakdown).map(function(key){var value=Number(breakdown[key]||0);return '<div><div><span>'+esc(criteria[key]||key)+'</span><b>'+value+'/5</b></div><i><em style="width:'+Math.max(0,Math.min(100,value*20))+'%"></em></i></div>';}).join('')+'</div></div>' +
          '<div class="section-block army-panel"><div class="army-title"><div><span class="overline">Indian Army relevance</span><h2>Potential capability fit</h2></div>'+armyBadge(army)+'</div><div class="army-score-large">'+esc(army.score||'—')+'<small>/5</small></div><p class="explanation">'+esc(army.rationale||'Army relevance is not yet available.')+'</p><div class="tag-list">'+capabilitiesHtml+'</div>'+(considerations?'<div class="considerations"><span class="overline">Considerations</span><ul>'+considerations+'</ul></div>':'')+'</div>' +
        '</section>' +
        '<section class="overview-grid lower">' +
          '<div class="section-block"><span class="overline">Score history</span><h2>Assessment over time</h2>'+(previous!==null?'<div class="history-numbers"><div><span>Previous</span><b>'+previous+'/40</b></div><div><span>Current</span><b>'+r.score.total+'/40</b></div><div><span>Change</span><b class="'+(r.score.total-previous>=0?'positive':'negative')+'">'+(r.score.total-previous>=0?'+':'')+(r.score.total-previous)+'</b></div></div><div class="history-line">'+scores.map(function(x){return '<span title="'+esc(date(x.at))+': '+x.score+'/40" style="height:'+Math.max(12,Number(x.score)*2)+'px"></span>';}).join('')+'</div>':'<div class="empty">A later monitoring run will show score movement here when assessment inputs change.</div>')+'</div>' +
          '<div class="section-block"><span class="overline">Detected changes</span><h2>Repository signals</h2>'+(alerts.length?signalList(alerts,20):'<div class="empty">No change events have been recorded for this repository.</div>')+'</div>' +
        '</section>'
      );
    }).catch(function(error){shell('Repository','Repository not available','<div class="empty-state"><b>Unable to load repository</b><span>'+esc(error.message)+'</span><a class="button" href="/discover">Return to discovery</a></div>');});
  }

  function watchlist(){
    var rs=(state.repositories||[]).filter(function(r){return r.watchlisted;});
    var counts=['HIGH','MEDIUM','LOW','REVIEW'].map(function(p){return rs.filter(function(r){return r.score&&r.score.priority===p;}).length;});
    shell('Watchlist','Monitoring scope','<div class="watch-header"><div><span class="overline">Selected repositories</span><h2>What we monitor</h2><p>Only repositories you explicitly choose are retained in monitoring state between scans.</p></div><div class="watch-counts"><b>'+rs.length+' tracked</b><span>'+counts[0]+' high · '+counts[1]+' medium · '+counts[2]+' low · '+counts[3]+' review</span></div></div>'+(rs.length?table(rs):'<div class="empty-state"><b>No watchlisted repositories</b><span>Discover repositories and add the projects that matter to your monitoring scope.</span><a class="button" href="/discover">Open discovery</a></div>'));
  }

  function alerts(){
    var all=state.alerts||[];
    var body="<section class=\"alert-intro\"><div><span class=\"overline\">Monitoring signals</span><h2>What changed in repositories you watch</h2><p>Changes are generated by previous-versus-current repository snapshots.</p></div><div class=\"alert-count\"><b>"+all.length+"</b><span>recorded signals</span></div></section>"+
      "<div class=\"filter-tabs\"><button class=\"active\" onclick=\"filterAlerts('',this)\">All</button><button onclick=\"filterAlerts('NEW_REPOSITORY',this)\">New repositories</button><button onclick=\"filterAlerts('REPOSITORY_UPDATED',this)\">Updates</button><button onclick=\"filterAlerts('_CHANGE',this)\">Metric changes</button><button onclick=\"filterAlerts('SCORE_CHANGE',this)\">Score changes</button><button onclick=\"filterAlerts('PRIORITY_CHANGE',this)\">Priority changes</button></div>"+
      "<div id=\"alert-table\">"+alertTable(all)+"</div>";
    shell('Alerts','Investigation queue',body);
  }

  function alertTable(items){
    var rows=(items||[]).slice().reverse().map(function(a){return '<tr><td><b>'+esc(String(a.type||'').split('_').join(' '))+'</b></td><td><a class="repo" href="'+repoUrl({full_name:a.repository})+'">'+esc(a.repository)+'</a></td><td>'+esc(a.field||'repository')+'</td><td>'+(a.previous===null||a.previous===undefined?'—':esc(a.previous))+'</td><td>'+(a.current===null||a.current===undefined?'—':esc(a.current))+(a.delta!==null&&a.delta!==undefined?' <span class="delta">'+(a.delta>0?'+':'')+a.delta+'</span>':'')+'</td><td>'+priorityBadge(a.priority)+'</td><td>'+date(a.detected_at)+'</td><td class="actions"><a href="'+githubUrl({full_name:a.repository})+'" target="_blank" rel="noopener">GitHub ↗</a><a href="'+repoUrl({full_name:a.repository})+'">Investigate</a></td></tr>';}).join('');
    return '<div class="data-table"><table><thead><tr><th>Type</th><th>Repository</th><th>Change</th><th>Previous</th><th>Current</th><th>Priority</th><th>Detected</th><th></th></tr></thead><tbody>'+(rows||'<tr><td colspan="8" class="empty">No alert events have been generated.</td></tr>')+'</tbody></table></div>';
  }

  function filterAlerts(filter,button){document.querySelectorAll('.filter-tabs button').forEach(function(x){x.classList.remove('active');});if(button)button.classList.add('active');var target=document.querySelector('#alert-table');if(target)target.innerHTML=alertTable((state.alerts||[]).filter(function(a){return !filter||String(a.type||'').indexOf(filter)>=0;}));}

  function armyPage(initialQuery){
    shell('Army Lens','Indian Army relevance','');
    var app=document.querySelector('#app');
    if(!app)return;
    var body="<section class=\"army-hero-page\"><div><span class=\"overline\">Army-focused assessment</span><h2>Which open-source capabilities may matter most?</h2><p>Explore repositories by broad capability area, then inspect their technical assessment and potential relevance. This is a prioritization aid, not an operational recommendation.</p></div><div class=\"army-note\"><b>5-point relevance scale</b><span>5 = strong potential alignment · 1 = little obvious relevance</span></div></section>"+
      "<div class=\"capability-grid large\">"+capabilities.map(function(c){
        return '<button onclick=\"openCapability(\''+esc(c.name).replace(/'/g,'&apos;')+'\',\''+esc(c.query).replace(/'/g,'&apos;')+'\')\"><span>'+esc(c.name)+'</span><b>Explore →</b></button>';
      }).join('')+"</div>"+
      "<section class=\"section-block army-results\"><div class=\"section-heading\"><div><span class=\"overline\">Results</span><h2 id=\"army-result-title\">"+(initialQuery?'Repositories for '+esc(initialQuery):'Choose a capability area')+"</h2></div></div><div id=\"army-result\">"+(initialQuery?'<div class=\"loading\">Loading capability results…</div>':'<div class=\"empty\">Choose a capability above to explore repositories.</div>')+"</div></section>";
    // Rebuild just the main content while retaining the global shell/navigation.
    var main=app.querySelector('main');
    var notice=main ? main.querySelector('.notice') : null;
    if(main) main.innerHTML=(notice?notice.outerHTML:'')+body;
    if(initialQuery)loadArmyResults(initialQuery);
  }

  function openCapability(name,query){window.location.href='/army?q='+encodeURIComponent(query)+'&name='+encodeURIComponent(name);}

  function loadArmyResults(query){
    fetchJson('/api/discover?q='+encodeURIComponent(query)+'&page=1').then(function(data){
      var rs=(data.repositories||[]).map(normalizeRepository).sort(function(a,b){return Number((b.army_relevance&&b.army_relevance.score)||0)-Number((a.army_relevance&&a.army_relevance.score)||0)||Number((b.score&&b.score.total)||0)-Number((a.score&&a.score.total)||0);});
      var el=document.querySelector('#army-result');
      if(el)el.innerHTML='<div class="result-context"><span>'+fmt(data.total_count||rs.length)+' repositories found</span><span>Sorted by Army relevance</span></div>'+table(rs);
    }).catch(function(e){var el=document.querySelector('#army-result');if(el)el.innerHTML='<div class="empty-state"><b>Army Lens unavailable</b><span>'+esc(e.message)+'</span></div>';});
  }

  function system(){
    var r=state.repositories||[], tracked=r.filter(function(x){return x.watchlisted;});
    shell('System','Monitoring architecture','<section class="architecture"><div class="architecture-flow">'+['GitHub API','Discovery','Assessment','Watchlist','Snapshot','Change detection','Priority','Alerting','Web UI'].map(function(x,i){return '<div><b>'+String(i+1).padStart(2,'0')+'</b><span>'+x+'</span></div>';}).join('')+'</div></section><section class="system-grid"><div class="section-block"><span class="overline">Runtime</span><dl><dt>Operating mode</dt><dd>'+esc(state.mode||'—')+'</dd><dt>Data source</dt><dd>'+(state.mode==='DEMO'?'Bundled fixture dataset':'GitHub public REST API')+'</dd><dt>API status</dt><dd>'+esc(state.api_status||'—')+'</dd><dt>Storage</dt><dd>Local JSON snapshots</dd></dl></div><div class="section-block"><span class="overline">Monitoring state</span><dl><dt>Discovered</dt><dd>'+fmt(state.mode==='DEMO'?r.length:(state.last_discovery_count||0))+'</dd><dt>Tracked</dt><dd>'+tracked.length+'</dd><dt>High priority tracked</dt><dd>'+tracked.filter(function(x){return x.score&&x.score.priority==='HIGH';}).length+'</dd><dt>Recorded signals</dt><dd>'+(state.alerts||[]).length+'</dd></dl></div></section><section class="notice"><b>Scope</b> Dynamic repository discovery, explainable technical assessment, high-level Indian Army relevance assessment, watchlist monitoring, previous-versus-current metadata comparison, and priority-based alerting.</section>');
  }

  function scan(){
    var buttons=document.querySelectorAll('.button');
    buttons.forEach(function(x){x.disabled=true;});
    showScanOverlay();
    fetchJson('/api/scan',{method:'POST'}).then(function(){return fetchJson('/api/state');}).then(function(next){state=next;finishScanOverlay(true);route();}).catch(function(e){finishScanOverlay(false);alert(e.message);}).finally(function(){buttons.forEach(function(x){x.disabled=false;});});
  }

  function showScanOverlay(){
    var overlay=document.createElement('div');overlay.id='scan-overlay';overlay.innerHTML='<div class="scan-modal"><span class="overline">Live monitoring run</span><h2>Refreshing repository intelligence</h2><div class="scan-steps"><div class="active"><b>01</b><span>Fetch tracked repositories</span></div><div><b>02</b><span>Normalize metadata</span></div><div><b>03</b><span>Recalculate assessments</span></div><div><b>04</b><span>Compare snapshots</span></div><div><b>05</b><span>Generate signals</span></div></div><div class="scan-progress"><i></i></div></div>';document.body.appendChild(overlay);
    var steps=overlay.querySelectorAll('.scan-steps div'), index=0;
    scanTimer=setInterval(function(){if(index<steps.length){steps[index].classList.add('complete');if(index+1<steps.length)steps[index+1].classList.add('active');index++;}},550);
  }

  function finishScanOverlay(ok){clearInterval(scanTimer);var overlay=document.querySelector('#scan-overlay');if(!overlay)return;overlay.querySelector('.scan-modal h2').textContent=ok?'Monitoring run complete':'Monitoring run failed';setTimeout(function(){if(overlay.parentNode)overlay.parentNode.removeChild(overlay);},500);}

  function toggleWatch(name,watched){
    var url,options={method:'POST'};
    if(watched)url='/api/watchlist/'+encodeURIComponent(name);
    else{url='/api/watchlist';options.headers={'Content-Type':'application/json'};options.body=JSON.stringify({full_name:name});}
    fetchJson(url,options).then(function(){return fetchJson('/api/state');}).then(function(next){state=next;if(path==='/discover')loadDiscovery(discoveryMeta.page,discoveryMeta.query);else if(path.indexOf('/repository/')===0)detail(name);else route();}).catch(function(e){alert(e.message);});
  }

  function route(){
    if(path==='/discover')discoverPage();
    else if(path==='/compare')comparePage();
    else if(path==='/watchlist')watchlist();
    else if(path==='/alerts')alerts();
    else if(path==='/army'){var q=new URLSearchParams(window.location.search).get('q');armyPage(q||'');}
    else if(path==='/system')system();
    else if(path.indexOf('/repository/')===0)detail(decodeURIComponent(path.slice(12)));
    else overview();
  }

  window.scan=scan;
  window.toggleWatch=toggleWatch;
  window.runDiscovery=runDiscovery;
  window.loadDiscovery=loadDiscovery;
  window.filterAlerts=filterAlerts;
  window.toggleCompare=toggleCompare;
  window.clearCompare=clearCompare;
  window.homeSearch=homeSearch;
  window.openCapability=openCapability;

  fetchJson('/api/state').then(function(data){state=data||{};route();}).catch(function(error){var app=document.querySelector('#app');if(app)app.innerHTML='<div class="startup-error"><div><b>OSS Watch could not start</b><span>'+esc(error.message)+'</span><button class="button" onclick="location.reload()">Reload</button></div></div>';});
}());
