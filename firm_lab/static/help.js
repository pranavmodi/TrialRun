// One help control per section, including sections created after a live update.
(() => {
const tips={
 'put an agent to work.':'TrialRun gives an agent a fictional job, records its actions, and checks the result.',
 'enter the lab':'Sign in as a lab operator to start tests, observe work, and grade attempts.',
 'attempt controls':'Advance only this attempt. You can inspect its workspace at any time. Grading freezes the records.',
 'put an agentto work.':'TrialRun gives an agent a fictional job, records its actions, and checks the result.',
 'the evaluation lab':'Start here to see how a model performs in a simulated firm.',
 'field guide':'These are the three steps of a typical intake test, not results from a live attempt.',
 'injured in an accident? you don’t have to face it alone.':'This is the fictional client’s entrance to the practice firm. The form uses test details only.',
 'open tasks':'Work someone still needs to complete, including callbacks.',
 'active matters':'Potential cases that are still open in the practice firm.',
 'awaiting review':'Draft messages waiting for a person to review them.',
 'start from the front door.':'Submit a fictional inquiry on the practice website and follow it into the leads inbox.',
 'your case review':'Fill in fictional details to send a new inquiry to the practice inbox.',
 'next actions':'See what still needs to happen on this case.',
 'injuries / medical care':'Symptoms and treatment reported in this inquiry, not a medical assessment.',
 'client communications':'Drafts and messages linked to the selected case. They stay in the simulation.',
 'notes':'Additional information that staff or an agent saved on this case.',
 'scenario library':'Pick a job to test. Each attempt starts with its own copy of the starting records.',
 'convert one website inquiry':'Jamie submits a form. The clerk should create one accurate contact and one linked potential case.',
 'model-backed agent':'A real model chooses what to do. Pick a local or OpenClaw clerk, or edit its instructions before starting.',
 'attempts':'Each row is one independent try. Open the attempt for its score or the workspace for its records.',
 'more scenarios and other runs':'Explore other situations, such as a returning caller. The scripts show how the fixtures work.',
 'run scenarios in parallel':'Start several independent scripts together. They do not share records or measure an AI model.',
 'workspace state':'These are the records inside this attempt, not the records in your practice firm.',
 'agent actions & activity':'Follow the order of events. Expand an event to see who acted and what changed.',
 'model turns':'Inspect the requests, tool results and final response recorded while the model worked.',
 'limits':'Stop this agent after a maximum number of decisions or elapsed seconds, whichever comes first.',
 'new agent profile':'Save a reusable provider, set of instructions, and budget for future attempts.',
 'edit agent profile':'Changes apply to new attempts. Earlier attempts keep the settings they actually used.',
 'agent connection details':'Give the external agent the limited token for this attempt, never your controller token.',
 'new inquiries':'Website forms wait here until someone converts or ignores them.',
 'leads inbox':'Incoming inquiries before they become a contact and potential case.',
 'your firm at a glance':'See what is waiting for the practice firm. Test attempts have separate records.',
 'intake pipeline':'Each column is a stage. Follow potential cases from initial inquiry onward.',
 'contacts':'People the firm has heard from. One person can have more than one case.',
 'tasks & callbacks':'Follow promised calls and other work, including who owns it and when it is due.',
 'communications':'Read and draft simulated messages. Nothing is delivered to real clients.',
 'consultations & calendar':'Check appointments against the staff calendar to avoid scheduling conflicts.',
 'calendar':'See the appointments and their assigned staff in this firm.',
 'documents':'Read case documents and their saved versions.',
 'attorney handoffs':'Identify issues that need a person to review and follow their resolution.',
 'conversation observer':'Review the sequence of messages and any recording attached to a practice conversation.',
 'conversations':'See what the participants said, in order.',
 'firm controls':'Set the practice firm’s rules, staff, forms and reusable workflows.',
 'audit history':'See who changed which record, and compare the before and after values.',
 'operation explorer':'Inspect or run the same operations the website and command line use.',
 'world controls & access':'Manage access and the simulated clock. Reset only when you want to clear this practice firm.',
 'forms':'Choose which questions the practice website asks.',
 'staff':'The people available to own work, take appointments, and review cases.',
 'workflows':'Reusable steps that staff can apply to a case.',
 'case notes':'Read the notes saved against a potential case.',
 'linked cases':'Potential cases that refer to this same person.',
 'your next actions':'Items the practice firm still needs to handle.',
 'follow through on commitments':'Look here for callbacks and other work that remains open.',
 'recent matters':'The firm’s most recently created potential cases.',
 'api reference':'Use the same firm operations from an app or the command line.',
 'operation directory':'Find the command for a task and check which role can use it.',
 'first, tell your story.':'A short account in your own words is enough to start the practice inquiry.',
 'tell us what happened.':'Use this form to simulate a website submission. No real lawyer receives it.',
 'what to expect':'This explains what information a visitor needs before submitting an inquiry.',
 'preview jamie’s website form':'See the exact fictional submission before it reaches this attempt’s inbox.'
};
const pop=document.createElement('div');pop.className='help-pop';pop.id='section-explanation';pop.setAttribute('role','tooltip');pop.hidden=true;
document.body.append(pop);
let active=null;
function close(){if(active)active.removeAttribute('aria-describedby');active=null;pop.hidden=true}
function show(b){close();active=b;(b.closest('dialog')||document.body).append(pop);pop.textContent=b.dataset.explanation;pop.hidden=false;b.setAttribute('aria-describedby',pop.id);
 const r=b.getBoundingClientRect(),p=pop.getBoundingClientRect();pop.style.left=Math.max(8,Math.min(innerWidth-p.width-8,r.left))+'px';
 pop.style.top=(r.bottom+p.height+8<innerHeight?r.bottom+6:Math.max(6,r.top-p.height-6))+'px';}
const controls=new WeakMap();
function scan(){
 if(active&&!active.isConnected)close();
 const selector='h1,h2,h3,.card-label,.column-heading,.run-controls>.eyebrow,.trust-strip[aria-label],details>summary';
 document.querySelectorAll(selector).forEach(el=>{
   const summary=el.tagName==='SUMMARY',parent=el.parentElement;
   if(!parent||el.closest('pre,button,a,.matter-card,.help-pop')||(summary&&(parent.dataset.key&&!/^(set-|profile$)/.test(parent.dataset.key)||el.closest('#activity'))))return;
   const name=(el.getAttribute('aria-label')||el.textContent).replace(/\s+/g,' ').trim();if(!name)return;
   const k=name.toLowerCase(),desc=tips[k]||
    (/checks passed/.test(k)?'The grader compared saved records with the scenario rules. Expand a check to see its evidence.':
     /· attempt \d+/.test(k)?'This page follows one isolated attempt, from the starting records to its final grade.':
     (el.id==='page-title'&&document.querySelector('#page-description')?.textContent)||
     (el.id==='modal-title'?'Review the details for this action here before continuing.':''));
   // Read the section’s own description for custom scenarios and record panels.
   const owner=parent.classList.contains('help-anchor')?parent.parentElement:parent;
   const copy=desc||owner.querySelector(':scope > p:not(.eyebrow):not(.error)')?.textContent.trim().slice(0,220)||
    (el.matches('.card-label')?'Count of '+name.toLowerCase()+' in this firm.':el.matches('.column-heading')?'Cases currently at this stage of intake.':
    summary?'Expand to inspect '+name+' for the selected firm or attempt.':'Details for '+name+' in the current view.');
   let b=controls.get(el);
   if(!b){
     b=document.createElement('button');b.type='button';b.className='help-dot';b.textContent='?';controls.set(el,b);
     if(el.matches('.trust-strip'))el.querySelector('.shell').append(b);
     else if(summary){const d=el.parentElement,w=document.createElement('div');w.className='help-fold';d.before(w);w.append(d,b)}
     else {const w=document.createElement('div');w.className='help-anchor';el.before(w);w.append(el,b)}
   }
   b.dataset.explanation=copy;b.setAttribute('aria-label','About '+name);
 });
}
document.addEventListener('pointerover',e=>{const b=e.target.closest('.help-dot');if(b)show(b)});
document.addEventListener('pointerout',e=>{if(active&&e.target===active&&document.activeElement!==active)close()});
document.addEventListener('focusin',e=>{if(e.target.matches('.help-dot'))show(e.target);else close()});
document.addEventListener('focusout',e=>{if(e.target===active)close()});
document.addEventListener('click',e=>{const b=e.target.closest('.help-dot');if(b)show(b);else close()});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&active){e.preventDefault();e.stopPropagation();close()}},true);
window.addEventListener('resize',close);document.addEventListener('scroll',close,true);
let pending=false;const observer=new MutationObserver(m=>{if(!pending&&m.some(v=>v.target!==pop&&!pop.contains(v.target))){pending=true;queueMicrotask(()=>{pending=false;scan()})}});
scan();observer.observe(document.body,{childList:true,subtree:true,characterData:true});
})();
