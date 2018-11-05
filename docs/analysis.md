# Analysis
use [snakemake](http://snakemake.readthedocs.io/en/latest/index.html) to manage workflows.

simple split-gather pattern
https://groups.google.com/forum/#!topic/snakemake/tXEb2MBccHQ

# analysis steps
1. copy to server (lab share or compute server?)
2. containerize: `ffmpeg -i source.h264 -vcodec copy out.mp4` - needs to be 'mp4', not 'avi', otherwise weird issues occur because the frame rate in the h264 file is wrong (25 or 50 fps, but we record at 40 fps)
3. track all chambers
4. gather data, trial-average, plot
