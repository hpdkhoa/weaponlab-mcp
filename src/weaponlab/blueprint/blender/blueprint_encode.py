"""PNG frames to an H.264 MP4 with Blender's own encoder (its sequence editor): no ffmpeg needed on the PATH.

    blender -b --factory-startup -P blueprint_encode.py -- <job.json>
job: {"frames": folder of c00000.png..., "count": n, "fps": 15, "size": [w, h], "out": "<file>.mp4"}"""
import json
import os
import sys

import bpy

job = json.load(open(sys.argv[sys.argv.index("--") + 1], encoding="utf-8"))
sc = bpy.context.scene
sc.render.resolution_x, sc.render.resolution_y = job["size"]
sc.render.resolution_percentage = 100
sc.render.fps = int(job["fps"])
sc.frame_start, sc.frame_end = 1, int(job["count"])
sc.sequence_editor_create()
files = [{"name": "c%05d.png" % k} for k in range(int(job["count"]))]
strips = sc.sequence_editor.strips if hasattr(sc.sequence_editor, "strips") else sc.sequence_editor.sequences
st = strips.new_image("frames", os.path.join(job["frames"], files[0]["name"]), 1, 1)
for f in files[1:]:
    st.elements.append(f["name"])
st.frame_final_duration = int(job["count"])
sc.render.image_settings.media_type = 'VIDEO' if hasattr(sc.render.image_settings, "media_type") else None
sc.render.image_settings.file_format = 'FFMPEG'
sc.render.ffmpeg.format = 'MPEG4'
sc.render.ffmpeg.codec = 'H264'
sc.render.ffmpeg.constant_rate_factor = 'HIGH'
sc.render.filepath = job["out"]
sc.render.use_file_extension = False
bpy.ops.render.render(animation=True)
print("ENCODED " + job["out"])
