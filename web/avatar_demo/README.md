# Avatar activity demo

Semi-realistic 3D avatar styled after the Adarsh reference photos (black bomber, cream quarter-zip polo, slim jeans, blue sneakers, glasses, moustache + goatee, backpack straps).
Activities: walk with coffee (default), walk, idle, run, wave, talk, sit, type, jump, dance, stretch. The **Cap** checkbox swaps the quiff for a blue cap.

## Run the web demo
```
cd web/avatar_demo && python3 -m http.server 8000   # then open http://localhost:8000
```
three.js loads from jsDelivr, so the page needs internet access. Pick an activity with the buttons or keys 1–9, 0.

## Where the motion lives
`engine/animation/activities.py` is the single source of truth (pure Python, rig bone names).
- Web: `python3 tools/export_clips.py` samples it to `clips.json`, which `avatar.js` plays back (re-run after editing).
- Blender: `blender -b -P engine/animation/demo.py -- --role default` builds the rigged character, bakes each
  activity to an Action/NLA track and writes `work/avatar_activities.glb`.
  **The Blender path is not yet tested** (Blender wasn't available when written); check bone axis directions on first run.

## Next steps
Load the Adarsh GLB in the web viewer, more activities, blend/transition graph, speech lip-sync.
