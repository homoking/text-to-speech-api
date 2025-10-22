const MAX_CHARS = 3000;
const LS_KEY = "tts-ui-state-v1";

// Elements
const $ = (sel) => document.querySelector(sel);
const els = {
  text: $("#text"), ssml: $("#ssml"), engine: $("#engine"), voice: $("#voice"),
  format: $("#format"), rate: $("#rate"), pitch: $("#pitch"),
  rateVal: $("#rateVal"), pitchVal: $("#pitchVal"),
  charCounter: $("#charCounter"), voiceHelp: $("#voiceHelp"),
  gen: $("#generateBtn"), clear: $("#clearBtn"), spinner: $("#spinner"),
  status: $("#status"), player: $("#player"), copy: $("#copyBtn"),
  download: $("#downloadLink"), info: $("#info"), toast: $("#toast"),
};

function setBusy(b) {
  els.gen.disabled = b;
  els.spinner.classList.toggle("hidden", !b);
  els.status.textContent = b ? "Working…" : "";
}
function toast(msg, ok=false){ els.toast.textContent=msg; els.toast.classList.remove("hidden"); els.toast.classList.toggle("ok", ok); setTimeout(()=>els.toast.classList.add("hidden"), 2200); }
function updateCounters(){ const n=(els.text.value||"").length; els.charCounter.textContent = `${n} / ${MAX_CHARS}`; }
function updateSliders(){ els.rateVal.textContent = `${els.rate.value}%`; els.pitchVal.textContent = `${els.pitch.value}`; }
function saveState(){
  const st={engine:els.engine.value, voice:els.voice.value, format:els.format.value, rate:+els.rate.value, pitch:+els.pitch.value, ssml:els.ssml.checked, text: (els.text.value||"").slice(0,2000)};
  localStorage.setItem(LS_KEY, JSON.stringify(st));
}
function loadState(){
  try{ const st=JSON.parse(localStorage.getItem(LS_KEY)||"{}");
    if(st.engine) els.engine.value=st.engine;
    if(st.format) els.format.value=st.format;
    if(typeof st.rate==="number") els.rate.value=st.rate;
    if(typeof st.pitch==="number") els.pitch.value=st.pitch;
    if(typeof st.ssml==="boolean") els.ssml.checked=st.ssml;
    if(st.text) els.text.value=st.text;
  }catch{}
  updateCounters(); updateSliders();
}
function absoluteUrl(p){ return `${window.location.origin}${p}`; }

async function fetchVoices(engine){
  els.voice.innerHTML = `<option value="">Loading…</option>`;
  els.voiceHelp.classList.add("hidden");
  try{
    const res = await fetch(`/voices?engine=${encodeURIComponent(engine)}`);
    if(!res.ok) throw new Error(await res.text());
    const data = await res.json();
    const voices = data.voices||[];
    if(!voices.length){
      els.voice.innerHTML = `<option value="">No voices found</option>`;
      els.voiceHelp.textContent = engine==="pyttsx3" ? "pyttsx3 voices depend on your OS installation." : "Could not load edge voices.";
      els.voiceHelp.classList.remove("hidden"); return;
    }
    els.voice.innerHTML = voices.map(v=>`<option value="${v.id}">${v.id} — ${v.locale} — ${v.gender}</option>`).join("");
    const st = JSON.parse(localStorage.getItem(LS_KEY)||"{}");
    if(st.voice && voices.some(v=>v.id===st.voice)) els.voice.value = st.voice;
  }catch(e){
    els.voice.innerHTML = `<option value="">Error loading voices</option>`;
    els.voiceHelp.textContent = "Please retry later.";
    els.voiceHelp.classList.remove("hidden");
  }
}

async function callTTS(payload){
  const res = await fetch("/tts",{method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(payload)});
  if(!res.ok) { const msg = await res.text().catch(()=> ""); throw new Error(msg || "TTS failed"); }
  return res.json();
}

// events
els.text.addEventListener("input", ()=>{ autoGrow(els.text); updateCounters(); saveState(); });
["change","input"].forEach(ev => els.ssml.addEventListener(ev, saveState));
els.engine.addEventListener("change", async ()=>{ saveState(); await fetchVoices(els.engine.value); });
["change"].forEach(ev => els.voice.addEventListener(ev, saveState));
["change"].forEach(ev => els.format.addEventListener(ev, saveState));
els.rate.addEventListener("input", ()=>{ updateSliders(); saveState(); });
els.pitch.addEventListener("input", ()=>{ updateSliders(); saveState(); });

els.copy.addEventListener("click", async ()=>{
  const src = els.player.getAttribute("src");
  if(!src) return toast("Generate audio first.");
  try{ await navigator.clipboard.writeText(absoluteUrl(src)); toast("URL copied ✓", true); } catch { toast("Copy failed."); }
});
els.clear.addEventListener("click", ()=>{
  els.text.value=""; updateCounters(); autoGrow(els.text); toast("Cleared", true); saveState();
});

els.gen.addEventListener("click", async ()=>{
  const txt = els.text.value||"";
  if(!txt.trim()) return toast("Text cannot be empty.");
  if(txt.length > MAX_CHARS) return toast(`Max ${MAX_CHARS} characters.`);

  const payload = {
    text: txt, engine: els.engine.value, voice: els.voice.value || "",
    rate: Number(els.rate.value), pitch: Number(els.pitch.value),
    format: els.format.value, ssml: els.ssml.checked, normalize: !els.ssml.checked,
  };

  setBusy(true); els.info.textContent=""; els.download.classList.add("hidden");
  try{
    const data = await callTTS(payload);
    const { audio_url, duration, cached, engine, voice, format } = data;
    els.player.setAttribute("src", audio_url);
    els.player.load();
    els.download.href = audio_url; els.download.classList.remove("hidden");
    const durStr = duration ? `${Number(duration).toFixed(2)}s` : "—";
    els.info.textContent = `engine=${engine} • voice=${voice||"default"} • format=${format} • duration=${durStr} • ${cached ? "cached" : "generated"}`;
    toast(cached ? "Served from cache." : "Generated ✓", true);
  }catch(e){
    toast("Synthesis failed. Check server logs.");
  }finally{ setBusy(false); }
});

// niceties
function autoGrow(el){ el.style.height="auto"; el.style.height = Math.min(360, el.scrollHeight) + "px"; }
function init(){ loadState(); autoGrow(els.text); fetchVoices(els.engine.value); }
document.addEventListener("DOMContentLoaded", init);
