# Analysis
use [snakemake](http://snakemake.readthedocs.io/en/latest/index.html) to manage workflows.

even works on the cluster
`snakemake --jobs 999 --cluster 'bsub -q normal -R "rusage[mem=4000]"'`

simple split-gather pattern
https://groups.google.com/forum/#!topic/snakemake/tXEb2MBccHQ

# analysis steps
1. copy to server (lab share or compute server?)
2. containerize: `ffmpeg -i source.h264 -vcodec copy out.mp4`
3. track all chambers
4. gather data, trial-average, plot
