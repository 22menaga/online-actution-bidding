import { Component, createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { clock } from './api.js';

/* ------------------------------------------------------------------ design system
   Dark "auction house" theme: obsidian surfaces, champagne-gold accents, serif display
   type. Styles are injected from JS so the project ships no stylesheet files. */
const CSS = `
:root{
  --bg:#07060c;--bg2:#0d0b18;--glass:rgba(22,19,40,.66);--glass2:rgba(34,29,62,.7);
  --line:rgba(255,255,255,.08);--line2:rgba(255,255,255,.16);
  --text:#f4f1ff;--mute:#a7a2bd;--faint:#6f6a88;
  --gold1:#fbe7ae;--gold2:#e0aa48;--gold3:#a8741c;--brand:#8b6cff;--pink:#ff5c9a;--ok:#37e6a0;--bad:#ff6b7a;
  --gold:linear-gradient(135deg,var(--gold1),var(--gold2) 55%,var(--gold3));
  --r:16px;--shadow:0 18px 50px -18px rgba(0,0,0,.7);
  --display:'Fraunces','Playfair Display',Georgia,serif;--sans:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 var(--sans);-webkit-font-smoothing:antialiased;overflow-x:hidden}
body::before{content:"";position:fixed;inset:0;z-index:-2;background:
  radial-gradient(900px 500px at 12% -5%,rgba(139,108,255,.20),transparent 60%),
  radial-gradient(800px 500px at 100% 10%,rgba(255,92,154,.12),transparent 60%),
  radial-gradient(900px 600px at 50% 120%,rgba(224,170,72,.10),transparent 60%),var(--bg)}
::selection{background:rgba(224,170,72,.35)}
::-webkit-scrollbar{width:10px}::-webkit-scrollbar-thumb{background:#2a2545;border-radius:10px}::-webkit-scrollbar-track{background:transparent}
a{color:inherit;text-decoration:none}
h1,h2,h3{font-family:var(--display);font-weight:600;letter-spacing:-.01em;margin:0 0 .5em;line-height:1.12}
h1{font-size:clamp(30px,4.5vw,46px)}h2{font-size:clamp(22px,2.6vw,30px)}h3{font-size:19px}
p{margin:0 0 .8em}
:focus-visible{outline:2px solid var(--gold2);outline-offset:2px;border-radius:8px}
.wrap{max-width:1200px;margin:0 auto;padding:0 22px}
.page{padding-top:34px;padding-bottom:72px;animation:rise .45s cubic-bezier(.2,.7,.2,1) both}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.gold-text{background:var(--gold);-webkit-background-clip:text;background-clip:text;color:transparent}
.eyebrow{font-size:12px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:var(--gold2)}
.mute{color:var(--mute)}.faint{color:var(--faint)}.small{font-size:13px}.center{text-align:center}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.between{justify-content:space-between}.grow{flex:1}
.stack>*+*{margin-top:16px}
.grid{display:grid;gap:22px;grid-template-columns:repeat(auto-fill,minmax(272px,1fr))}
.split{display:grid;gap:28px;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);align-items:start}
.sticky{position:sticky;top:84px}
.detail{display:grid;gap:28px;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);grid-template-areas:'view bid' 'info bid';grid-template-rows:auto 1fr;align-items:start}
.d-view{grid-area:view}.d-info{grid-area:info}.d-bid{grid-area:bid;position:sticky;top:84px}
@media(max-width:900px){.detail{grid-template-columns:1fr;grid-template-areas:'view' 'bid' 'info';grid-template-rows:none}.d-bid{position:static}}
@media(max-width:900px){.split{grid-template-columns:1fr}.sticky{position:static}}

/* nav */
.nav{position:sticky;top:0;z-index:30;background:rgba(7,6,12,.72);backdrop-filter:blur(16px) saturate(1.4);border-bottom:1px solid var(--line)}
.nav .wrap{display:flex;align-items:center;gap:26px;height:66px}
.brand{display:flex;align-items:center;gap:10px;font-family:var(--display);font-weight:700;font-size:20px;letter-spacing:.02em}
.brand svg{width:26px;height:26px}
.nav .links{display:flex;gap:6px;align-items:center}
.nav a.link{position:relative;color:var(--mute);padding:8px 12px;border-radius:10px;font-weight:500;transition:color .2s,background .2s}
.nav a.link:hover{color:var(--text);background:rgba(255,255,255,.05)}
.nav a.link.active{color:var(--text)}.nav a.link.active::after{content:"";position:absolute;left:12px;right:12px;bottom:2px;height:2px;border-radius:2px;background:var(--gold)}
.rolechip{display:inline-block;padding:2px 9px;border-radius:99px;font-size:10px;font-weight:800;letter-spacing:.1em;text-transform:uppercase;white-space:nowrap}
.rolechip.BUYER{background:rgba(224,170,72,.16);color:var(--gold1)}
.rolechip.SELLER{background:rgba(47,214,161,.16);color:#7ff0c8}
.rolechip.ADMIN{background:rgba(139,108,255,.2);color:#cdbfff}
:root{--accent:var(--gold)}
html[data-role=SELLER]{--accent:linear-gradient(135deg,#9dffd8,#2fd6a1 55%,#0f8f6a);--accent-solid:#2fd6a1}
html[data-role=ADMIN]{--accent:linear-gradient(135deg,#d9ccff,#8b6cff 55%,#5a3fd0);--accent-solid:#8b6cff}
html[data-role=SELLER] body::before{background:radial-gradient(900px 500px at 12% -5%,rgba(47,214,161,.14),transparent 60%),radial-gradient(800px 500px at 100% 10%,rgba(139,108,255,.10),transparent 60%),var(--bg)}
.nav a.link.active::after{background:var(--accent)}
.pmenu{position:relative}
.pbtn{display:flex;align-items:center;gap:9px;background:rgba(255,255,255,.04);border:1px solid var(--line2);border-radius:99px;padding:4px 12px 4px 4px;color:var(--text);cursor:pointer;font:600 13px var(--sans);transition:.18s}
.pbtn:hover{border-color:var(--gold2)}
.pdrop{position:absolute;right:0;top:calc(100% + 10px);z-index:60;width:300px;background:rgba(18,15,34,.98);border:1px solid var(--line2);border-radius:16px;padding:8px;box-shadow:0 24px 60px -12px rgba(0,0,0,.85);animation:rise .18s both}
.pdrop .phead{display:flex;gap:12px;align-items:center;padding:10px 10px 12px;border-bottom:1px solid var(--line);margin-bottom:6px}
.pdrop .plabel{font-size:10px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:var(--faint);padding:8px 10px 4px}
.pitem{display:flex;gap:10px;align-items:center;width:100%;background:none;border:0;color:var(--text);padding:9px 10px;border-radius:10px;cursor:pointer;font:500 14px var(--sans)}
.pitem:hover{background:rgba(255,255,255,.06)}
.avatar.sm{width:26px;height:26px;font-size:11px}
html[data-role=SELLER] .avatar{background:var(--accent);color:#04281b}
html[data-role=ADMIN] .avatar{background:var(--accent);color:#14093a}
@media(max-width:860px){.pname{display:none}.pdrop{position:fixed;left:12px;right:12px;width:auto;top:70px}}
.bell{position:relative;display:grid;place-items:center;width:40px;height:40px;border-radius:12px;color:var(--mute);transition:.2s}
.bell:hover{background:rgba(255,255,255,.06);color:var(--text)}
.bell .count{position:absolute;top:3px;right:2px;min-width:18px;height:18px;border-radius:9px;padding:0 5px;background:var(--pink);color:#fff;font-size:11px;font-weight:700;display:grid;place-items:center;box-shadow:0 0 0 2px var(--bg)}
.avatar{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:var(--gold);color:#2a1a00;font-weight:800;font-size:14px;flex:none}
.burger{display:none;background:none;border:0;color:var(--text);padding:8px;cursor:pointer}
@media(max-width:860px){
  .burger{display:block;margin-left:auto}
  .nav .links{position:fixed;inset:66px 0 auto 0;flex-direction:column;align-items:stretch;background:rgba(10,8,20,.97);padding:14px 22px 22px;gap:2px;border-bottom:1px solid var(--line);transform:translateY(-12px);opacity:0;pointer-events:none;transition:.22s}
  .nav .links.open{transform:none;opacity:1;pointer-events:auto}
  .nav .grow{display:none}
}

/* surfaces */
/* no backdrop-filter on cards: blurring dozens of cards over a WebGL layer is what makes scrolling janky */
.card{position:relative;background:rgba(20,17,38,.88);border:1px solid var(--line);border-radius:var(--r);box-shadow:var(--shadow)}
.card.pad{padding:22px}.card.clip{overflow:hidden}
.card.glow::before{content:"";position:absolute;inset:-1px;border-radius:inherit;padding:1px;background:linear-gradient(140deg,rgba(251,231,174,.55),transparent 40%,rgba(139,108,255,.4));-webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;pointer-events:none}
.divider{height:1px;background:var(--line);margin:16px 0}

/* buttons / forms */
.btn{position:relative;overflow:hidden;display:inline-flex;align-items:center;justify-content:center;gap:8px;border:1px solid transparent;border-radius:12px;padding:11px 20px;font:600 14px var(--sans);color:#fff;background:linear-gradient(135deg,#9a7dff,#6f4df0);cursor:pointer;transition:transform .12s,box-shadow .2s,filter .2s;box-shadow:0 8px 24px -10px rgba(111,77,240,.8)}
.btn:hover{filter:brightness(1.12);transform:translateY(-1px)}.btn:active{transform:translateY(0) scale(.98)}
.btn::after{content:"";position:absolute;inset:0;background:linear-gradient(110deg,transparent 30%,rgba(255,255,255,.28) 50%,transparent 70%);transform:translateX(-120%);transition:transform .6s}
.btn:hover::after{transform:translateX(120%)}
.btn.ok{background:linear-gradient(135deg,#3be8a4,#1faa72);color:#04281b;box-shadow:0 10px 28px -10px rgba(55,230,160,.7)}
.btn:disabled{opacity:.45;cursor:not-allowed;transform:none;filter:none}.btn:disabled::after{display:none}
.btn.gold{background:var(--gold);color:#2a1a00;box-shadow:0 10px 28px -10px rgba(224,170,72,.7)}
.btn.pink{background:linear-gradient(135deg,#ff7bb0,#e8325f);box-shadow:0 10px 28px -10px rgba(232,50,95,.7)}
.btn.ghost{background:rgba(255,255,255,.04);border-color:var(--line2);box-shadow:none;color:var(--text)}
.btn.sm{padding:7px 14px;font-size:13px;border-radius:10px}.btn.lg{padding:15px 28px;font-size:16px;border-radius:14px}.btn.block{width:100%}
input,select,textarea{width:100%;background:rgba(10,8,22,.7);border:1px solid var(--line2);border-radius:12px;color:var(--text);padding:12px 14px;font:inherit;transition:border-color .2s,box-shadow .2s}
input::placeholder{color:var(--faint)}
input:focus,select:focus,textarea:focus{outline:none;border-color:var(--gold2);box-shadow:0 0 0 4px rgba(224,170,72,.15)}
select{appearance:none;background-image:linear-gradient(45deg,transparent 50%,var(--mute) 50%),linear-gradient(135deg,var(--mute) 50%,transparent 50%);background-position:calc(100% - 20px) 50%,calc(100% - 15px) 50%;background-size:5px 5px;background-repeat:no-repeat;padding-right:36px}
label{display:block;font-size:12px;font-weight:600;letter-spacing:.04em;color:var(--mute);margin:14px 0 6px}
.err{color:var(--bad);font-size:13px;margin:8px 0}
.banner{display:flex;gap:10px;align-items:flex-start;background:rgba(224,170,72,.1);border:1px solid rgba(224,170,72,.35);color:var(--gold1);padding:12px 14px;border-radius:12px;font-size:14px}
.banner.info{background:rgba(139,108,255,.12);border-color:rgba(139,108,255,.4);color:#d5c9ff}
.chips{display:flex;gap:8px;flex-wrap:wrap}
.chip{border:1px solid var(--line2);background:rgba(255,255,255,.03);color:var(--mute);border-radius:99px;padding:7px 15px;font:500 13px var(--sans);cursor:pointer;transition:.18s}
.chip:hover{color:var(--text);border-color:var(--gold2)}.chip.on{background:var(--gold);color:#2a1a00;border-color:transparent;font-weight:700}

/* badges */
.badge{display:inline-flex;align-items:center;gap:6px;padding:3px 11px;border-radius:99px;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;background:rgba(255,255,255,.07);color:var(--mute)}
.badge.LIVE,.badge.SUCCESS,.badge.SOLD,.badge.ok{background:rgba(55,230,160,.13);color:var(--ok)}
.badge.LIVE::before{content:"";width:6px;height:6px;border-radius:50%;background:var(--ok);animation:blink 1.4s infinite}
.badge.SCHEDULED,.badge.PENDING,.badge.PROCESSING,.badge.PENDING_APPROVAL,.badge.warn{background:rgba(224,170,72,.14);color:var(--gold1)}
.badge.FAILED,.badge.CANCELLED,.badge.UNSOLD,.badge.REJECTED,.badge.bad{background:rgba(255,107,122,.14);color:var(--bad)}
@keyframes blink{50%{opacity:.25}}
.price{font-family:var(--display);font-weight:700;background:var(--gold);-webkit-background-clip:text;background-clip:text;color:transparent;font-variant-numeric:tabular-nums}

/* auction card */
.acard{display:block;transform-style:preserve-3d;transition:transform .18s ease-out,border-color .25s,box-shadow .25s;will-change:transform}
.acard:hover{border-color:rgba(224,170,72,.5);box-shadow:0 30px 60px -24px rgba(0,0,0,.9),0 0 0 1px rgba(224,170,72,.2)}
.acard .shot{position:relative;aspect-ratio:4/3;overflow:hidden;background:linear-gradient(135deg,#1d1a3a,#2a1f5c)}
.acard .shot img{width:100%;height:100%;object-fit:cover;transition:transform .6s cubic-bezier(.2,.7,.2,1)}
.acard:hover .shot img{transform:scale(1.07)}
.acard .shot .ph{display:grid;place-items:center;height:100%;font-size:46px;opacity:.6}
.acard .tag{position:absolute;top:12px;left:12px}
.acard .heart{position:absolute;top:10px;right:10px}
.acard .body{padding:16px 18px 18px;transform:translateZ(24px)}
.heartbtn{display:grid;place-items:center;width:36px;height:36px;border-radius:50%;border:1px solid var(--line2);background:rgba(8,6,16,.6);backdrop-filter:blur(8px);color:var(--text);cursor:pointer;transition:.18s}
.heartbtn:hover{transform:scale(1.12)}.heartbtn.on{color:var(--pink);border-color:var(--pink)}
.meter{height:4px;border-radius:4px;background:rgba(255,255,255,.08);overflow:hidden;margin-top:10px}
.meter>i{display:block;height:100%;background:var(--gold);border-radius:4px;transition:width 1s linear}
.meter.hot>i{background:linear-gradient(90deg,var(--pink),#ff9a62)}

/* tables / lists */
table{width:100%;border-collapse:collapse}
th,td{text-align:left;padding:12px 10px;border-bottom:1px solid var(--line)}
th{color:var(--faint);font-weight:600;font-size:11px;letter-spacing:.12em;text-transform:uppercase}
tbody tr{transition:background .15s}tbody tr:hover{background:rgba(255,255,255,.025)}
tr:last-child td{border-bottom:0}
.bidrow{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--line);animation:rise .4s both}
.bidrow:last-child{border-bottom:0}
.bidrow .avatar{width:32px;height:32px;font-size:12px;background:rgba(255,255,255,.08);color:var(--mute)}
.bidrow.top .avatar{background:var(--gold);color:#2a1a00}

/* countdown */
.cd{display:flex;gap:10px}
.cd .cell{flex:1;text-align:center;padding:10px 4px;border-radius:12px;background:rgba(0,0,0,.35);border:1px solid var(--line)}
.cd .cell b{display:block;font:700 26px var(--display);font-variant-numeric:tabular-nums;line-height:1.1}
.cd .cell span{font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--faint)}
.cd.urgent .cell{border-color:rgba(255,107,122,.5);animation:pulseB 1s infinite}.cd.urgent b{color:var(--bad)}
@keyframes pulseB{50%{box-shadow:0 0 22px -4px rgba(255,107,122,.55)}}

/* feedback */
.skel{position:relative;overflow:hidden;background:rgba(255,255,255,.05);border-radius:10px}
.skel::after{content:"";position:absolute;inset:0;background:linear-gradient(100deg,transparent 20%,rgba(255,255,255,.07) 50%,transparent 80%);animation:shimmer 1.4s infinite}
@keyframes shimmer{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.empty{text-align:center;padding:56px 20px}.empty .ico{font-size:44px;margin-bottom:8px;opacity:.85}
.toasts{position:fixed;right:18px;bottom:18px;z-index:80;display:flex;flex-direction:column;gap:10px;max-width:calc(100vw - 36px)}
.toast{display:flex;gap:10px;align-items:flex-start;background:rgba(20,17,38,.95);border:1px solid var(--line2);border-left:3px solid var(--brand);backdrop-filter:blur(12px);padding:13px 16px;border-radius:12px;min-width:250px;max-width:380px;box-shadow:var(--shadow);animation:toastin .35s cubic-bezier(.2,.9,.3,1.2) both}
.toast.ok{border-left-color:var(--ok)}.toast.err{border-left-color:var(--bad)}.toast.warn{border-left-color:var(--gold2)}
@keyframes toastin{from{opacity:0;transform:translateX(30px) scale(.96)}to{opacity:1;transform:none}}
.flash{animation:flash .9s ease-out}
@keyframes flash{0%{box-shadow:0 0 0 0 rgba(224,170,72,.7)}100%{box-shadow:0 0 0 26px rgba(224,170,72,0)}}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;background:var(--faint);margin-right:6px}.dot.live{background:var(--ok);box-shadow:0 0 10px var(--ok)}
.state{padding:10px 14px;border-radius:12px;font-weight:600;display:flex;gap:8px;align-items:center}
.state.win{background:rgba(55,230,160,.12);color:var(--ok);border:1px solid rgba(55,230,160,.35)}
.state.lose{background:rgba(255,107,122,.12);color:var(--bad);border:1px solid rgba(255,107,122,.35)}

/* hero */
.hero{position:relative;height:min(78vh,680px);min-height:520px;border-bottom:1px solid var(--line);overflow:hidden}
.hero canvas{position:absolute;inset:0}
.hero .copy{position:absolute;inset:0;display:flex;align-items:center;pointer-events:none;background:linear-gradient(90deg,rgba(7,6,12,.92) 0%,rgba(7,6,12,.55) 42%,transparent 70%)}
.hero .copy .wrap{width:100%}
.hero .copy .wrap>div{max-width:560px;pointer-events:auto}
.hero h1{font-size:clamp(38px,6vw,68px);margin:.25em 0 .3em}
.hero .hint{position:absolute;bottom:16px;left:0;right:0;text-align:center;color:var(--faint);font-size:12px;letter-spacing:.18em;text-transform:uppercase;pointer-events:none}
@media(max-width:760px){.hero .copy{background:linear-gradient(180deg,rgba(7,6,12,.85),rgba(7,6,12,.2) 70%);align-items:flex-start;padding-top:36px}}
.stats{display:flex;gap:28px;margin-top:30px;flex-wrap:wrap}.stats b{display:block;font:700 28px var(--display)}.stats span{font-size:12px;color:var(--mute);letter-spacing:.08em;text-transform:uppercase}
.step{padding:26px}.step .n{font:700 44px var(--display);opacity:.9}
.auth{display:grid;grid-template-columns:1.1fr 1fr;min-height:calc(100vh - 66px)}
.auth .art{position:relative;border-right:1px solid var(--line);background:#07060c}
.auth .art .cap{position:absolute;left:36px;right:36px;bottom:36px}
.auth .formside{display:grid;grid-template-columns:minmax(0,1fr);justify-items:center;align-items:center;padding:36px 22px}
@media(max-width:860px){.auth{grid-template-columns:minmax(0,1fr)}.auth .art{display:none}.auth .formside{min-width:0}}
.pw-meter{display:flex;gap:4px;margin-top:8px}.pw-meter i{flex:1;height:4px;border-radius:4px;background:rgba(255,255,255,.1)}
.viewer{position:relative;aspect-ratio:4/3;background:radial-gradient(circle at 50% 40%,#241c4a,#0a0816)}
.viewer .tabs{position:absolute;top:12px;left:12px;z-index:2}
.thumbs{display:flex;gap:8px;padding:12px;overflow-x:auto}.thumbs img{height:60px;width:80px;object-fit:cover;border-radius:8px;cursor:pointer;border:2px solid transparent;opacity:.7}.thumbs img.on{border-color:var(--gold2);opacity:1}
.tabs2{display:flex;gap:6px;border-bottom:1px solid var(--line);margin-bottom:22px;overflow-x:auto}
.tabs2 button{background:none;border:0;color:var(--mute);padding:12px 16px;font:600 14px var(--sans);cursor:pointer;border-bottom:2px solid transparent;white-space:nowrap}
.tabs2 button:hover{color:var(--text)}.tabs2 button.on{color:var(--text);border-color:var(--gold2)}
.tabs2 .n{display:inline-grid;place-items:center;min-width:20px;height:20px;border-radius:10px;background:var(--pink);color:#fff;font-size:11px;margin-left:6px;padding:0 6px}
.kpi{padding:18px 20px}.kpi b{display:block;font:700 30px var(--display);line-height:1.1}.kpi span{font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.check{display:flex;gap:10px;align-items:flex-start;padding:8px 0;border-bottom:1px solid var(--line)}.check:last-child{border-bottom:0}
.check .ic{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-size:12px;font-weight:800}
.check.ok .ic{background:rgba(55,230,160,.15);color:var(--ok)}.check.warn .ic{background:rgba(224,170,72,.18);color:var(--gold1)}.check.fail .ic{background:rgba(255,107,122,.18);color:var(--bad)}
.drop{display:grid;place-items:center;text-align:center;gap:4px;padding:22px 14px;border:2px dashed var(--line2);border-radius:14px;background:rgba(255,255,255,.02);cursor:pointer;transition:border-color .2s,background .2s}
.drop:hover,.drop.over{border-color:var(--gold2);background:rgba(224,170,72,.06)}
.previews{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;cursor:default}
.thumbcard{position:relative;width:96px;height:96px;border-radius:12px;overflow:hidden;border:1px solid var(--line2);background:#0b0a14;padding:0}
.thumbcard img{width:100%;height:100%;object-fit:cover}
.thumbcard>button{position:absolute;top:4px;right:4px;width:22px;height:22px;border-radius:50%;border:0;background:rgba(0,0,0,.7);color:#fff;cursor:pointer;line-height:1}
.thumbcard.add{display:grid;place-items:center;font-size:28px;color:var(--mute);cursor:pointer;border-style:dashed}
.thumbcard.scanning::after{content:"";position:absolute;left:0;right:0;height:34%;background:linear-gradient(180deg,transparent,rgba(224,170,72,.55),transparent);animation:scan 1.4s linear infinite}
@keyframes scan{from{top:-34%}to{top:100%}}
.drawer-bg{position:fixed;inset:0;z-index:70;background:rgba(3,2,10,.62);backdrop-filter:blur(3px);animation:fade .2s both}
.drawer{position:absolute;right:0;top:0;bottom:0;width:min(780px,100%);overflow-y:auto;background:#0e0c1c;border-left:1px solid var(--line2);padding:22px 24px 40px;box-shadow:-30px 0 80px -20px rgba(0,0,0,.8);animation:slidein .28s cubic-bezier(.2,.8,.2,1) both}
@keyframes slidein{from{transform:translateX(40px);opacity:0}to{transform:none;opacity:1}}
@keyframes fade{from{opacity:0}to{opacity:1}}
.kv{display:grid;grid-template-columns:130px 1fr;gap:12px;padding:8px 0;border-bottom:1px solid var(--line);font-size:14px}
.kv:last-child{border-bottom:0}.kv>span{color:var(--faint);font-size:12px;letter-spacing:.08em;text-transform:uppercase;padding-top:2px}
@media(max-width:600px){.kv{grid-template-columns:1fr;gap:2px}}
table.clicky tbody tr{cursor:pointer}table.clicky tbody tr:focus-visible{outline:2px solid var(--gold2);outline-offset:-2px}
.plink{background:none;border:0;padding:0;color:var(--gold1);font:inherit;font-weight:700;cursor:pointer;text-decoration:underline dotted;text-underline-offset:3px}
.plink:hover{color:#fff}
.modal-bg{position:fixed;inset:0;z-index:75;background:rgba(3,2,10,.7);backdrop-filter:blur(3px);display:grid;place-items:center;padding:16px;animation:fade .2s both}
.modal{width:min(520px,100%);max-height:calc(100vh - 32px);overflow-y:auto;background:#100e20;border:1px solid var(--line2);border-radius:20px;padding:24px;box-shadow:0 40px 100px -20px rgba(0,0,0,.9);animation:rise .25s both}
.mcard{border:1px solid var(--line2);border-radius:14px;padding:14px 16px;background:rgba(255,255,255,.025)}
.mcard.dim{opacity:.7}
.coinpill{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:99px;background:rgba(224,170,72,.13);border:1px solid rgba(224,170,72,.35);color:var(--gold1);font:700 13px var(--sans);white-space:nowrap}
html[data-role=SELLER] .coinpill{background:rgba(47,214,161,.12);border-color:rgba(47,214,161,.35);color:#7ff0c8}
.skip{position:fixed;left:12px;top:-60px;z-index:200;background:var(--gold);color:#2a1a00;padding:10px 16px;border-radius:10px;font-weight:700;transition:top .2s}.skip:focus{top:12px}
.offline{position:sticky;top:66px;z-index:25;text-align:center;padding:9px 16px;background:rgba(255,107,122,.16);border-bottom:1px solid rgba(255,107,122,.5);color:#ffb3bb;font-weight:600;font-size:14px}
.viewers{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:99px;background:rgba(255,255,255,.06);font-size:12px;font-weight:700;color:var(--mute)}
.viewers i{width:7px;height:7px;border-radius:50%;background:var(--ok);box-shadow:0 0 8px var(--ok);animation:blink 1.4s infinite}
.phase{margin:12px 0 0;padding:12px 14px;border-radius:12px;font-weight:800;text-align:center;letter-spacing:.04em;background:rgba(255,107,122,.12);border:1px solid rgba(255,107,122,.5);color:#ff9aa6;animation:pulseB 1s infinite}
.phase.hot{font-size:20px;background:rgba(255,107,122,.22)}
.foot{border-top:1px solid var(--line);padding:30px 0;color:var(--faint);font-size:13px}
.checkout-card{background:linear-gradient(135deg,#2a1f5c,#12102a);border-radius:18px;padding:22px;border:1px solid var(--line2);margin-bottom:6px}
.confetti{position:fixed;inset:0;pointer-events:none;z-index:90;overflow:hidden}.confetti i{position:absolute;top:-20px;width:9px;height:14px;opacity:.9;animation:fall linear forwards}
@keyframes fall{to{transform:translateY(110vh) rotate(720deg)}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.001ms!important;transition-duration:.001ms!important}}
`;

export function injectStyles() {
  if (document.getElementById('app-css')) return;
  const font = document.createElement('link');
  font.rel = 'stylesheet';
  font.href = 'https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700;800&display=swap';
  document.head.appendChild(font);
  const el = document.createElement('style');
  el.id = 'app-css';
  el.textContent = CSS;
  document.head.appendChild(el);
  const icon = document.createElement('link');
  icon.rel = 'icon';
  icon.href = `data:image/svg+xml,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="8" fill="#0d0b18"/><path d="M8 22l9-9 3 3-9 9z M15 8l5-3 7 7-3 5z" fill="#e0aa48"/></svg>')}`;
  document.head.appendChild(icon);
}

/* ------------------------------------------------------------------ helpers */
export const money = (n, digits = 2) =>
  n == null || Number.isNaN(Number(n)) ? '—' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 0, maximumFractionDigits: digits }).format(n);

/** Date -> value for <input type="datetime-local"> in the viewer's local time. */
export const toLocalInput = (d) => {
  const x = new Date(d); const p = (n) => String(n).padStart(2, '0');
  return `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}T${p(x.getHours())}:${p(x.getMinutes())}`;
};
export const fmtDateTime = (d) => (d ? new Date(d).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : '—');

/** Same masking the server uses for public bidder names ('alice99' -> 'al***9'). */
export const maskName = (n = '') => (n.length > 3 ? `${n.slice(0, 2)}***${n.slice(-1)}` : `${n.slice(0, 1)}***`);

export const initials = (name = '?') => {
  const clean = name.replace(/\*/g, '');
  const parts = clean.split(/[_\s.-]+/).filter(Boolean);
  return (parts.length > 1 ? parts[0][0] + parts[1][0] : clean.slice(0, 2)).toUpperCase();
};

export const Icon = ({ name, size = 20 }) => {
  const paths = {
    heart: 'M12 21s-7-4.6-9.3-9A5.4 5.4 0 0112 6.5 5.4 5.4 0 0121.3 12C19 16.4 12 21 12 21z',
    bell: 'M18 16v-5a6 6 0 10-12 0v5l-2 2h16zM10 21h4',
    clock: 'M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    search: 'M21 21l-4.3-4.3M17 10.5a6.5 6.5 0 11-13 0 6.5 6.5 0 0113 0z',
    shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z M9 12l2 2 4-4',
    bolt: 'M13 2L4 14h7l-1 8 9-12h-7z',
    share: 'M4 12v7a1 1 0 001 1h14a1 1 0 001-1v-7M16 6l-4-4-4 4M12 2v13',
    gavel: 'M14 5l5 5-3 3-5-5zM9 9l-6 6 3 3 6-6M13 19h8',
    lock: 'M6 11V8a6 6 0 1112 0v3M5 11h14v10H5z',
    check: 'M5 12l5 5 9-10',
    menu: 'M4 7h16M4 12h16M4 17h16',
    x: 'M6 6l12 12M18 6L6 18',
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={paths[name]} />
    </svg>
  );
};

export const Badge = ({ status, children }) => <span className={`badge ${status}`}>{children ?? String(status).replace(/_/g, ' ')}</span>;

export function Field({ label, children }) {
  return (<div><label>{label}</label>{children}</div>);
}

export const Skeleton = ({ h = 16, w = '100%', r }) => <div className="skel" style={{ height: h, width: w, borderRadius: r }} />;

export function CardSkeletons({ n = 6 }) {
  return (
    <div className="grid">
      {Array.from({ length: n }, (_, i) => (
        <div key={i} className="card clip"><Skeleton h={200} r={0} /><div style={{ padding: 18 }} className="stack"><Skeleton h={18} w="70%" /><Skeleton h={14} w="40%" /><Skeleton h={26} w="55%" /></div></div>
      ))}
    </div>
  );
}

export function EmptyState({ icon = '🏺', title, children, action }) {
  return (<div className="card empty"><div className="ico">{icon}</div><h3>{title}</h3><p className="mute">{children}</p>{action}</div>);
}

/** Pointer-driven 3D tilt: rotates its child toward the cursor. */
export function Tilt({ children, max = 7, className = '', style, ...rest }) {
  const ref = useRef(null);
  const raf = useRef(0);
  const move = (e) => {
    const el = ref.current; if (!el || matchMedia('(pointer: coarse)').matches) return;
    const { clientX, clientY } = e;
    cancelAnimationFrame(raf.current); // at most one style write per frame
    raf.current = requestAnimationFrame(() => {
      const r = el.getBoundingClientRect();
      const x = (clientX - r.left) / r.width - 0.5; const y = (clientY - r.top) / r.height - 0.5;
      el.style.transform = `perspective(900px) rotateX(${(-y * max).toFixed(2)}deg) rotateY(${(x * max).toFixed(2)}deg) translateZ(0)`;
    });
  };
  const leave = () => { cancelAnimationFrame(raf.current); if (ref.current) ref.current.style.transform = ''; };
  return (<div ref={ref} className={className} style={style} onMouseMove={move} onMouseLeave={leave} {...rest}>{children}</div>);
}

/** Animates between numeric values (e.g. when a live bid lands). */
export function AnimatedMoney({ value, digits = 0, format, ...rest }) {
  const [shown, setShown] = useState(value ?? 0);
  const from = useRef(value ?? 0);
  useEffect(() => {
    if (value == null) return undefined;
    const start = performance.now(); const a = from.current; const b = Number(value);
    let raf;
    const tick = (t) => {
      const p = Math.min(1, (t - start) / 700); const e = 1 - (1 - p) ** 3;
      setShown(a + (b - a) * e);
      if (p < 1) raf = requestAnimationFrame(tick); else from.current = b;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <span {...rest}>{format ? format(shown) : money(value == null ? null : shown, digits)}</span>;
}

/* ------------------------------------------------------------------ toasts */
const ToastCtx = createContext(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }) {
  const [items, setItems] = useState([]);
  const push = useCallback((text, kind = '') => {
    const id = crypto.randomUUID();
    setItems((l) => [...l.slice(-3), { id, text, kind }]);
    setTimeout(() => setItems((l) => l.filter((t) => t.id !== id)), 5500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => <div key={t.id} className={`toast ${t.kind}`}>{t.text}</div>)}
      </div>
    </ToastCtx.Provider>
  );
}

/* ------------------------------------------------------------------ time */
export function useNow(interval = 1000) {
  const [now, setNow] = useState(clock.now());
  useEffect(() => { const t = setInterval(() => setNow(clock.now()), interval); return () => clearInterval(t); }, [interval]);
  return now;
}

export function useCountdown(endIso) {
  const now = useNow();
  const ms = endIso ? Math.max(0, new Date(endIso).getTime() - now) : 0;
  const s = Math.floor(ms / 1000);
  const parts = { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60 };
  const pad = (x) => String(x).padStart(2, '0');
  const text = ms === 0 ? 'Ended' : parts.d ? `${parts.d}d ${pad(parts.h)}h ${pad(parts.m)}m` : `${pad(parts.h)}:${pad(parts.m)}:${pad(parts.s)}`;
  return { ms, parts, text, urgent: ms > 0 && ms < 120000 };
}

/** true once the end time has passed. Re-renders only at that moment (not every second), so a page can react to the end cheaply. */
export function useEnded(endIso) {
  const [ended, setEnded] = useState(() => (endIso ? new Date(endIso).getTime() <= clock.now() : false));
  useEffect(() => {
    if (!endIso) { setEnded(false); return undefined; }
    const left = new Date(endIso).getTime() - clock.now();
    if (left <= 0) { setEnded(true); return undefined; }
    setEnded(false);
    const t = setTimeout(() => setEnded(true), Math.min(left, 2 ** 31 - 1));
    return () => clearTimeout(t);
  }, [endIso]);
  return ended;
}

export function Countdown({ end }) {
  const { text, urgent } = useCountdown(end);
  return <span style={{ color: urgent ? 'var(--bad)' : undefined, fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>{text}</span>;
}

export function CountdownBlocks({ end }) {
  const { parts, ms, urgent } = useCountdown(end);
  const cells = parts.d ? [['d', 'days'], ['h', 'hrs'], ['m', 'min'], ['s', 'sec']] : [['h', 'hrs'], ['m', 'min'], ['s', 'sec']];
  return (
    <div className={`cd ${urgent ? 'urgent' : ''}`} role="timer" aria-label={ms ? 'Time remaining' : 'Auction ended'}>
      {cells.map(([k, label]) => (<div className="cell" key={k}><b>{String(parts[k]).padStart(2, '0')}</b><span>{label}</span></div>))}
    </div>
  );
}

/* ------------------------------------------------------------------ data */
/** Catches rendering crashes so one bug never blanks the whole app. */
export class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error, info) { console.error('UI crash:', error, info?.componentStack); }
  componentDidUpdate(prev) { if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null }); } // leaving the page clears the error
  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="wrap page center" role="alert" style={{ maxWidth: 560 }}>
        <div className="card glow pad" style={{ padding: 36 }}>
          <div style={{ fontSize: 44 }}>🛠️</div>
          <h2>Something went wrong on this page</h2>
          <p className="mute">The rest of the site is fine. Reload to try again; if it keeps happening, please tell support what you were doing.</p>
          <button className="btn gold" onClick={() => window.location.reload()}>Reload page</button>
        </div>
      </div>
    );
  }
}

/** Shown while the browser is offline, because live bidding needs a connection. */
export function OfflineBanner() {
  const [online, setOnline] = useState(typeof navigator === 'undefined' ? true : navigator.onLine);
  useEffect(() => {
    const on = () => setOnline(true); const off = () => setOnline(false);
    window.addEventListener('online', on); window.addEventListener('offline', off);
    return () => { window.removeEventListener('online', on); window.removeEventListener('offline', off); };
  }, []);
  return online ? null : <div className="offline" role="status">You're offline — live bids and prices are paused until your connection returns.</div>;
}

export const Spinner = () => <p className="mute">Loading…</p>;

export function useAsync(fn, deps) {
  const [state, setState] = useState({ loading: true, data: null, error: null });
  const seq = useRef(0);
  const run = useCallback(async () => {
    const id = ++seq.current; // ignore out-of-order responses (fast filter changes)
    try {
      const data = await fn();
      if (id === seq.current) setState({ loading: false, data, error: null });
    } catch (error) {
      if (id === seq.current) setState({ loading: false, data: null, error });
    }
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { run(); }, [run]);
  return { ...state, reload: run };
}

export function Confetti({ run }) {
  if (!run) return null;
  const colors = ['#fbe7ae', '#e0aa48', '#8b6cff', '#ff5c9a', '#37e6a0'];
  return (
    <div className="confetti" aria-hidden="true">
      {Array.from({ length: 70 }, (_, i) => (
        <i key={i} style={{ left: `${Math.random() * 100}%`, background: colors[i % colors.length], animationDuration: `${2.2 + Math.random() * 2.2}s`, animationDelay: `${Math.random() * 0.6}s`, transform: `rotate(${Math.random() * 360}deg)` }} />
      ))}
    </div>
  );
}
