# M24 SWS through MCP calls only

The M24 Sniper Weapon System built from nothing in a fresh environment, by calling the Weapon Lab MCP server's tools
only, the way another session would. Tested on 2026-10-24: 62 calls, every one ok. The model has 25,041 faces, every
mesh sound, and passes the contract, the length and the finish gate. Its 12 hand clips show 0 clipping seen from the
first-person camera on 1,226 frames.

1. Install the labs: `pip install "weaponlab-mcp[blueprint] @ git+https://github.com/hpdkhoa/weaponlab-mcp.git"
   "ocrlab-mcp[lines] @ git+https://github.com/hpdkhoa/ocrlab-mcp.git" "fakepose-mcp @ git+https://github.com/hpdkhoa/fakepose-mcp.git"
   "poselab-mcp @ git+https://github.com/hpdkhoa/poselab-mcp.git"`.
2. Make a project folder with a `weaponlab.json` like `weaponlab.example.json`: Blender 5.2 and your own shared arms
   (an arms FBX and its idle clip; the example's arms are a game's asset and are not shipped).
3. Download the sources the calls name: the US Air Force M24 photo (public domain), FM 23-10 (1994, approved for public
   release), the Wikipedia M24 page's facts and the H-S Precision PSL134 spec sheet (facts only). Point `M` in
   `m24_mcp_calls.py` at them.
4. `python m24_mcp_calls.py > calls.json`, then with WEAPONLAB_PROJECT and WEAPONLAB_DIGITIZE set:
   `python client.py weaponlab-mcp @calls.json`.
