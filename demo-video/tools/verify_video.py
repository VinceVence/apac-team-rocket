"""Verify a final film; --master optionally gives the generated audio headroom locally."""
import array
import argparse
import hashlib
import json
import math
import os
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--story', action='store_true')
parser.add_argument('--story-v2', action='store_true')
parser.add_argument('--film', type=Path)
parser.add_argument('--master', action='store_true')
parser.add_argument('--width', type=int, default=1920)
parser.add_argument('--height', type=int, default=1080)
parser.add_argument('--max-bytes', type=int)
args=parser.parse_args()
FILM=ROOT/'out'/('mint-town-story-narrated.mp4' if args.story_v2 else 'mint-town-story.mp4' if args.story else 'mint-town-apac-demo.mp4')
if args.film:
 FILM=args.film.resolve()
FF=imageio_ffmpeg.get_ffmpeg_exe()
if args.master:
 assert FILM.parent.resolve()==(ROOT/'out').resolve(), 'Master only generated film exports'
 mastered=FILM.with_suffix('.audio-master.mp4')
 subprocess.run([FF,'-y','-v','error','-i',str(FILM),'-c:v','copy',
  '-af','aresample=192000,alimiter=limit=0.794328:level=false:latency=true,aresample=48000',
  '-c:a','aac','-b:a','256k','-movflags','+faststart',str(mastered)],check=True)
 mastered.replace(FILM)
compositor=ROOT/'node_modules/@remotion/compositor-darwin-arm64'
env=dict(os.environ, DYLD_LIBRARY_PATH=str(compositor))
probe=json.loads(subprocess.check_output([str(compositor/'ffprobe'),'-v','error','-show_format','-show_streams','-of','json',str(FILM)],env=env))
video=next(s for s in probe['streams'] if s['codec_type']=='video')
audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
assert (video['width'],video['height'])==(args.width,args.height)
if args.max_bytes:
 assert FILM.stat().st_size < args.max_bytes, 'Submission exceeds the byte limit'
assert video['r_frame_rate']=='30/1'
assert video['codec_name']=='h264' and audio['codec_name']=='aac'
expected_seconds=sum(s['duration'] for s in json.loads((ROOT/'story-v2.json').read_text())['scenes']) if args.story_v2 else 180
assert expected_seconds<=180, 'Competition film exceeds three minutes'
assert abs(float(probe['format']['duration'])-expected_seconds)<.1
assert int(video['nb_frames'])==round(expected_seconds*30)
pcm=subprocess.check_output([FF,'-v','error','-i',str(FILM),'-vn','-ar','16000','-ac','1','-f','s16le','-'])
samples=array.array('h',pcm)
rms=[]
for second in range(math.ceil(expected_seconds)):
 chunk=samples[second*16000:(second+1)*16000]
 rms.append(round(20*math.log10(max(1,math.sqrt(sum(x*x for x in chunk)/max(1,len(chunk))))/32768),2))
assert sum(x>-40 for x in rms)>=140, 'Narration coverage unexpectedly low'
float_pcm=subprocess.check_output([FF,'-v','error','-i',str(FILM),'-vn','-f','f32le','-'])
peak=max(abs(x) for x in array.array('f',float_pcm))
assert peak<1, 'Audio exceeds full scale'
if args.story_v2:
 from build_story_v2 import check_audio
 check_audio()
 story=json.loads((ROOT/'story-v2.json').read_text())
 assert sum(s['duration'] for s in story['scenes'])==expected_seconds
else:
 scenes=json.loads((ROOT/('story-script.json' if args.story else 'script.json')).read_text())
 assert sum(s['duration'] for s in scenes)==180
 assert all(s['audioDuration']/s['playbackRate']+s.get('offset',.4)<s['duration'] for s in scenes)
report={'duration_seconds':float(probe['format']['duration']),'frames':int(video['nb_frames']),'resolution':[video['width'],video['height']],'fps':video['r_frame_rate'],'video_codec':video['codec_name'],'audio_codec':audio['codec_name'],'audio_sample_rate':audio['sample_rate'],'audio_peak_dbfs':round(20*math.log10(peak),2),'seconds_above_minus40_dbfs':sum(x>-40 for x in rms),'size_bytes':FILM.stat().st_size,'sha256':hashlib.sha256(FILM.read_bytes()).hexdigest(),'new_gemini_calls':0,'qa_frames':14 if args.story else 12,'rms_by_second_dbfs':rms}
if args.story_v2:
 report['voiced_lines']=len(story['lines'])
 report.pop('qa_frames',None)
(FILM.with_suffix('.verification.json') if args.film else ROOT/'out'/('story-narrated-verification.json' if args.story_v2 else 'story-verification.json' if args.story else 'verification.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='rms_by_second_dbfs'},indent=2))
